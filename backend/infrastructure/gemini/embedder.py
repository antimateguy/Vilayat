"""The Embedder port, implemented with the Gemini embedding models.

Google's two embedding generations are told what a text is for in different
ways, so there is one small class for each. Both produce vectors of
EMBEDDING_DIMENSIONS entries with length 1.
"""

import math
import time
from collections import deque
from collections.abc import Callable, Sequence
from itertools import batched
from typing import Any

from google import genai
from google.genai import types

from domain.document import EMBEDDING_DIMENSIONS
from infrastructure.gemini.sdk import SDK_ERRORS, describe, is_daily_quota_error
from ports.embedder import Embedder, EmbedderUnavailableError
from ports.usage import DailyLimitReachedError, RequestBudget

BATCH_SIZE = 16
"""Texts sent in one call: few enough to stay inside the per-request limits."""


class _GeminiEmbedder(Embedder):
    def __init__(
        self,
        client: genai.Client,
        model: str,
        budget: RequestBudget,
        pace: "TextPace | None" = None,
    ) -> None:
        self._client = client
        self._model = model
        self._budget = budget
        self._pace = pace

    @property
    def model_name(self) -> str:
        return self._model

    def _embed(self, contents: list[Any], task_type: str | None) -> list[tuple[float, ...]]:
        config = types.EmbedContentConfig(
            output_dimensionality=EMBEDDING_DIMENSIONS, task_type=task_type
        )
        # The free tier counts every text in a call as one request.
        self._budget.spend(len(contents))
        if self._pace is not None:
            self._pace.wait_for(len(contents))
        try:
            result = self._client.models.embed_content(
                model=self._model, contents=contents, config=config
            )
        except SDK_ERRORS as error:
            if is_daily_quota_error(error):
                self._budget.use_up()
                raise DailyLimitReachedError(
                    self._model, self._budget.status().resets_at
                ) from error
            raise EmbedderUnavailableError(f"{self._model}: {describe(error)}") from error

        vectors = [tuple(embedding.values or ()) for embedding in result.embeddings or ()]
        if len(vectors) != len(contents):
            raise EmbedderUnavailableError(
                f"{self._model} returned {len(vectors)} vectors for {len(contents)} texts"
            )
        if any(len(vector) != EMBEDDING_DIMENSIONS for vector in vectors):
            raise EmbedderUnavailableError(f"{self._model} returned a vector of the wrong length")
        return [_unit_length(vector) for vector in vectors]


class GeminiEmbedder(_GeminiEmbedder):
    """gemini-embedding-2 and later: the task is written into the text itself."""

    def embed_documents(self, texts: Sequence[str]) -> list[tuple[float, ...]]:
        vectors: list[tuple[float, ...]] = []
        for batch in batched(texts, BATCH_SIZE):
            # Several plain strings in one call would be merged into one vector;
            # one Content per text gives one vector per text.
            contents = [_content(f"title: none | text: {text}") for text in batch]
            vectors.extend(self._embed(contents, task_type=None))
        return vectors

    def embed_query(self, text: str) -> tuple[float, ...]:
        return self._embed([_content(f"task: question answering | query: {text}")], None)[0]


class GeminiTaskTypeEmbedder(_GeminiEmbedder):
    """gemini-embedding-001: the task is a separate parameter."""

    def embed_documents(self, texts: Sequence[str]) -> list[tuple[float, ...]]:
        vectors: list[tuple[float, ...]] = []
        for batch in batched(texts, BATCH_SIZE):
            vectors.extend(self._embed(list(batch), task_type="RETRIEVAL_DOCUMENT"))
        return vectors

    def embed_query(self, text: str) -> tuple[float, ...]:
        return self._embed([text], task_type="QUESTION_ANSWERING")[0]


class TextPace:
    """Keeps an offline job under the free tier's texts per minute by waiting
    before a call that would go over. The API never waits: it embeds one
    question at a time."""

    def __init__(
        self,
        per_minute: int,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._per_minute = per_minute
        self._clock = clock
        self._sleep = sleep
        self._sent: deque[tuple[float, int]] = deque()

    def wait_for(self, texts: int) -> None:
        while True:
            now = self._clock()
            while self._sent and now - self._sent[0][0] >= 60:
                self._sent.popleft()
            if sum(count for _, count in self._sent) + texts <= self._per_minute:
                self._sent.append((now, texts))
                return
            self._sleep(60 - (now - self._sent[0][0]) + 0.5)


def create_gemini_embedder(
    client: genai.Client, model: str, budget: RequestBudget, pace: TextPace | None = None
) -> Embedder:
    if model == "gemini-embedding-001":
        return GeminiTaskTypeEmbedder(client, model, budget, pace)
    return GeminiEmbedder(client, model, budget, pace)


def _content(text: str) -> types.Content:
    return types.Content(parts=[types.Part(text=text)])


def _unit_length(vector: tuple[float, ...]) -> tuple[float, ...]:
    """Scale a vector to length 1.

    gemini-embedding-001 does not do this for vectors shortened to 768 entries.
    Cosine similarity ignores length, so search works either way; scaling keeps
    the stored vectors comparable whichever model made them.
    """
    length = math.sqrt(sum(value * value for value in vector))
    if length == 0:
        raise EmbedderUnavailableError("the model returned a vector of zeros")
    return tuple(value / length for value in vector)

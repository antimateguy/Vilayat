"""In-memory stand-ins for the model, the embedder and the vector store.

They let every AI service be tested without a network, a key or a database.
"""

import math
import re
import zlib
from collections.abc import Sequence, Set
from datetime import date

from domain.briefing import AreaBriefing
from domain.document import EMBEDDING_DIMENSIONS, EmbeddedChunk, RetrievedChunk
from ports.briefings import BriefingRepository
from ports.embedder import Embedder, EmbedderUnavailableError
from ports.llm import JsonObject, LLMClient, LLMUnavailableError
from ports.usage import UsageLedger
from ports.vector_store import VectorStore

Reply = str | JsonObject | Exception


class ScriptedLLMClient(LLMClient):
    """Gives prepared replies in order and records the prompts it was sent.

    A reply that is an exception is raised instead of returned, which is how a
    test makes the model fail.
    """

    def __init__(self, *replies: Reply, model_name: str = "scripted-model") -> None:
        self._replies = list(replies)
        self._model_name = model_name
        self.prompts: list[str] = []
        self.schemas: list[JsonObject] = []

    @property
    def model_name(self) -> str:
        return self._model_name

    def generate_text(self, prompt: str) -> str:
        reply = self._next(prompt)
        if not isinstance(reply, str):
            raise TypeError("the test scripted a JSON reply for a text request")
        return reply

    def generate_json(self, prompt: str, schema: JsonObject) -> JsonObject:
        self.schemas.append(schema)
        reply = self._next(prompt)
        if isinstance(reply, str):
            raise TypeError("the test scripted a text reply for a JSON request")
        return reply

    def _next(self, prompt: str) -> str | JsonObject:
        self.prompts.append(prompt)
        if not self._replies:
            raise LLMUnavailableError("the test scripted no further reply")
        reply = self._replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


class WordEmbedder(Embedder):
    """A toy embedder: each word switches on one of the vector's entries.

    Texts that share words point in similar directions, so retrieval behaves
    sensibly in tests. The same text always gives the same vector.
    """

    def __init__(self, model_name: str = "word-embedder", *, available: bool = True) -> None:
        self._model_name = model_name
        self._available = available
        self.queries: list[str] = []

    @property
    def model_name(self) -> str:
        return self._model_name

    def embed_documents(self, texts: Sequence[str]) -> list[tuple[float, ...]]:
        self._require_available()
        return [self._vector(text) for text in texts]

    def embed_query(self, text: str) -> tuple[float, ...]:
        self._require_available()
        self.queries.append(text)
        return self._vector(text)

    def _require_available(self) -> None:
        if not self._available:
            raise EmbedderUnavailableError("the test switched the embedder off")

    @staticmethod
    def _vector(text: str) -> tuple[float, ...]:
        vector = [0.0] * EMBEDDING_DIMENSIONS
        for word in re.findall(r"[a-zäöüß]+", text.lower()):
            # crc32 instead of hash(): hash() changes between Python runs.
            vector[zlib.crc32(word.encode()) % EMBEDDING_DIMENSIONS] = 1.0
        length = math.sqrt(sum(vector)) or 1.0
        return tuple(value / length for value in vector)


class InMemoryVectorStore(VectorStore):
    def __init__(self) -> None:
        self._chunks: dict[tuple[str, int], EmbeddedChunk] = {}

    def add(self, chunks: Sequence[EmbeddedChunk]) -> None:
        for item in chunks:
            self._chunks[item.chunk.document_key, item.chunk.chunk_index] = item

    def search(
        self, embedding: Sequence[float], limit: int, model: str, city_id: str | None = None
    ) -> Sequence[RetrievedChunk]:
        candidates = [
            RetrievedChunk(item.chunk, _cosine(embedding, item.embedding))
            for item in self._chunks.values()
            if item.model == model and (city_id is None or item.chunk.city_id in (None, city_id))
        ]
        return sorted(candidates, key=lambda found: -found.similarity)[:limit]

    def document_keys(self) -> Set[str]:
        return {key for key, _ in self._chunks}

    def delete_document(self, document_key: str) -> None:
        for key in [key for key in self._chunks if key[0] == document_key]:
            del self._chunks[key]

    def stored(self) -> list[EmbeddedChunk]:
        """Everything in the store, in document and chunk order. For assertions."""
        return [self._chunks[key] for key in sorted(self._chunks)]


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    lengths = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return dot / lengths if lengths else 0.0


class InMemoryBriefings(BriefingRepository):
    def __init__(self) -> None:
        self.stored: dict[int, AreaBriefing] = {}

    def get(self, area_id: int) -> AreaBriefing | None:
        return self.stored.get(area_id)

    def save(self, briefing: AreaBriefing) -> None:
        self.stored[briefing.area_id] = briefing


class InMemoryUsageLedger(UsageLedger):
    """Daily request counts in a dictionary."""

    def __init__(self) -> None:
        self.counts: dict[tuple[str, date], int] = {}

    def take(self, model: str, day: date, limit: int, units: int = 1) -> bool:
        used = self.counts.get((model, day), 0)
        if used + units > limit:
            return False
        self.counts[model, day] = used + units
        return True

    def used(self, model: str, day: date) -> int:
        return self.counts.get((model, day), 0)

    def use_up(self, model: str, day: date, limit: int) -> None:
        self.counts[model, day] = max(self.used(model, day), limit)

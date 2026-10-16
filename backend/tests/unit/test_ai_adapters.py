"""The Gemini adapters, with Google's SDK replaced by a stub: no network, no key."""

from types import SimpleNamespace
from typing import Any, cast

import httpx
import pytest
from google import genai
from google.genai import errors

from domain.document import EMBEDDING_DIMENSIONS
from infrastructure.ai_disabled import DisabledEmbedder, DisabledLLMClient
from infrastructure.budget import DailyBudget, UnlimitedBudget
from infrastructure.fakes.ai import InMemoryUsageLedger
from infrastructure.gemini.client import GeminiClient
from infrastructure.gemini.embedder import (
    BATCH_SIZE,
    GeminiEmbedder,
    GeminiTaskTypeEmbedder,
    TextPace,
    create_gemini_embedder,
)
from infrastructure.settings import Settings
from ports.embedder import EmbedderUnavailableError
from ports.llm import LLMUnavailableError
from ports.usage import DailyLimitReachedError

BUSY = errors.ServerError(503, {"error": {"message": "high demand", "status": "UNAVAILABLE"}})
SCHEMA = {"type": "object", "properties": {"rent": {"type": "integer"}}}
FREE = UnlimitedBudget()
DAILY_QUOTA = errors.ClientError(
    429,
    {
        "error": {
            "message": "You exceeded your current quota.",
            "status": "RESOURCE_EXHAUSTED",
            "details": [{"violations": [{"quotaId": "GenerateRequestsPerDayPerProjectPerModel"}]}],
        }
    },
)
MINUTE_QUOTA = errors.ClientError(
    429,
    {
        "error": {
            "message": "You exceeded your current quota.",
            "status": "RESOURCE_EXHAUSTED",
            "details": [
                {"violations": [{"quotaId": "GenerateRequestsPerMinutePerProjectPerModel"}]}
            ],
        }
    },
)


class StubModels:
    """Stands in for `client.models` of the SDK."""

    def __init__(
        self,
        *,
        text: str | None = None,
        error: Exception | None = None,
        vector: list[float] | None = None,
        vectors_per_call: int | None = None,
    ) -> None:
        self._text = text
        self._error = error
        self._vector = vector if vector is not None else [3.0, 4.0] + [0.0] * 766
        self._vectors_per_call = vectors_per_call
        self.calls: list[dict[str, Any]] = []

    def generate_content(self, *, model: str, contents: Any, config: Any) -> Any:
        self.calls.append({"model": model, "contents": contents, "config": config})
        if self._error:
            raise self._error
        return SimpleNamespace(text=self._text)

    def embed_content(self, *, model: str, contents: list[Any], config: Any) -> Any:
        self.calls.append({"model": model, "contents": contents, "config": config})
        if self._error:
            raise self._error
        count = len(contents) if self._vectors_per_call is None else self._vectors_per_call
        return SimpleNamespace(embeddings=[SimpleNamespace(values=self._vector)] * count)


def sdk(models: StubModels) -> genai.Client:
    return cast(genai.Client, SimpleNamespace(models=models))


def sent_texts(call: dict[str, Any]) -> list[str]:
    return [content.parts[0].text for content in call["contents"]]


# --- Text model ---------------------------------------------------------------


def test_text_is_requested_from_the_configured_model_and_trimmed() -> None:
    models = StubModels(text="  A calm area.\n")

    reply = GeminiClient(sdk(models), "flash-test", FREE).generate_text("Describe it")

    assert reply == "A calm area."
    (call,) = models.calls
    assert (call["model"], call["contents"]) == ("flash-test", "Describe it")
    assert call["config"].temperature == 0


def test_json_is_requested_with_the_schema_and_parsed() -> None:
    models = StubModels(text='{"rent": 700}')

    reply = GeminiClient(sdk(models), "flash-test", FREE).generate_json("Extract", SCHEMA)

    assert reply == {"rent": 700}
    config = models.calls[0]["config"]
    assert config.response_mime_type == "application/json"
    assert config.response_json_schema == SCHEMA


@pytest.mark.parametrize(
    "error",
    [BUSY, httpx.ReadTimeout("slow"), httpx.ConnectError("offline")],
    ids=["service busy", "timeout", "no connection"],
)
def test_any_failure_of_the_service_becomes_one_error(error: Exception) -> None:
    client = GeminiClient(sdk(StubModels(error=error)), "flash-test", FREE)

    with pytest.raises(LLMUnavailableError, match="flash-test"):
        client.generate_text("Describe it")
    with pytest.raises(LLMUnavailableError):
        client.generate_json("Extract", SCHEMA)


@pytest.mark.parametrize("text", [None, "", "   "])
def test_an_empty_reply_counts_as_unavailable(text: str | None) -> None:
    with pytest.raises(LLMUnavailableError, match="no text"):
        GeminiClient(sdk(StubModels(text=text)), "flash-test", FREE).generate_text("Describe it")


@pytest.mark.parametrize("text", ["not json at all", '["a", "list"]', '"a string"'])
def test_a_reply_that_is_not_a_json_object_counts_as_unavailable(text: str) -> None:
    with pytest.raises(LLMUnavailableError, match="JSON"):
        GeminiClient(sdk(StubModels(text=text)), "flash-test", FREE).generate_json(
            "Extract", SCHEMA
        )


def test_the_error_message_names_the_status_but_not_the_request() -> None:
    client = GeminiClient(sdk(StubModels(error=BUSY)), "flash-test", FREE)

    with pytest.raises(LLMUnavailableError) as raised:
        client.generate_text("a prompt that must not be echoed")

    assert "503" in str(raised.value)
    assert "must not be echoed" not in str(raised.value)


# --- Embedding models ---------------------------------------------------------


def test_the_newer_embedder_writes_the_task_into_each_text() -> None:
    models = StubModels()
    embedder = GeminiEmbedder(sdk(models), "embedding-test", FREE)

    documents = embedder.embed_documents(["Register within two weeks.", "Rent is due monthly."])
    embedder.embed_query("When do I register?")

    assert len(documents) == 2
    assert sent_texts(models.calls[0]) == [
        "title: none | text: Register within two weeks.",
        "title: none | text: Rent is due monthly.",
    ]
    assert sent_texts(models.calls[1]) == ["task: question answering | query: When do I register?"]
    assert models.calls[0]["config"].output_dimensionality == EMBEDDING_DIMENSIONS
    assert models.calls[0]["config"].task_type is None


def test_the_older_embedder_passes_the_task_as_a_parameter() -> None:
    models = StubModels()
    embedder = GeminiTaskTypeEmbedder(sdk(models), "gemini-embedding-001", FREE)

    embedder.embed_documents(["Register within two weeks."])
    embedder.embed_query("When do I register?")

    assert models.calls[0]["contents"] == ["Register within two weeks."]
    assert models.calls[0]["config"].task_type == "RETRIEVAL_DOCUMENT"
    assert models.calls[1]["config"].task_type == "QUESTION_ANSWERING"


@pytest.mark.parametrize("embedder_class", [GeminiEmbedder, GeminiTaskTypeEmbedder])
def test_vectors_are_scaled_to_length_one(embedder_class: type[GeminiEmbedder]) -> None:
    embedder = embedder_class(
        sdk(StubModels(vector=[3.0, 4.0] + [0.0] * 766)), "embedding-test", FREE
    )

    vector = embedder.embed_query("anything")

    assert vector[:3] == pytest.approx((0.6, 0.8, 0.0))
    assert len(vector) == EMBEDDING_DIMENSIONS


def test_many_documents_are_sent_in_batches_and_come_back_in_order() -> None:
    models = StubModels()
    texts = [f"text {number}" for number in range(BATCH_SIZE + 4)]

    vectors = GeminiEmbedder(sdk(models), "embedding-test", FREE).embed_documents(texts)

    assert len(vectors) == len(texts)
    assert [len(call["contents"]) for call in models.calls] == [BATCH_SIZE, 4]
    assert sent_texts(models.calls[1])[0] == f"title: none | text: text {BATCH_SIZE}"


def test_no_documents_means_no_call() -> None:
    models = StubModels()

    assert GeminiEmbedder(sdk(models), "embedding-test", FREE).embed_documents([]) == []
    assert models.calls == []


@pytest.mark.parametrize(
    ("models", "problem"),
    [
        (StubModels(error=BUSY), "503"),
        (StubModels(error=httpx.ReadTimeout("slow")), "ReadTimeout"),
        (StubModels(vectors_per_call=1), "1 vectors for 2 texts"),
        (StubModels(vector=[1.0] * 100), "wrong length"),
        (StubModels(vector=[0.0] * EMBEDDING_DIMENSIONS), "zeros"),
    ],
    ids=["service busy", "timeout", "a vector is missing", "wrong dimensions", "all zeros"],
)
def test_an_embedding_that_cannot_be_used_is_reported(models: StubModels, problem: str) -> None:
    embedder = GeminiEmbedder(sdk(models), "embedding-test", FREE)

    with pytest.raises(EmbedderUnavailableError, match=problem):
        embedder.embed_documents(["one", "two"])


def test_the_embedder_class_follows_the_model_generation() -> None:
    client = sdk(StubModels())

    older = create_gemini_embedder(client, "gemini-embedding-001", FREE)
    newer = create_gemini_embedder(client, "gemini-embedding-2", FREE)

    assert isinstance(older, GeminiTaskTypeEmbedder)
    assert isinstance(newer, GeminiEmbedder)
    assert (older.model_name, newer.model_name) == ("gemini-embedding-001", "gemini-embedding-2")


# --- Daily allowance -----------------------------------------------------------


def budget(limit: int) -> tuple[DailyBudget, InMemoryUsageLedger]:
    ledger = InMemoryUsageLedger()
    return DailyBudget(ledger, "flash-test", limit), ledger


def test_every_request_is_counted_and_none_is_sent_once_the_day_is_spent() -> None:
    allowance, _ = budget(limit=2)
    models = StubModels(text="ok")
    client = GeminiClient(sdk(models), "flash-test", allowance)

    client.generate_text("one")
    client.generate_text("two")
    with pytest.raises(DailyLimitReachedError) as raised:
        client.generate_text("three")

    assert len(models.calls) == 2
    assert raised.value.resets_at == allowance.status().resets_at
    assert allowance.status().reached


def test_the_providers_daily_refusal_spends_the_rest_of_the_day() -> None:
    allowance, _ = budget(limit=100)
    models = StubModels(error=DAILY_QUOTA)
    client = GeminiClient(sdk(models), "flash-test", allowance)

    with pytest.raises(DailyLimitReachedError):
        client.generate_text("one")
    with pytest.raises(DailyLimitReachedError):
        client.generate_text("two")

    assert len(models.calls) == 1
    assert allowance.status().used == 100


def test_a_per_minute_refusal_does_not_spend_the_day() -> None:
    allowance, _ = budget(limit=100)
    client = GeminiClient(sdk(StubModels(error=MINUTE_QUOTA)), "flash-test", allowance)

    with pytest.raises(LLMUnavailableError) as raised:
        client.generate_text("one")

    assert not isinstance(raised.value, DailyLimitReachedError)
    assert allowance.status().used == 1


def test_every_embedded_text_counts_as_a_request_as_google_counts_it() -> None:
    allowance, _ = budget(limit=100)
    embedder = GeminiEmbedder(sdk(StubModels()), "embedding-test", allowance)

    embedder.embed_documents([f"text {n}" for n in range(BATCH_SIZE + 1)])

    assert allowance.status().used == BATCH_SIZE + 1


def test_a_call_that_would_go_over_the_limit_is_not_sent() -> None:
    allowance, _ = budget(limit=BATCH_SIZE - 1)
    models = StubModels()

    with pytest.raises(DailyLimitReachedError):
        GeminiEmbedder(sdk(models), "embedding-test", allowance).embed_documents(
            [f"text {n}" for n in range(BATCH_SIZE)]
        )
    assert models.calls == []
    assert allowance.status().used == 0


def test_an_offline_job_waits_rather_than_exceed_the_texts_per_minute() -> None:
    now = [0.0]
    waits: list[float] = []

    def sleep(seconds: float) -> None:
        waits.append(seconds)
        now[0] += seconds

    pace = TextPace(per_minute=40, clock=lambda: now[0], sleep=sleep)
    embedder = GeminiEmbedder(sdk(StubModels()), "embedding-test", FREE, pace)

    embedder.embed_documents([f"text {n}" for n in range(3 * BATCH_SIZE)])

    # 16 + 16 fit in the first minute; the third batch waits for it to pass.
    assert len(waits) == 1 and 60 <= waits[0] <= 61


def test_the_embedder_stops_at_the_daily_limit_too() -> None:
    allowance, _ = budget(limit=0)
    models = StubModels()

    with pytest.raises(EmbedderUnavailableError):
        GeminiEmbedder(sdk(models), "embedding-test", allowance).embed_query("question")
    assert models.calls == []


# --- No key configured ----------------------------------------------------------


def test_without_a_key_the_stand_ins_always_report_unavailable() -> None:
    llm, embedder = DisabledLLMClient(), DisabledEmbedder()

    with pytest.raises(LLMUnavailableError):
        llm.generate_text("anything")
    with pytest.raises(LLMUnavailableError):
        llm.generate_json("anything", SCHEMA)
    with pytest.raises(EmbedderUnavailableError):
        embedder.embed_query("anything")
    with pytest.raises(EmbedderUnavailableError):
        embedder.embed_documents(["anything"])


@pytest.mark.parametrize("value", ["", "   "])
def test_a_blank_key_switches_the_ai_layer_off(value: str) -> None:
    assert Settings(gemini_api_key=value).ai_enabled is False


def test_the_key_never_appears_when_settings_are_printed() -> None:
    settings = Settings(gemini_api_key="secret-value")

    assert settings.ai_enabled is True
    assert "secret-value" not in repr(settings)
    assert "secret-value" not in str(settings.model_dump())

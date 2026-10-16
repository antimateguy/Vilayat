"""Stand-ins used when no API key is configured.

They implement the same ports as the Gemini adapters and always report that the
model is unavailable. The services already handle that error, so switching the
AI off needs no "if AI is enabled" check anywhere else (the Null Object pattern).
"""

from collections.abc import Sequence

from ports.embedder import Embedder, EmbedderUnavailableError
from ports.llm import JsonObject, LLMClient, LLMUnavailableError

_REASON = "no API key is configured"


class DisabledLLMClient(LLMClient):
    @property
    def model_name(self) -> str:
        return "disabled"

    def generate_text(self, prompt: str) -> str:
        raise LLMUnavailableError(_REASON)

    def generate_json(self, prompt: str, schema: JsonObject) -> JsonObject:
        raise LLMUnavailableError(_REASON)


class DisabledEmbedder(Embedder):
    @property
    def model_name(self) -> str:
        return "disabled"

    def embed_documents(self, texts: Sequence[str]) -> list[tuple[float, ...]]:
        raise EmbedderUnavailableError(_REASON)

    def embed_query(self, text: str) -> tuple[float, ...]:
        raise EmbedderUnavailableError(_REASON)

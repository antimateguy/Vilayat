"""Port for a large language model."""

from abc import ABC, abstractmethod
from collections.abc import Mapping
from typing import Any

type JsonObject = Mapping[str, Any]


class LLMUnavailableError(Exception):
    """The model could not be reached or returned nothing usable.

    Services catch this and fall back to behaviour that needs no model, so the
    app keeps working without one.
    """


class LLMClient(ABC):
    """The model only translates and explains; it never decides rent, commute or rank."""

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Stored next to anything the model wrote, so its origin can be shown."""

    @abstractmethod
    def generate_text(self, prompt: str) -> str:
        """Raises LLMUnavailableError when the model cannot answer."""

    @abstractmethod
    def generate_json(self, prompt: str, schema: JsonObject) -> JsonObject:
        """Return an object that follows the given JSON Schema.

        Raises LLMUnavailableError when the model cannot answer. The caller still
        validates the result; the schema is a request, not a guarantee.
        """

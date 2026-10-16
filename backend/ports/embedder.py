"""Port for turning text into embedding vectors."""

from abc import ABC, abstractmethod
from collections.abc import Sequence


class EmbedderUnavailableError(Exception):
    """The embedding model could not be reached or returned nothing usable."""


class Embedder(ABC):
    """Every vector returned has domain.document.EMBEDDING_DIMENSIONS entries.

    Both methods raise EmbedderUnavailableError when the model cannot answer.
    """

    @property
    @abstractmethod
    def model_name(self) -> str: ...

    @abstractmethod
    def embed_documents(self, texts: Sequence[str]) -> list[tuple[float, ...]]:
        """One vector per text, in the same order."""

    @abstractmethod
    def embed_query(self, text: str) -> tuple[float, ...]:
        """Vector for a search query. Kept apart from embed_documents because
        embedding models treat a question and a passage differently."""

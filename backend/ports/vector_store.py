"""Port for storing embedded document chunks and searching them by similarity."""

from abc import ABC, abstractmethod
from collections.abc import Sequence, Set

from domain.document import EmbeddedChunk, RetrievedChunk


class VectorStore(ABC):
    @abstractmethod
    def add(self, chunks: Sequence[EmbeddedChunk]) -> None:
        """Store chunks. A chunk with the same document key and index is replaced."""

    @abstractmethod
    def search(
        self, embedding: Sequence[float], limit: int, model: str, city_id: str | None = None
    ) -> Sequence[RetrievedChunk]:
        """The chunks most similar to the embedding, best first.

        Only chunks embedded with the given model are searched: vectors made by
        different models cannot be compared with each other.
        With a city id, only chunks for that city or for every city are searched.
        """

    @abstractmethod
    def document_keys(self) -> Set[str]:
        """The key of every stored document."""

    @abstractmethod
    def delete_document(self, document_key: str) -> None:
        """Remove every chunk of a document. Does nothing if there is none."""

"""Document chunks for retrieval-augmented question answering."""

from dataclasses import dataclass
from datetime import date
from typing import Final

EMBEDDING_DIMENSIONS: Final = 768
"""Length of every embedding vector. Fixed by the database column, so every
embedder must produce vectors of exactly this length."""


@dataclass(frozen=True, slots=True)
class SourceDocument:
    """A whole document, before it is cut into chunks."""

    key: str
    """Stable name of the document; storing it again replaces the old version."""
    title: str
    source_url: str
    retrieved_on: date
    text: str
    """Markdown. A line starting with "## " begins a section."""
    city_id: str | None = None
    is_sample: bool = False
    can_quote: bool = True
    """Whether the text may be shown word for word. False for official pages
    whose licence does not say so: they are searched, answered from and linked,
    but their passages are not reproduced."""


@dataclass(frozen=True, slots=True)
class DocChunk:
    """One passage of an official document, small enough to embed and to cite."""

    document_key: str
    chunk_index: int
    title: str
    source_url: str
    content: str
    retrieved_on: date
    city_id: str | None = None
    """None when the document applies to every city."""
    is_sample: bool = False
    can_quote: bool = True


@dataclass(frozen=True, slots=True)
class EmbeddedChunk:
    chunk: DocChunk
    embedding: tuple[float, ...]
    model: str

    def __post_init__(self) -> None:
        if len(self.embedding) != EMBEDDING_DIMENSIONS:
            raise ValueError(
                f"embedding has {len(self.embedding)} dimensions, expected {EMBEDDING_DIMENSIONS}"
            )


@dataclass(frozen=True, slots=True)
class RetrievedChunk:
    chunk: DocChunk
    similarity: float
    """Cosine similarity to the query: 1 means the same direction, 0 unrelated."""

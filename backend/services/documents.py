"""Preparing documents for retrieval: cutting them into chunks and storing them.

Runs offline. Nothing here is called while a student waits for an answer.
"""

from collections.abc import Iterator, Sequence
from dataclasses import dataclass

from domain.document import DocChunk, EmbeddedChunk, SourceDocument
from ports.embedder import Embedder
from ports.vector_store import VectorStore

MAX_CHUNK_WORDS = 180
"""A chunk is one section of a document, or part of a long one. Small chunks
keep a citation precise and let the search match one topic at a time."""

_HEADING = "## "


def chunk_document(document: SourceDocument, max_words: int = MAX_CHUNK_WORDS) -> list[DocChunk]:
    """Cut a document into chunks, one per section.

    A section longer than `max_words` is cut at paragraph ends. Every chunk
    starts with the document title and its section heading, so it still makes
    sense, and can still be found, when read on its own.
    """
    chunks: list[DocChunk] = []
    for heading, paragraphs in _sections(document.text):
        label = f"{document.title}: {heading}" if heading else document.title
        for body in _groups(paragraphs, max_words):
            chunks.append(
                DocChunk(
                    document_key=document.key,
                    chunk_index=len(chunks),
                    title=document.title,
                    source_url=document.source_url,
                    content=f"{label}\n{body}",
                    retrieved_on=document.retrieved_on,
                    city_id=document.city_id,
                    is_sample=document.is_sample,
                    can_quote=document.can_quote,
                )
            )
    return chunks


def _sections(text: str) -> Iterator[tuple[str | None, list[str]]]:
    """(heading, paragraphs) for each section. Text before the first heading
    is a section without a heading."""
    heading: str | None = None
    lines: list[str] = []
    for line in [*text.splitlines(), _HEADING]:
        if not line.startswith(_HEADING):
            lines.append(line)
            continue
        paragraphs = [p.strip() for p in "\n".join(lines).split("\n\n") if p.strip()]
        if paragraphs:
            yield heading, paragraphs
        heading, lines = line.removeprefix(_HEADING).strip(), []


def _groups(paragraphs: Sequence[str], max_words: int) -> Iterator[str]:
    """Join paragraphs into pieces of at most `max_words` words. A single
    paragraph longer than that is cut by word count."""
    current: list[str] = []
    count = 0
    for paragraph in paragraphs:
        words = paragraph.split()
        if current and count + len(words) > max_words:
            yield "\n\n".join(current)
            current, count = [], 0
        if len(words) > max_words:
            for start in range(0, len(words), max_words):
                yield " ".join(words[start : start + max_words])
            continue
        current.append(paragraph)
        count += len(words)
    if current:
        yield "\n\n".join(current)


@dataclass(frozen=True, slots=True)
class IngestionReport:
    documents: int
    chunks: int
    removed: tuple[str, ...]
    """Keys of stored documents that were no longer supplied and were deleted."""
    model: str


class DocumentIngestionService:
    def __init__(self, embedder: Embedder, store: VectorStore) -> None:
        self._embedder = embedder
        self._store = store

    def sync(self, documents: Sequence[SourceDocument]) -> IngestionReport:
        """Make the store hold exactly these documents.

        Every chunk is embedded before the store is touched, so a model failure
        (EmbedderUnavailableError) leaves the stored documents as they were.
        """
        keys = [document.key for document in documents]
        duplicates = sorted({key for key in keys if keys.count(key) > 1})
        if duplicates:
            raise ValueError(f"document keys are used more than once: {', '.join(duplicates)}")

        chunks = [chunk for document in documents for chunk in chunk_document(document)]
        vectors = self._embedder.embed_documents([chunk.content for chunk in chunks])

        removed = sorted(self._store.document_keys() - set(keys))
        # Deleting first also clears chunks left over from a longer old version.
        for key in [*removed, *keys]:
            self._store.delete_document(key)
        model = self._embedder.model_name
        self._store.add(
            [
                EmbeddedChunk(chunk=chunk, embedding=vector, model=model)
                for chunk, vector in zip(chunks, vectors, strict=True)
            ]
        )
        return IngestionReport(len(documents), len(chunks), tuple(removed), model)

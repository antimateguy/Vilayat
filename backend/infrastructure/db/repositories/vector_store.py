"""Document chunks and similarity search in PostgreSQL with pgvector."""

from collections.abc import Sequence, Set
from typing import Any

from sqlalchemy import Float, Row, delete, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from domain.document import DocChunk, EmbeddedChunk, RetrievedChunk
from infrastructure.db.models import DocChunkRow
from ports.vector_store import VectorStore


class PgVectorStore(VectorStore):
    """Keeps the vectors next to the rest of the data, so no separate vector
    database has to be run or kept in sync."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, chunks: Sequence[EmbeddedChunk]) -> None:
        if not chunks:
            return
        statement = insert(DocChunkRow).values(
            [
                {
                    "document_key": item.chunk.document_key,
                    "chunk_index": item.chunk.chunk_index,
                    "title": item.chunk.title,
                    "source_url": item.chunk.source_url,
                    "content": item.chunk.content,
                    "city_id": item.chunk.city_id,
                    "retrieved_on": item.chunk.retrieved_on,
                    "is_sample": item.chunk.is_sample,
                    "can_quote": item.chunk.can_quote,
                    "embedding": list(item.embedding),
                    "embedding_model": item.model,
                }
                for item in chunks
            ]
        )
        # Re-ingesting a document replaces its chunks instead of duplicating them.
        key = ("document_key", "chunk_index")
        replaced = {
            column.name: column for column in statement.excluded if column.name not in (*key, "id")
        }
        self._session.execute(statement.on_conflict_do_update(index_elements=key, set_=replaced))

    def search(
        self, embedding: Sequence[float], limit: int, model: str, city_id: str | None = None
    ) -> Sequence[RetrievedChunk]:
        # "<=>" is pgvector's cosine distance: 0 for the same direction, 1 for unrelated.
        # Without return_type the result would be read back as a vector, not a number.
        distance = DocChunkRow.embedding.op("<=>", return_type=Float)(list(embedding))
        statement = (
            select(
                DocChunkRow.document_key,
                DocChunkRow.chunk_index,
                DocChunkRow.title,
                DocChunkRow.source_url,
                DocChunkRow.content,
                DocChunkRow.retrieved_on,
                DocChunkRow.city_id,
                DocChunkRow.is_sample,
                DocChunkRow.can_quote,
                distance,
            )
            .where(DocChunkRow.embedding_model == model)
            .order_by(distance)
            .limit(limit)
        )
        if city_id is not None:
            statement = statement.where(
                or_(DocChunkRow.city_id == city_id, DocChunkRow.city_id.is_(None))
            )
        return [_to_retrieved(row) for row in self._session.execute(statement)]

    def document_keys(self) -> Set[str]:
        return set(self._session.scalars(select(DocChunkRow.document_key).distinct()))

    def delete_document(self, document_key: str) -> None:
        self._session.execute(delete(DocChunkRow).where(DocChunkRow.document_key == document_key))


def _to_retrieved(row: Row[*tuple[Any, ...]]) -> RetrievedChunk:
    fields = tuple(row)
    return RetrievedChunk(chunk=DocChunk(*fields[:-1]), similarity=1 - fields[-1])

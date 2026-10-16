"""Ranking document sections for a question with any embedder.

The app searches in PostgreSQL. For the evaluation the same ranking is done in
memory, so that models whose vectors have a different length than the database
column can be compared too. The rule is the one the app uses: cosine
similarity, over the sections for the question's city and the general ones.
"""

import math
from collections.abc import Sequence

from domain.document import DocChunk
from evaluation.data import ChunkId
from ports.embedder import Embedder


def chunk_id(chunk: DocChunk) -> ChunkId:
    """A chunk's first line is "<document title>: <section heading>"."""
    heading = chunk.content.split("\n", 1)[0].removeprefix(chunk.title).removeprefix(":").strip()
    return chunk.document_key, heading


class SectionIndex:
    """Every section embedded once with one model, ready to be searched."""

    def __init__(self, embedder: Embedder, chunks: Sequence[DocChunk]) -> None:
        self._embedder = embedder
        self._chunks = list(chunks)
        self._vectors = embedder.embed_documents([chunk.content for chunk in chunks])

    def search(self, question: str, city: str) -> list[tuple[ChunkId, float]]:
        """Every section the question's city may use, most similar first."""
        query = self._embedder.embed_query(question)
        scored = [
            (chunk_id(chunk), cosine(query, vector))
            for chunk, vector in zip(self._chunks, self._vectors, strict=True)
            if chunk.city_id in (None, city)
        ]
        return sorted(scored, key=lambda item: -item[1])


def cosine(a: Sequence[float], b: Sequence[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    lengths = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return dot / lengths if lengths else 0.0

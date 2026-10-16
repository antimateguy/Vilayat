"""An open embedding model run on this machine, behind the Embedder port.

For the comparison in the evaluation only. It needs the "eval" dependency
group (sentence-transformers), which the app and its Docker image never install.
"""

from collections.abc import Sequence
from typing import Any

from ports.embedder import Embedder


class SentenceTransformerEmbedder(Embedder):
    """Adapter for a sentence-transformers model.

    Some models expect a marker in front of each text that says whether it is a
    question or a passage (the E5 family: "query: " and "passage: "). Its
    vectors are as long as the model makes them, which may not be the length of
    the database column, so this adapter is for in-memory comparison.
    """

    def __init__(self, model_name: str, query_prefix: str = "", passage_prefix: str = "") -> None:
        # Imported here so that the rest of the package works without the
        # evaluation dependencies installed.
        from sentence_transformers import SentenceTransformer

        self._model_name = model_name
        self._model: Any = SentenceTransformer(model_name)
        self._query_prefix = query_prefix
        self._passage_prefix = passage_prefix

    @property
    def model_name(self) -> str:
        return self._model_name

    def embed_documents(self, texts: Sequence[str]) -> list[tuple[float, ...]]:
        return self._encode([self._passage_prefix + text for text in texts])

    def embed_query(self, text: str) -> tuple[float, ...]:
        return self._encode([self._query_prefix + text])[0]

    def _encode(self, texts: list[str]) -> list[tuple[float, ...]]:
        vectors = self._model.encode(texts, normalize_embeddings=True)
        return [tuple(float(value) for value in vector) for vector in vectors]

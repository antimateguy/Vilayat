"""Load the documents in data/documents into the vector store.

    uv run python -m jobs.ingest_documents

Each document is cut into chunks, each chunk is embedded, and the store is made
to hold exactly the documents in the folder: changed ones are replaced, ones
that were deleted from the folder are removed. Needs GEMINI_API_KEY.

A document is a Markdown file that starts with a header:

    ---
    title: Registering your address in Berlin
    source_url: https://service.berlin.de/dienstleistung/120686/
    retrieved_on: 2026-10-06
    city: berlin
    is_sample: true
    ---
    ## Deadline and place
    ...

`city` is empty for a document that applies to every city. `is_sample` is true
for a note that is not the official text. See data/documents/README.md.
"""

import logging
import sys
from collections.abc import Set
from datetime import date
from pathlib import Path

from sqlalchemy.orm import Session

from domain.document import SourceDocument
from infrastructure.ai import create_embedder, embedding_budget
from infrastructure.db.repositories.catalog import PostgresCatalogRepository
from infrastructure.db.repositories.vector_store import PgVectorStore
from infrastructure.settings import Settings
from jobs.runtime import configure_logging, job_session, job_sessions
from ports.embedder import Embedder, EmbedderUnavailableError
from services.documents import DocumentIngestionService, IngestionReport

logger = logging.getLogger("jobs.ingest_documents")

DOCUMENTS_DIR = Path(__file__).resolve().parents[1] / "data" / "documents"
REQUIRED_KEYS = {"title", "source_url", "retrieved_on"}
OPTIONAL_KEYS = {"city", "is_sample", "can_quote"}
_FENCE = "---"


def read_document(path: Path) -> SourceDocument:
    """Parse one file. Raises ValueError, naming the file, for a bad header."""
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != _FENCE or _FENCE not in [x.strip() for x in lines[1:]]:
        raise ValueError(f"{path.name}: must start with a header between two '---' lines")
    end = [line.strip() for line in lines[1:]].index(_FENCE) + 1

    header: dict[str, str] = {}
    for line in lines[1:end]:
        if not line.strip():
            continue
        key, separator, value = line.partition(":")
        if not separator:
            raise ValueError(f"{path.name}: header line is not 'key: value': {line!r}")
        header[key.strip()] = value.strip()

    unknown = set(header) - REQUIRED_KEYS - OPTIONAL_KEYS
    missing = {key for key in REQUIRED_KEYS if not header.get(key)}
    if unknown or missing:
        problems = [f"unknown keys {sorted(unknown)}"] if unknown else []
        problems += [f"missing {sorted(missing)}"] if missing else []
        raise ValueError(f"{path.name}: {' and '.join(problems)}")
    for flag in ("is_sample", "can_quote"):
        if header.get(flag, "true" if flag == "can_quote" else "false") not in ("true", "false"):
            raise ValueError(f"{path.name}: {flag} must be true or false")
    if not header["source_url"].startswith("https://"):
        raise ValueError(f"{path.name}: source_url must be an https:// address")
    try:
        retrieved_on = date.fromisoformat(header["retrieved_on"])
    except ValueError as error:
        raise ValueError(f"{path.name}: retrieved_on must be a date like 2026-10-06") from error

    text = "\n".join(lines[end + 1 :]).strip()
    if not text:
        raise ValueError(f"{path.name}: the document has no text")
    return SourceDocument(
        key=path.stem,
        title=header["title"],
        source_url=header["source_url"],
        retrieved_on=retrieved_on,
        text=text,
        city_id=header.get("city") or None,
        is_sample=header.get("is_sample") == "true",
        can_quote=header.get("can_quote", "true") == "true",
    )


def read_documents(directory: Path, known_city_ids: Set[str]) -> list[SourceDocument]:
    """Every document of a folder and of its fetched/ subfolder (written by
    jobs.fetch_documents), in file-name order. README.md is not a document."""
    documents = [
        read_document(path)
        for path in sorted([*directory.glob("*.md"), *directory.glob("fetched/*.md")])
        if path.name.lower() != "readme.md"
    ]
    for document in documents:
        if document.city_id is not None and document.city_id not in known_city_ids:
            raise ValueError(f"{document.key}.md: no city with id {document.city_id!r}")
    return documents


def run(session: Session, embedder: Embedder, directory: Path = DOCUMENTS_DIR) -> IngestionReport:
    known = {city.id for city in PostgresCatalogRepository(session).list_cities()}
    documents = read_documents(directory, known)
    return DocumentIngestionService(embedder, PgVectorStore(session)).sync(documents)


def main() -> int:
    configure_logging()
    settings = Settings()
    if not settings.ai_enabled:
        logger.error("GEMINI_API_KEY is not set in .env; documents cannot be embedded without it")
        return 1
    try:
        with job_sessions() as sessions, job_session() as session:
            embedder = create_embedder(settings, embedding_budget(settings, sessions), for_job=True)
            report = run(session, embedder)
    except (ValueError, EmbedderUnavailableError) as error:
        logger.error("nothing was changed: %s", error)
        return 1
    logger.info(
        "%d documents stored as %d chunks, embedded with %s",
        report.documents,
        report.chunks,
        report.model,
    )
    if report.removed:
        logger.info("removed documents no longer in the folder: %s", ", ".join(report.removed))
    return 0


if __name__ == "__main__":
    sys.exit(main())

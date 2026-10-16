"""Cutting documents into chunks, reading document files, and filling the store."""

from datetime import date
from pathlib import Path

import pytest

from domain.document import SourceDocument
from infrastructure.fakes.ai import InMemoryVectorStore, WordEmbedder
from jobs.ingest_documents import DOCUMENTS_DIR, read_document, read_documents
from ports.embedder import EmbedderUnavailableError
from services.documents import MAX_CHUNK_WORDS, DocumentIngestionService, chunk_document

HEADER = """\
---
title: Registering your address
source_url: https://example.org/registration
retrieved_on: 2026-10-06
city: testville
is_sample: true
---
"""
BODY = """\
## Deadline

Register within 14 days.

## Documents

Bring your passport.

Bring the landlord's confirmation.
"""


def document(text: str = BODY, key: str = "registration", **changes: object) -> SourceDocument:
    fields: dict[str, object] = {
        "key": key,
        "title": "Registering your address",
        "source_url": "https://example.org/registration",
        "retrieved_on": date(2026, 10, 6),
        "text": text,
        "city_id": "testville",
        "is_sample": True,
    }
    return SourceDocument(**(fields | changes))  # type: ignore[arg-type]


# --- Chunking -------------------------------------------------------------------


def test_each_section_becomes_one_chunk_that_names_its_document_and_heading() -> None:
    first, second = chunk_document(document())

    assert first.content == "Registering your address: Deadline\nRegister within 14 days."
    assert second.content == (
        "Registering your address: Documents\n"
        "Bring your passport.\n\nBring the landlord's confirmation."
    )
    assert [first.chunk_index, second.chunk_index] == [0, 1]


def test_a_chunk_carries_the_documents_source_date_city_and_sample_flag() -> None:
    chunk = chunk_document(document())[0]

    assert (chunk.document_key, chunk.title) == ("registration", "Registering your address")
    assert chunk.source_url == "https://example.org/registration"
    assert (chunk.retrieved_on, chunk.city_id, chunk.is_sample) == (
        date(2026, 10, 6),
        "testville",
        True,
    )


def test_text_before_the_first_heading_is_a_chunk_without_a_heading() -> None:
    chunks = chunk_document(document("An introduction.\n\n## Deadline\n\nWithin 14 days."))

    assert [chunk.content for chunk in chunks] == [
        "Registering your address\nAn introduction.",
        "Registering your address: Deadline\nWithin 14 days.",
    ]


def test_a_long_section_is_cut_at_paragraph_ends() -> None:
    paragraphs = [" ".join([f"word{n}"] * 4) for n in range(5)]
    text = "## Rules\n\n" + "\n\n".join(paragraphs)

    chunks = chunk_document(document(text), max_words=10)

    assert [chunk.content.split("\n", 1)[1] for chunk in chunks] == [
        f"{paragraphs[0]}\n\n{paragraphs[1]}",
        f"{paragraphs[2]}\n\n{paragraphs[3]}",
        paragraphs[4],
    ]
    assert all(chunk.content.startswith("Registering your address: Rules\n") for chunk in chunks)
    assert [chunk.chunk_index for chunk in chunks] == [0, 1, 2]


def test_one_paragraph_that_is_too_long_is_cut_by_word_count() -> None:
    text = "## Rules\n\n" + " ".join(f"w{n}" for n in range(25))

    bodies = [c.content.split("\n", 1)[1] for c in chunk_document(document(text), max_words=10)]

    assert [len(body.split()) for body in bodies] == [10, 10, 5]
    assert bodies[2] == "w20 w21 w22 w23 w24"


def test_empty_sections_and_empty_documents_give_no_chunks() -> None:
    assert chunk_document(document("## Empty\n\n\n## Also empty\n")) == []
    assert chunk_document(document("")) == []


# --- Filling the store ---------------------------------------------------------------


def test_sync_stores_every_chunk_with_its_vector_and_model() -> None:
    store = InMemoryVectorStore()

    report = DocumentIngestionService(WordEmbedder("toy-model"), store).sync([document()])

    assert (report.documents, report.chunks, report.removed, report.model) == (
        1,
        2,
        (),
        "toy-model",
    )
    assert [item.chunk.chunk_index for item in store.stored()] == [0, 1]
    assert {item.model for item in store.stored()} == {"toy-model"}


def test_sync_replaces_changed_documents_and_removes_missing_ones() -> None:
    store = InMemoryVectorStore()
    service = DocumentIngestionService(WordEmbedder(), store)
    service.sync([document(), document(key="visa")])

    report = service.sync([document("## Deadline\n\nNow within 7 days.")])

    assert report.removed == ("visa",)
    assert [item.chunk.content for item in store.stored()] == [
        "Registering your address: Deadline\nNow within 7 days."
    ]


def test_sync_twice_changes_nothing() -> None:
    store = InMemoryVectorStore()
    service = DocumentIngestionService(WordEmbedder(), store)

    service.sync([document()])
    before = store.stored()
    service.sync([document()])

    assert store.stored() == before


def test_a_model_failure_leaves_the_store_as_it_was() -> None:
    store = InMemoryVectorStore()
    DocumentIngestionService(WordEmbedder(), store).sync([document()])
    before = store.stored()

    with pytest.raises(EmbedderUnavailableError):
        DocumentIngestionService(WordEmbedder(available=False), store).sync(
            [document("## New\n\nNew text.")]
        )

    assert store.stored() == before


def test_two_documents_with_the_same_key_are_refused() -> None:
    service = DocumentIngestionService(WordEmbedder(), InMemoryVectorStore())

    with pytest.raises(ValueError, match="more than once: registration"):
        service.sync([document(), document()])


# --- Reading document files ------------------------------------------------------------


def write(folder: Path, name: str, content: str) -> Path:
    path = folder / name
    path.write_text(content, encoding="utf-8")
    return path


def test_a_file_is_read_into_a_document(tmp_path: Path) -> None:
    path = write(tmp_path, "registration.md", HEADER + BODY)

    assert read_document(path) == document(BODY.strip())


def test_city_and_sample_flag_are_optional(tmp_path: Path) -> None:
    header = HEADER.replace("city: testville\n", "city:\n").replace("is_sample: true\n", "")

    found = read_document(write(tmp_path, "general.md", header + BODY))

    assert (found.city_id, found.is_sample) == (None, False)


@pytest.mark.parametrize(
    ("content", "problem"),
    [
        (BODY, "must start with a header"),
        ("---\ntitle: No end\n" + BODY, "must start with a header"),
        (HEADER.replace("title: Registering your address\n", "") + BODY, r"missing \['title'\]"),
        (HEADER.replace("title:", "titel:") + BODY, r"unknown keys \['titel'\] and missing"),
        (HEADER.replace("2026-10-06", "6 October") + BODY, "retrieved_on must be a date"),
        (HEADER.replace("https://", "ftp://") + BODY, "source_url must be an https"),
        (HEADER.replace("is_sample: true", "is_sample: yes") + BODY, "is_sample must be true"),
        (
            HEADER.replace("city: testville", "just some words") + BODY,
            "header line is not 'key: value'",
        ),
        (HEADER, "the document has no text"),
    ],
    ids=[
        "no header",
        "header not closed",
        "title missing",
        "misspelt key",
        "bad date",
        "not https",
        "bad flag",
        "not a key and value",
        "no text",
    ],
)
def test_a_bad_file_is_refused_with_its_name_and_the_problem(
    tmp_path: Path, content: str, problem: str
) -> None:
    path = write(tmp_path, "broken.md", content)

    with pytest.raises(ValueError, match=f"broken.md: {problem}"):
        read_document(path)


def test_a_folder_is_read_in_name_order_without_its_readme(tmp_path: Path) -> None:
    write(tmp_path, "b-second.md", HEADER + BODY)
    write(tmp_path, "a-first.md", HEADER + BODY)
    write(tmp_path, "README.md", "# Not a document")
    write(tmp_path, "notes.txt", "Not a document either")

    found = read_documents(tmp_path, {"testville"})

    assert [item.key for item in found] == ["a-first", "b-second"]


def test_a_document_for_a_city_that_does_not_exist_is_refused(tmp_path: Path) -> None:
    write(tmp_path, "registration.md", HEADER + BODY)

    with pytest.raises(ValueError, match=r"registration\.md: no city with id 'testville'"):
        read_documents(tmp_path, {"berlin", "munich"})


# --- The sample notes shipped with the project --------------------------------------------


def test_every_shipped_document_is_readable_labelled_as_sample_and_small_enough() -> None:
    # The committed notes only: fetched/ holds official pages, present only
    # where jobs.fetch_documents has run.
    documents = [
        item
        for item in read_documents(DOCUMENTS_DIR, {"berlin", "munich"})
        if (DOCUMENTS_DIR / f"{item.key}.md").exists()
    ]

    assert len(documents) >= 8
    assert all(item.is_sample for item in documents), "these notes are not official texts"
    assert {item.city_id for item in documents} == {None, "berlin", "munich"}
    for item in documents:
        chunks = chunk_document(item)
        assert len(chunks) >= 2, item.key
        for chunk in chunks:
            assert len(chunk.content.split()) <= MAX_CHUNK_WORDS + 15, item.key
            # The heading line plus the text: no chunk is a bare heading.
            assert len(chunk.content.split("\n", 1)[1].split()) >= 10, item.key


def test_fetched_pages_are_read_with_the_notes_and_keep_their_quote_flag(tmp_path: Path) -> None:
    def document(title: str, extra: str) -> str:
        return "\n".join(
            [
                "---",
                f"title: {title}",
                f"source_url: https://example.org/{title.lower()}",
                "retrieved_on: 2026-10-16",
                extra,
                "---",
                "## Part",
                f"The text of {title}.",
            ]
        )

    (tmp_path / "fetched").mkdir()
    (tmp_path / "note.md").write_text(document("Note", "is_sample: true"), encoding="utf-8")
    (tmp_path / "fetched" / "law.md").write_text(
        document("Law", "can_quote: false"), encoding="utf-8"
    )

    documents = read_documents(tmp_path, set())

    assert [(item.key, item.is_sample, item.can_quote) for item in documents] == [
        ("law", False, False),
        ("note", True, True),
    ]

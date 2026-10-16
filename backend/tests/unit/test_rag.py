"""Question answering from documents: a toy embedder, an in-memory store, a scripted model."""

from datetime import date
from typing import Any

import pytest

from domain.answer import Answer, AnswerStatus
from domain.document import DocChunk, EmbeddedChunk
from infrastructure.fakes.ai import InMemoryVectorStore, ScriptedLLMClient, WordEmbedder
from ports.embedder import EmbedderUnavailableError
from ports.llm import LLMUnavailableError
from services.grounding import numbers_in, unsupported_numbers
from services.rag import ANSWER_SCHEMA, NO_EVIDENCE_TEXT, SOURCES_ONLY_TEXT, RagService

MODEL = "word-embedder"
MIN_SIMILARITY = 0.3
QUESTION = "within how many days must I register my address"

REGISTRATION = "Registering your address: Deadline\nYou must register your address within 14 days."
FUNDS = "Proof of funds: Amount\nYou must prove 11,904 EUR per year, which is 992 EUR per month."
PAPERS = (
    "Registering your address: Documents\n"
    "To register your address bring your passport within the appointment."
)
ELSEWHERE = "Registering your address: Deadline\nIn Elsewhere register your address within 7 days."


def chunk(key: str, content: str, city_id: str | None = None, index: int = 0) -> DocChunk:
    return DocChunk(
        document_key=key,
        chunk_index=index,
        title=content.split(":")[0],
        source_url=f"https://example.org/{key}",
        content=content,
        retrieved_on=date(2026, 10, 6),
        city_id=city_id,
        is_sample=True,
    )


def store_with(*chunks: DocChunk, model: str = MODEL) -> InMemoryVectorStore:
    store = InMemoryVectorStore()
    embedder = WordEmbedder(model)
    vectors = embedder.embed_documents([item.content for item in chunks])
    store.add([EmbeddedChunk(c, v, model) for c, v in zip(chunks, vectors, strict=True)])
    return store


def library() -> InMemoryVectorStore:
    return store_with(
        chunk("registration", REGISTRATION),
        chunk("registration", PAPERS, index=1),
        chunk("funds", FUNDS),
    )


def written(answer: str, answerable: bool = True) -> dict[str, Any]:
    return {"answerable": answerable, "answer": answer}


def ask(
    reply: Any,
    question: str = QUESTION,
    *,
    store: InMemoryVectorStore | None = None,
    city_id: str | None = None,
    top_k: int = 4,
) -> tuple[Answer, ScriptedLLMClient]:
    llm = ScriptedLLMClient(reply)
    service = RagService(
        WordEmbedder(), store or library(), llm, min_similarity=MIN_SIMILARITY, top_k=top_k
    )
    return service.ask(question, city_id), llm


# --- An answer with citations ------------------------------------------------------


def test_an_answer_cites_the_passage_it_was_written_from() -> None:
    answer, llm = ask(written("You must register within 14 days [1]."))

    assert answer.status is AnswerStatus.ANSWERED
    assert answer.text == "You must register within 14 days [1]."
    (citation,) = answer.citations
    assert (citation.number, citation.chunk.content) == (1, REGISTRATION)
    assert citation.similarity > MIN_SIMILARITY
    assert llm.schemas == [ANSWER_SCHEMA]


def test_the_model_sees_numbered_passages_and_the_quoted_question() -> None:
    _, llm = ask(written("Within 14 days [1]."))

    (prompt,) = llm.prompts
    assert f"[1] (Registering your address)\n{REGISTRATION}" in prompt
    assert f"[2] (Registering your address)\n{PAPERS}" in prompt
    assert "11,904" not in prompt, "the passage about funds is not close enough to be sent"
    assert prompt.endswith(f'Question: """{QUESTION}"""')


def test_only_the_passages_the_answer_cites_are_returned_with_their_numbers() -> None:
    answer, _ = ask(written("Bring your passport [2]."))

    assert [(c.number, c.chunk.content) for c in answer.citations] == [(2, PAPERS)]


def test_a_figure_may_be_written_with_or_without_a_thousands_separator() -> None:
    answer, _ = ask(
        written("You must prove 11904 EUR per year [1]."),
        "how many EUR per year must I prove",
    )

    assert answer.status is AnswerStatus.ANSWERED


# --- No evidence -----------------------------------------------------------------------


def test_a_question_the_documents_do_not_cover_gets_the_fixed_answer_without_a_model_call() -> None:
    answer, llm = ask(written("Zebras play the violin [1]."), "zebra quantum violin")

    assert answer == Answer(AnswerStatus.NO_EVIDENCE, NO_EVIDENCE_TEXT, ())
    assert llm.prompts == []


def test_the_model_itself_may_say_the_passages_do_not_answer() -> None:
    for reply in (written("", answerable=False), written("  "), written("x [1]", answerable=False)):
        answer, _ = ask(reply)

        assert answer == Answer(AnswerStatus.NO_EVIDENCE, NO_EVIDENCE_TEXT, ())


def test_documents_about_another_city_are_not_evidence() -> None:
    store = store_with(chunk("elsewhere", ELSEWHERE, city_id="elsewhere"))

    here, here_llm = ask(written("Within 7 days [1]."), store=store, city_id="testville")
    there, there_llm = ask(written("Within 7 days [1]."), store=store, city_id="elsewhere")

    assert (here.status, here_llm.prompts) == (AnswerStatus.NO_EVIDENCE, [])
    assert there.status is AnswerStatus.ANSWERED
    assert "[1] (Registering your address, applies to elsewhere)" in there_llm.prompts[0]


def test_passages_embedded_with_another_model_are_not_compared() -> None:
    answer, llm = ask(
        written("Within 14 days [1]."), store=store_with(chunk("r", REGISTRATION), model="older")
    )

    assert (answer.status, llm.prompts) == (AnswerStatus.NO_EVIDENCE, [])


# --- An answer that fails a check is withheld ---------------------------------------


@pytest.mark.parametrize(
    "reply",
    [
        LLMUnavailableError("quota used up"),
        {"answer": "Within 14 days [1]."},
        written("You must register within 14 days."),
        written("You must register within 14 days [7]."),
        written("You must register within 14 days [1] or pay a fine [9]."),
        written("You must register within 7 days [1]."),
        written("You must register within 14 days and prove 992 EUR [1]."),
    ],
    ids=[
        "model unavailable",
        "reply does not fit the form",
        "no citation",
        "cites a passage that does not exist",
        "one of two citations does not exist",
        "a figure that is in no passage",
        "a figure from a passage it does not cite",
    ],
)
def test_instead_of_an_unchecked_answer_the_passages_are_shown(reply: Any) -> None:
    answer, _ = ask(reply)

    assert answer.status is AnswerStatus.SOURCES_ONLY
    assert answer.text == SOURCES_ONLY_TEXT
    assert [(c.number, c.chunk.content) for c in answer.citations] == [
        (1, REGISTRATION),
        (2, PAPERS),
    ]


def test_without_an_embedder_there_is_nothing_to_search_with() -> None:
    service = RagService(
        WordEmbedder(available=False), library(), ScriptedLLMClient(), MIN_SIMILARITY
    )

    with pytest.raises(EmbedderUnavailableError):
        service.ask(QUESTION)


def test_at_most_top_k_passages_are_used() -> None:
    answer, _ = ask(LLMUnavailableError("down"), top_k=1)

    assert [c.chunk.content for c in answer.citations] == [REGISTRATION]


# --- The figure check --------------------------------------------------------------------


def test_figures_are_read_in_one_spelling() -> None:
    assert numbers_in("Pay 1,500 EUR, 18.36 EUR or 18.360 EUR within 14 days.") == {
        "1500",
        "18.36",
        "14",
    }
    assert numbers_in("Rooms 1, 2 and 3; 11,904 EUR; 2.0 hours") == {"1", "2", "3", "11904"}
    assert numbers_in("No figures here.") == set()


def test_a_figure_counts_as_supported_if_any_source_has_it() -> None:
    sources = ["Within 14 days.", "The fee is 18.36 EUR."]

    assert unsupported_numbers("Pay 18.36 EUR within 14 days.", sources) == set()
    assert unsupported_numbers("Pay 20 EUR within 7 days.", sources) == {"20", "7"}


def test_the_log_says_why_an_answer_was_withheld(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level("INFO", logger="services.rag"):
        ask(written("You must register within 7 days [1]."))
        ask(written("You must register within 14 days."))
        ask(LLMUnavailableError("quota used up"))

    assert [record.getMessage() for record in caplog.records] == [
        "answer withheld: figures not in the cited passages: 7",
        "answer withheld: the answer cites no passage, or one that does not exist",
        "answer withheld: no usable reply from the model (quota used up)",
    ]

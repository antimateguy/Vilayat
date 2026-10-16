"""The evaluation's measures and labels. No model and no network."""

from datetime import date
from pathlib import Path

import pytest

from cities.registry import discover_cities
from domain.city import Campus, University
from domain.destination import Destination, DestinationKind
from domain.document import DocChunk
from domain.geo import Coordinate
from domain.intent import SearchIntent
from evaluation.data import ExpectedIntent, load_questions, load_sentences
from evaluation.intent import FIELDS, field_matches
from evaluation.metrics import gate_scores, hit, reciprocal_rank, retrieval_scores, share
from evaluation.report import render
from evaluation.retrieval import SectionIndex, chunk_id, cosine
from infrastructure.fakes.ai import WordEmbedder
from jobs.ingest_documents import DOCUMENTS_DIR, read_documents
from services.documents import chunk_document

HERE = Coordinate(48.1, 11.5)
CITY_IDS = {city.id for city in discover_cities().all()}


# --- Measures -------------------------------------------------------------------


def test_reciprocal_rank_is_one_over_the_position_of_the_first_right_item() -> None:
    assert reciprocal_rank(["a", "b", "c"], {"a"}) == 1
    assert reciprocal_rank(["a", "b", "c"], {"c", "b"}) == 0.5
    assert reciprocal_rank(["a", "b", "c"], {"z"}) == 0
    assert reciprocal_rank([], {"a"}) == 0


def test_a_hit_means_a_right_item_among_the_first_k() -> None:
    assert hit(["a", "b", "c"], {"b"}, k=1) is False
    assert hit(["a", "b", "c"], {"b"}, k=2) is True


def test_retrieval_scores_average_over_the_questions() -> None:
    scores = retrieval_scores(
        [
            (["a", "b", "c"], {"a"}),  # first
            (["a", "b", "c"], {"c"}),  # third
            (["a", "b", "c", "d"], {"d"}),  # fourth: a miss at 3
            (["a", "b"], {"z"}),  # never
        ]
    )

    assert scores.questions == 4
    assert scores.hit_at_1 == 0.25
    assert scores.hit_at_3 == 0.5
    assert scores.mrr == pytest.approx((1 + 1 / 3 + 1 / 4 + 0) / 4)


def test_a_threshold_is_scored_on_both_kinds_of_question() -> None:
    scores = gate_scores(answerable=[0.9, 0.8, 0.6], unanswerable=[0.7, 0.5], threshold=0.65)

    assert scores.answerable_kept == pytest.approx(2 / 3)
    assert scores.unanswerable_stopped == 0.5
    assert scores.accuracy == pytest.approx(3 / 5)


def test_a_score_equal_to_the_threshold_passes_as_in_the_app() -> None:
    assert gate_scores([0.7], [0.7], threshold=0.7).answerable_kept == 1
    assert gate_scores([0.7], [0.7], threshold=0.7).unanswerable_stopped == 0


def test_empty_input_is_refused_rather_than_scored_as_zero() -> None:
    with pytest.raises(ValueError):
        retrieval_scores([])
    with pytest.raises(ValueError):
        gate_scores([], [0.5], 0.6)
    with pytest.raises(ValueError):
        share([])
    assert share([True, False, True, True]) == 0.75


# --- Ranking sections ----------------------------------------------------------------


def chunk(key: str, content: str, city_id: str | None = None) -> DocChunk:
    return DocChunk(
        key, 0, content.split(":")[0], "https://example.org", content, date(2026, 1, 1), city_id
    )


def test_sections_are_ranked_by_similarity_within_the_questions_city() -> None:
    index = SectionIndex(
        WordEmbedder(),
        [
            chunk("registration", "Registering: Deadline\nRegister your address within 14 days."),
            chunk("fee", "Broadcasting fee: Amount\nThe fee is 18.36 EUR per month."),
            chunk(
                "elsewhere", "Registering: Deadline\nRegister your address within 7 days.", "other"
            ),
        ],
    )

    ranked = index.search("when must I register my address", "here")

    assert [found for found, _ in ranked] == [("registration", "Deadline"), ("fee", "Amount")]
    assert ranked[0][1] > ranked[1][1]


def test_a_section_is_identified_by_document_and_heading() -> None:
    assert chunk_id(chunk("visa", "Residence permit: Fee and validity\nUp to 100 EUR.")) == (
        "visa",
        "Fee and validity",
    )
    assert cosine([1.0, 0.0], [0.0, 1.0]) == 0
    assert cosine([0.0, 0.0], [1.0, 0.0]) == 0


# --- Comparing a parsed sentence with its label -----------------------------------


def test_a_sentence_read_exactly_right_matches_in_every_field() -> None:
    found = SearchIntent(
        city_id="munich",
        university=University(5, "munich", "Technische Universität München", "TUM"),
        campus=Campus(8, 5, "City Campus", HERE, 100),
        max_rent_eur=700,
        employer=Destination(
            40, "munich", DestinationKind.EMPLOYER, "BMW Group Headquarters", HERE
        ),
        weights={"commute": 0.35, "rent": 0.5, "amenities": 0.0, "job_access": 0.15},
    )
    expected = ExpectedIntent(
        city="munich",
        campus=("TUM", "City Campus"),
        employer="BMW Group Headquarters",
        max_rent_eur=700,
        important=("rent",),
        unimportant=("amenities",),
    )

    assert field_matches(found, expected) == dict.fromkeys(FIELDS, True)


def test_a_field_is_wrong_when_set_differently_or_set_without_reason() -> None:
    found = SearchIntent(max_rent_eur=750, max_commute_minutes=30)
    expected = ExpectedIntent(max_rent_eur=700)

    matches = field_matches(found, expected)

    assert matches["max_rent_eur"] is False
    assert matches["max_commute_minutes"] is False, "the sentence did not set a commute limit"
    assert matches["campus"] is True and matches["weights"] is True


# --- The labelled data shipped with the project -----------------------------------------


def test_every_labelled_question_points_at_sections_that_exist() -> None:
    documents = read_documents(DOCUMENTS_DIR, CITY_IDS)
    sections = {chunk_id(c): c.city_id for doc in documents for c in chunk_document(doc)}
    answerable, unanswerable = load_questions()

    assert len(answerable) >= 30 and len(unanswerable) >= 10
    for question in answerable:
        assert question.city in CITY_IDS, question.text
        assert question.relevant, question.text
        for section in question.relevant:
            assert section in sections, f"{question.text}: no section {section}"
            assert sections[section] in (None, question.city), (
                f"{question.text}: {section} belongs to another city"
            )
    assert all(not question.relevant and question.city in CITY_IDS for question in unanswerable)


def test_every_labelled_sentence_uses_known_cities_and_preferences() -> None:
    sentences = load_sentences()

    assert len(sentences) >= 25
    for item in sentences:
        assert item.current_city in CITY_IDS, item.text
        assert item.expected.city in (None, *CITY_IDS), item.text
        for name in (*item.expected.important, *item.expected.unimportant):
            assert name in ("commute", "rent", "amenities", "job_access"), item.text
    assert any(not field_matches(SearchIntent(), s.expected)["campus"] for s in sentences)
    assert any(all(field_matches(SearchIntent(), s.expected).values()) for s in sentences), (
        "some sentences should set nothing at all"
    )


# --- The written summary --------------------------------------------------------------------

RESULTS = {
    "run_on": "2026-10-06",
    "text_model": "text-model",
    "embedding_model_in_app": "embed-a",
    "material": {
        "documents": 10,
        "sections": 40,
        "answerable_questions": 4,
        "unanswerable_questions": 2,
        "sentences": 3,
    },
    "retrieval": {
        "embed-b": {"hit_at_1": 0.5, "hit_at_3": 0.75, "mrr": 0.625},
        "embed-a": {"hit_at_1": 1.0, "hit_at_3": 1.0, "mrr": 1.0},
    },
    "retrieval_german_only": {"questions": 1, "embed-a": 1.0, "embed-b": 0.0},
    "similarity_gate": {
        "model": "embed-a",
        "answerable_min": 0.71,
        "answerable_max": 0.86,
        "unanswerable_min": 0.55,
        "unanswerable_max": 0.75,
        "by_threshold": [
            {
                "threshold": 0.68,
                "answerable_kept": 1.0,
                "unanswerable_stopped": 0.5,
                "accuracy": 0.83,
            }
        ],
        "at_app_threshold": {
            "threshold": 0.68,
            "answerable_kept": 1.0,
            "unanswerable_stopped": 0.5,
            "accuracy": 0.83,
        },
    },
    "answers": {
        "answerable": {
            "questions": 4,
            "answered_with_right_source": 3,
            "answered_with_other_source": 0,
            "refused_as_no_evidence": 1,
            "passages_only": 0,
        },
        "unanswerable": {
            "questions": 2,
            "refused_as_no_evidence": 2,
            "answered_anyway": 0,
            "passages_only": 0,
        },
    },
    "intent": {
        "sentences": 3,
        "scored": 3,
        "model_unavailable": 0,
        "by_field": {"city": 1.0, "campus": 2 / 3},
        "all_fields_right": 2 / 3,
        "misses": [{"sentence": "HU Adlershof", "wrong": ["campus"]}],
    },
}


def test_the_summary_is_written_from_the_saved_results() -> None:
    text = render(RESULTS)

    assert "Measured on 2026-10-06" in text
    assert text.index("`embed-a` | 100% | 100% | 1.00 | 1 of 1 |") < text.index("`embed-b` | 50%")
    assert "between 0.71 and 0.86" in text and "between 0.55 and 0.75" in text
    assert "100% of the answerable questions pass and 50% of the unanswerable ones" in text
    assert "| Answerable: answered, citing a right source | 3 of 4 |" in text
    assert "| Unanswerable: correctly refused | 2 of 2 |" in text
    assert "| campus | 67% |" in text
    assert "| **every field of a sentence** | **67%** |" in text
    assert '- "HU Adlershof": campus' in text
    assert "got no reply" not in text


def test_both_charts_are_drawn_from_the_saved_results(tmp_path: Path) -> None:
    pytest.importorskip("matplotlib", reason="charts need the eval dependency group")
    from evaluation.charts import retrieval_chart, save_charts, similarity_chart

    results = {
        **RESULTS,
        "similarity_gate": {
            **RESULTS["similarity_gate"],  # type: ignore[dict-item]
            "answerable_best": [0.71, 0.8, 0.86],
            "unanswerable_best": [0.55, 0.75],
        },
    }

    bars = retrieval_chart(results).axes[0]
    dots = similarity_chart(results).axes[0]
    saved = save_charts(results, tmp_path)

    assert [label.get_text() for label in bars.get_yticklabels()] == ["embed-b", "embed-a"]
    assert bars.get_title(loc="left") == "Retrieval quality by embedding model, 4 questions"
    legend = dots.get_legend()
    assert legend is not None
    assert [text.get_text() for text in legend.get_texts()] == [
        "The documents answer it (3)",
        "The documents do not (2)",
    ]
    assert [path.name for path in saved] == ["retrieval.png", "similarity_gate.png"]
    assert all(path.stat().st_size > 1000 for path in saved)

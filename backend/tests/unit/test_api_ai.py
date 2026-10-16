"""The AI endpoints over HTTP, with the model scripted or switched off."""

import dataclasses
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from infrastructure.budget import DailyBudget
from infrastructure.fakes.ai import (
    InMemoryBriefings,
    InMemoryUsageLedger,
    InMemoryVectorStore,
    ScriptedLLMClient,
    WordEmbedder,
)
from ports.llm import LLMUnavailableError
from ports.usage import DailyLimitReachedError
from services.briefing import BriefingWriter
from tests.unit.api_client import V1, make_client
from tests.unit.engine_world import (
    ALTSTADT,
    CITY,
    EMPLOYER,
    MAIN_CAMPUS,
    NORDEND,
    NORTH_CAMPUS,
    build_engine,
)
from tests.unit.test_intent import reply
from tests.unit.test_rag import (
    PAPERS,
    QUESTION,
    REGISTRATION,
    chunk,
    library,
    store_with,
    written,
)

SEARCH = {"campus_id": MAIN_CAMPUS, "max_commute_minutes": 40, "max_rent_eur": 700}
SENTENCE = {"sentence": "I study at SU and can pay 650 euros", "city_id": CITY}


# --- Status --------------------------------------------------------------------


def test_status_says_whether_a_model_is_configured() -> None:
    off = make_client()[0].get(f"{V1}/ai/status")
    on = make_client(llm=ScriptedLLMClient())[0].get(f"{V1}/ai/status")

    assert (off.status_code, off.json()["enabled"]) == (200, False)
    assert on.json() == {"enabled": True, "daily_limit_reached": False, "resets_at": None}


def test_status_reports_a_spent_daily_allowance_and_when_it_returns() -> None:
    now = datetime(2026, 10, 16, 12, tzinfo=UTC)
    spent = DailyBudget(InMemoryUsageLedger(), "flash-test", 0, clock=lambda: now)
    client = make_client(llm=ScriptedLLMClient(), budgets=[spent])[0]

    status = client.get(f"{V1}/ai/status").json()

    assert status["daily_limit_reached"] is True
    assert status["resets_at"] == "2026-10-17T07:00:00Z"


def test_a_spent_allowance_answers_503_with_its_own_code_and_retry_after() -> None:
    resets_at = datetime.now(UTC) + timedelta(hours=3)
    llm = ScriptedLLMClient(DailyLimitReachedError("flash-test", resets_at))
    client = make_client(llm=llm)[0]

    response = client.post(f"{V1}/intent", json=SENTENCE)

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "ai_daily_limit"
    assert 3 * 3600 - 60 <= int(response.headers["Retry-After"]) <= 3 * 3600


# --- Sentence to settings ----------------------------------------------------------


def test_a_sentence_becomes_search_settings() -> None:
    llm = ScriptedLLMClient(
        reply(
            university_id=2,
            employer_id=EMPLOYER,
            max_rent_eur=650,
            important=["rent"],
            not_understood=["wants a balcony"],
        )
    )
    client = make_client(llm=llm)[0]

    response = client.post(f"{V1}/intent", json=SENTENCE)

    assert response.status_code == 200
    assert response.json() == {
        "understood": True,
        "city_id": CITY,
        "campus": {
            "id": NORTH_CAMPUS,
            "name": "North Campus",
            "university_id": 2,
            "university_short_name": "SU",
        },
        "max_rent_eur": 650,
        "max_commute_minutes": None,
        "employer": {"id": EMPLOYER, "name": "Example Works"},
        "weights": {"commute": 0.35, "rent": 0.5, "amenities": 0.15, "job_access": 0.15},
        "notes": [
            "No campus of SU was named, so North Campus is used. Change it if you study elsewhere.",
            "Not used: wants a balcony",
        ],
    }
    assert "I study at SU and can pay 650 euros" in llm.prompts[0]
    assert "model;dur=" in response.headers["Server-Timing"]


def test_a_sentence_with_nothing_usable_says_so() -> None:
    client = make_client(llm=ScriptedLLMClient(reply()))[0]

    body = client.post(f"{V1}/intent", json=SENTENCE).json()

    assert body["understood"] is False
    assert body["campus"] is None and body["weights"] is None


def test_the_settings_from_a_sentence_run_through_the_ordinary_search() -> None:
    client = make_client(llm=ScriptedLLMClient(reply(campus_id=MAIN_CAMPUS, max_rent_eur=700)))[0]

    found = client.post(f"{V1}/intent", json=SENTENCE).json()
    search = client.post(
        f"{V1}/search",
        json={
            "campus_id": found["campus"]["id"],
            "max_rent_eur": found["max_rent_eur"],
            "max_commute_minutes": 40,
        },
    )

    assert [item["area"]["name"] for item in search.json()["ranked"]] == [
        "Altstadt",
        "Nordend",
        "Ostpark",
    ]


@pytest.mark.parametrize(
    "body",
    [
        {"sentence": "hi"},
        {"sentence": "x" * 501},
        {},
        {"sentence": "a valid sentence", "campus_id": 1},
    ],
    ids=["too short", "too long", "missing", "unknown field"],
)
def test_an_invalid_sentence_request_is_a_422(body: dict[str, Any]) -> None:
    llm = ScriptedLLMClient(reply())

    response = make_client(llm=llm)[0].post(f"{V1}/intent", json=body)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_request"
    assert llm.prompts == []


# --- Without the model -----------------------------------------------------------------


@pytest.mark.parametrize(
    "llm",
    [None, ScriptedLLMClient(LLMUnavailableError("quota used up")), ScriptedLLMClient({"x": 1})],
    ids=["no key", "model fails", "reply does not fit the form"],
)
def test_without_a_usable_model_the_sentence_search_answers_503(
    llm: ScriptedLLMClient | None, caplog: pytest.LogCaptureFixture
) -> None:
    client = make_client(llm=llm)[0]

    response = client.post(f"{V1}/intent", json=SENTENCE)

    assert response.status_code == 503
    error = response.json()["error"]
    assert error["code"] == "ai_unavailable"
    assert error["request_id"] == response.headers["X-Request-ID"]
    # The reason is logged for the operator, not sent to the client.
    assert "quota" not in error["message"]
    assert "model unavailable" in caplog.text


def test_everything_else_works_while_the_model_is_off() -> None:
    client = make_client()[0]

    assert client.post(f"{V1}/intent", json=SENTENCE).status_code == 503
    assert client.post(f"{V1}/search", json=SEARCH).status_code == 200
    assert client.get(f"{V1}/cities/{CITY}/comparison?max_rent_eur=700&max_commute_minutes=40")
    assert client.get(f"{V1}/areas/1?campus_id={MAIN_CAMPUS}").status_code == 200
    assert client.get("/health").status_code == 200


# --- The stricter limit on model calls ----------------------------------------------


def test_model_endpoints_have_their_own_stricter_limit() -> None:
    llm = ScriptedLLMClient(reply(), reply(), reply())
    client = make_client(llm=llm, rate_limit_per_minute=100, ai_rate_limit_per_minute=2)[0]

    statuses = [client.post(f"{V1}/intent", json=SENTENCE).status_code for _ in range(3)]
    refused = client.post(f"{V1}/intent", json=SENTENCE)

    assert statuses == [200, 200, 429]
    assert refused.json()["error"]["code"] == "rate_limited"
    assert int(refused.headers["Retry-After"]) >= 1
    assert len(llm.prompts) == 2
    # Only the model endpoints are held back; the search is not.
    assert client.post(f"{V1}/search", json=SEARCH).status_code == 200
    assert client.get(f"{V1}/ai/status").status_code == 200


# --- Questions answered from documents ---------------------------------------------

ASK = {"question": QUESTION, "city_id": CITY}


def ask_client(
    *replies: Any, embedder: WordEmbedder | None = None, store: InMemoryVectorStore | None = None
) -> tuple[Any, ScriptedLLMClient]:
    llm = ScriptedLLMClient(*replies)
    client = make_client(
        llm=llm, embedder=embedder or WordEmbedder(), vector_store=store or library()
    )[0]
    return client, llm


def test_a_question_is_answered_with_its_sources() -> None:
    client, _ = ask_client(written("You must register within 14 days [1]."))

    response = client.post(f"{V1}/ask", json=ASK)

    assert response.status_code == 200
    assert response.json() == {
        "status": "answered",
        "answer": "You must register within 14 days [1].",
        "citations": [
            {
                "number": 1,
                "title": "Registering your address",
                "section": "Deadline",
                "passage": "You must register your address within 14 days.",
                "source_url": "https://example.org/registration",
                "retrieved_on": "2026-10-06",
                "city_id": None,
                "is_sample": True,
            }
        ],
    }
    stages = [part.split(";")[0] for part in response.headers["Server-Timing"].split(", ")]
    assert stages == ["embed", "retrieve", "model", "total"]


def test_a_source_that_may_not_be_quoted_is_cited_without_its_passage() -> None:
    official = dataclasses.replace(chunk("registration", REGISTRATION), can_quote=False)
    client, _ = ask_client(
        written("You must register within 14 days [1]."), store=store_with(official)
    )

    (citation,) = client.post(f"{V1}/ask", json=ASK).json()["citations"]

    assert citation["passage"] is None
    assert citation["source_url"] == "https://example.org/registration"


def test_a_question_the_documents_do_not_cover_is_not_answered() -> None:
    client, llm = ask_client(written("Zebras play the violin [1]."))

    body = client.post(f"{V1}/ask", json={"question": "zebra quantum violin"}).json()

    assert (body["status"], body["citations"]) == ("no_evidence", [])
    assert "do not cover that question" in body["answer"]
    assert llm.prompts == []


def test_when_the_text_model_fails_the_passages_are_still_returned() -> None:
    client, _ = ask_client(LLMUnavailableError("quota used up"))

    response = client.post(f"{V1}/ask", json=ASK)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "sources_only"
    assert [c["passage"] for c in body["citations"]] == [
        REGISTRATION.split("\n")[1],
        PAPERS.split("\n")[1],
    ]


def test_without_an_embedder_questions_answer_503_and_the_search_still_works() -> None:
    client = make_client()[0]

    response = client.post(f"{V1}/ask", json=ASK)

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "ai_unavailable"
    assert client.post(f"{V1}/search", json=SEARCH).status_code == 200


@pytest.mark.parametrize(
    ("body", "status"),
    [
        ({"question": "hi"}, 422),
        ({"question": "x" * 301}, 422),
        ({}, 422),
        ({"question": QUESTION, "city_id": "atlantis"}, 404),
    ],
    ids=["too short", "too long", "missing", "unknown city"],
)
def test_an_invalid_question_is_refused_before_any_model_is_called(
    body: dict[str, Any], status: int
) -> None:
    embedder = WordEmbedder()
    client, llm = ask_client(written("x [1]"), embedder=embedder)

    assert client.post(f"{V1}/ask", json=body).status_code == status
    assert (embedder.queries, llm.prompts) == ([], [])


def test_the_stricter_limit_counts_sentences_and_questions_together() -> None:
    llm = ScriptedLLMClient(reply(), written("Within 14 days [1]."))
    client = make_client(
        llm=llm, embedder=WordEmbedder(), vector_store=library(), ai_rate_limit_per_minute=2
    )[0]

    statuses = [
        client.post(f"{V1}/intent", json=SENTENCE).status_code,
        client.post(f"{V1}/ask", json=ASK).status_code,
        client.post(f"{V1}/ask", json=ASK).status_code,
    ]

    assert statuses == [200, 200, 429]


# --- Stored briefings ------------------------------------------------------------------


def written_briefings(*texts: str) -> InMemoryBriefings:
    """Briefings for the first areas of Testville, written by a scripted model."""
    engine, briefings = build_engine(), InMemoryBriefings()
    llm = ScriptedLLMClient(*texts, model_name="scripted-model")
    BriefingWriter(llm, engine.catalog, engine.collector, briefings).refresh_city(
        CITY, limit=len(texts)
    )
    return briefings


def test_a_stored_briefing_is_read_without_any_model() -> None:
    briefings = written_briefings("Altstadt costs 680 EUR and has 20 cafes.")
    client = make_client(briefings=briefings)[0]

    response = client.get(f"{V1}/areas/{ALTSTADT}/briefing")

    assert response.status_code == 200
    body = response.json()
    assert body["area"] == {"id": ALTSTADT, "name": "Altstadt"}
    assert body["briefing"]["text"] == "Altstadt costs 680 EUR and has 20 cafes."
    assert body["briefing"]["model"] == "scripted-model"
    assert body["briefing"]["uses_sample_rent"] is False
    assert body["briefing"]["generated_at"].startswith("20")


def test_an_area_without_a_briefing_says_unknown() -> None:
    client = make_client(briefings=written_briefings("Altstadt costs 680 EUR."))[0]

    body = client.get(f"{V1}/areas/{NORDEND}/briefing").json()

    assert body == {"area": {"id": NORDEND, "name": "Nordend"}, "briefing": "UNKNOWN"}


def test_a_briefing_is_withdrawn_when_the_figures_behind_it_change() -> None:
    briefings = written_briefings("Altstadt costs 680 EUR.")
    # The same areas, but now without any places data: the amenity and job
    # figures the briefing was written from are no longer the current ones.
    client = make_client(briefings=briefings, with_places=False)[0]

    assert client.get(f"{V1}/areas/{ALTSTADT}/briefing").json()["briefing"] == "UNKNOWN"


@pytest.mark.parametrize(("area", "status"), [("999", 404), ("0", 422), ("abc", 422)])
def test_briefing_errors(area: str, status: int) -> None:
    assert make_client()[0].get(f"{V1}/areas/{area}/briefing").status_code == status

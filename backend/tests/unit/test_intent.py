"""Sentence to search settings: the model's reply is scripted, the checks are real."""

from typing import Any

import pytest

from domain.intent import SearchIntent
from domain.score import DEFAULT_WEIGHTS, EMPHASISED_WEIGHT, adjusted_weights
from infrastructure.fakes.ai import ScriptedLLMClient
from ports.llm import LLMUnavailableError
from services.intent import EXTRACTION_SCHEMA, IntentService
from tests.unit.engine_world import (
    CITY,
    EAST_CAMPUS,
    EMPLOYER,
    EMPLOYER_ELSEWHERE,
    HOTSPOT,
    MAIN_CAMPUS,
    NORTH_CAMPUS,
    build_engine,
)

FIRST_UNIVERSITY, SECOND_UNIVERSITY = 1, 2


def reply(**fields: Any) -> dict[str, Any]:
    """A filled-in form as the model would return it; everything else is empty."""
    empty: dict[str, Any] = {
        "city_id": None,
        "university_id": None,
        "campus_id": None,
        "employer_id": None,
        "max_rent_eur": None,
        "max_commute_minutes": None,
        "important": [],
        "unimportant": [],
        "not_understood": [],
    }
    return empty | fields


def parse(model_reply: Any, current_city_id: str | None = CITY) -> SearchIntent:
    service = IntentService(ScriptedLLMClient(model_reply), build_engine().catalog)
    return service.parse("a sentence", current_city_id)


# --- What a sentence can set -------------------------------------------------------


def test_a_full_sentence_sets_every_control() -> None:
    intent = parse(
        reply(
            campus_id=EAST_CAMPUS,
            employer_id=EMPLOYER,
            max_rent_eur=650,
            max_commute_minutes=30,
            important=["rent"],
        )
    )

    assert intent.city_id == CITY
    assert (intent.campus.id, intent.university.short_name) == (EAST_CAMPUS, "SU")  # type: ignore[union-attr]
    assert (intent.max_rent_eur, intent.max_commute_minutes) == (650, 30)
    assert intent.employer.name == "Example Works"  # type: ignore[union-attr]
    assert intent.weights == {**DEFAULT_WEIGHTS, "rent": EMPHASISED_WEIGHT}
    assert intent.notes == ()
    assert not intent.is_empty


def test_a_sentence_that_says_nothing_usable_is_empty() -> None:
    intent = parse(reply(not_understood=["wants a balcony"]))

    assert intent.is_empty
    assert intent.notes == ("Not used: wants a balcony",)


def test_a_university_with_one_campus_needs_no_assumption() -> None:
    intent = parse(reply(university_id=FIRST_UNIVERSITY))

    assert intent.campus.id == MAIN_CAMPUS  # type: ignore[union-attr]
    assert intent.notes == ()


def test_a_university_with_several_campuses_uses_its_main_one_and_says_so() -> None:
    intent = parse(reply(university_id=SECOND_UNIVERSITY))

    assert intent.campus.id == NORTH_CAMPUS  # type: ignore[union-attr]
    assert intent.notes == (
        "No campus of SU was named, so North Campus is used. Change it if you study elsewhere.",
    )


def test_a_named_campus_wins_over_the_university_and_city_the_model_gave() -> None:
    intent = parse(
        reply(campus_id=EAST_CAMPUS, university_id=FIRST_UNIVERSITY, city_id="elsewhere")
    )

    assert (intent.campus.id, intent.university.id) == (EAST_CAMPUS, SECOND_UNIVERSITY)  # type: ignore[union-attr]
    assert intent.city_id == CITY


def test_a_city_alone_is_kept() -> None:
    assert parse(reply(city_id="elsewhere")).city_id == "elsewhere"


def test_repeating_the_city_the_student_is_already_looking_at_is_not_a_setting() -> None:
    intent = parse(reply(city_id=CITY), current_city_id=CITY)

    assert intent.is_empty


# --- The model's reply is checked, not trusted -----------------------------------


@pytest.mark.parametrize(
    "fields",
    [
        {"campus_id": 999},
        {"university_id": 999},
        {"employer_id": 999},
        {"employer_id": HOTSPOT},
        {"city_id": "atlantis"},
    ],
    ids=["campus", "university", "employer", "a job hotspot is not an employer", "city"],
)
def test_an_id_that_is_not_in_the_catalogue_is_dropped(fields: dict[str, Any]) -> None:
    assert parse(reply(**fields)).is_empty


@pytest.mark.parametrize(
    ("fields", "note"),
    [
        (
            {"max_rent_eur": 50000},
            "A rent limit of 50000 EUR is outside what the search accepts (1 to 20000), "
            "so it was left out.",
        ),
        (
            {"max_rent_eur": 0},
            "A rent limit of 0 EUR is outside what the search accepts (1 to 20000), "
            "so it was left out.",
        ),
        (
            {"max_commute_minutes": 600},
            "A commute limit of 600 min is outside what the search accepts (1 to 180), "
            "so it was left out.",
        ),
    ],
)
def test_a_number_out_of_range_is_left_out_with_a_note(fields: dict[str, Any], note: str) -> None:
    intent = parse(reply(**fields))

    assert intent.is_empty
    assert intent.notes == (note,)


def test_an_employer_in_another_city_than_the_campus_is_not_pinned() -> None:
    intent = parse(reply(campus_id=MAIN_CAMPUS, employer_id=EMPLOYER_ELSEWHERE))

    assert intent.employer is None
    assert intent.notes == ("Far Works is in Elsewhere, not in Testville, so it was not pinned.",)


def test_an_employer_alone_also_says_which_city_is_meant() -> None:
    moved = parse(reply(employer_id=EMPLOYER_ELSEWHERE), current_city_id=CITY)
    same = parse(reply(employer_id=EMPLOYER), current_city_id=CITY)

    assert (moved.city_id, moved.employer.id) == ("elsewhere", EMPLOYER_ELSEWHERE)  # type: ignore[union-attr]
    assert moved.notes == ("Far Works is in Elsewhere, so the search moved there.",)
    assert (same.city_id, same.notes) == (CITY, ())


@pytest.mark.parametrize(
    "broken",
    [
        reply(max_rent_eur="cheap"),
        reply(important=["nightlife"]),
        {"max_rent_eur": 700},
        reply(not_understood="a string, not a list"),
    ],
    ids=["text for a number", "unknown preference", "fields missing", "wrong type"],
)
def test_a_reply_that_does_not_fit_the_form_counts_as_no_answer(broken: dict[str, Any]) -> None:
    with pytest.raises(LLMUnavailableError, match="did not fit the form"):
        parse(broken)


def test_fields_the_form_does_not_have_are_ignored() -> None:
    intent = parse(reply(max_rent_eur=700, ranking=["Altstadt first"], campus_name="Main"))

    assert intent.max_rent_eur == 700


def test_an_unavailable_model_is_reported_to_the_caller() -> None:
    with pytest.raises(LLMUnavailableError, match="quota"):
        parse(LLMUnavailableError("quota used up"))


# --- Preferences become weights by a fixed rule ----------------------------------------


def test_no_stressed_preference_leaves_the_weights_alone() -> None:
    assert parse(reply(max_rent_eur=700)).weights is None


def test_an_unimportant_preference_is_switched_off() -> None:
    intent = parse(reply(important=["commute", "job_access"], unimportant=["amenities"]))

    assert intent.weights == {"commute": 0.5, "rent": 0.35, "amenities": 0.0, "job_access": 0.5}


def test_calling_everything_unimportant_changes_nothing() -> None:
    intent = parse(reply(unimportant=["commute", "rent", "amenities", "job_access"]))

    assert intent.weights is None
    assert intent.notes == (
        "Every preference was called unimportant, so the weights were left as they are.",
    )


def test_a_preference_named_both_ways_counts_as_important() -> None:
    assert adjusted_weights(["rent"], ["rent"])["rent"] == EMPHASISED_WEIGHT


def test_an_unknown_preference_is_an_error() -> None:
    with pytest.raises(ValueError, match="nightlife"):
        adjusted_weights(["nightlife"], [])


# --- Notes from the model -----------------------------------------------------------


def test_the_models_notes_are_capped_trimmed_and_labelled() -> None:
    intent = parse(reply(not_understood=["  a balcony ", "", "x" * 300, "a garden", "a fifth"]))

    assert intent.notes == ("Not used: a balcony", f"Not used: {'x' * 120}")


# --- What the model is shown ------------------------------------------------------------


def test_the_prompt_lists_the_catalogue_and_quotes_the_sentence() -> None:
    llm = ScriptedLLMClient(reply())

    IntentService(llm, build_engine().catalog).parse("I study at SU, east side", CITY)

    (prompt,) = llm.prompts
    assert "- testville | Testville" in prompt
    assert "- 2 | testville | SU | Second University" in prompt
    assert f"- {EAST_CAMPUS} | 2 | East Campus" in prompt
    assert f"- {EMPLOYER} | testville | Example Works" in prompt
    assert f"- {EMPLOYER_ELSEWHERE} | elsewhere | Far Works" in prompt
    assert "Job hotspot" not in prompt
    assert "The student is currently looking at: testville" in prompt
    assert prompt.endswith('Sentence: """I study at SU, east side"""')
    assert llm.schemas == [EXTRACTION_SCHEMA]


def test_an_unknown_current_city_is_not_passed_on() -> None:
    llm = ScriptedLLMClient(reply())

    IntentService(llm, build_engine().catalog).parse("anything", "atlantis")

    assert "currently looking at" not in llm.prompts[0]


def test_the_form_sent_to_the_model_names_every_field_and_preference() -> None:
    properties = EXTRACTION_SCHEMA["properties"]

    assert set(properties) == set(reply())
    assert set(EXTRACTION_SCHEMA["required"]) == set(reply())
    assert "job_access" in str(properties["important"])

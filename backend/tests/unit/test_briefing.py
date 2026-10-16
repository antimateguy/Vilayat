"""Area briefings: the figures given to the model, the checks on its text, and reading."""

import dataclasses
from datetime import UTC, datetime, timedelta

import pytest

from domain.briefing import AreaBriefing, BriefingFacts
from infrastructure.fakes.ai import InMemoryBriefings, Reply, ScriptedLLMClient
from ports.llm import LLMUnavailableError
from services.briefing import BriefingReader, BriefingWriter, briefing_facts
from services.errors import NotFoundError
from services.grounding import unsupported_names
from tests.unit.engine_world import (
    ALTSTADT,
    CITY,
    NAMES,
    NORDEND,
    OSTPARK,
    WESTEND,
    Engine,
    build_engine,
)

NOW = datetime(2026, 10, 6, 12, 0, tzinfo=UTC)
IN_ORDER = sorted(NAMES.values())
"""Areas are handled in name order: Altstadt, Fernweh, Niemandsland, Nordend, ..."""
AREA_COUNT = len(IN_ORDER)


def plain(area: str) -> str:
    """A text that passes every check for that area."""
    return f"{area} is described here without any figure."


EVERY_AREA = [plain(name) for name in IN_ORDER]


def facts_of(engine: Engine) -> dict[int, BriefingFacts]:
    return briefing_facts("Testville", engine.collector.collect(CITY, None))


def writer(engine: Engine, briefings: InMemoryBriefings, *replies: Reply) -> BriefingWriter:
    llm = ScriptedLLMClient(*replies, model_name="scripted-model")
    return BriefingWriter(llm, engine.catalog, engine.collector, briefings, clock=lambda: NOW)


def reader(engine: Engine, briefings: InMemoryBriefings) -> BriefingReader:
    return BriefingReader(engine.catalog, engine.areas, engine.collector, briefings)


# --- The figures given to the model -------------------------------------------------


def test_the_facts_of_an_area_are_its_figures_and_its_place_in_the_city() -> None:
    assert facts_of(build_engine())[ALTSTADT] == {
        "neighbourhood": "Altstadt",
        "city": "Testville",
        "typical_monthly_rent_eur": 680,
        # Six areas have a rent figure; only Teuerberg (900) is dearer.
        "percent_of_the_citys_areas_with_higher_rent": 17,
        "rent_figure_is_a_placeholder": False,
        "supermarkets": 6,
        "cafes": 20,
        "libraries": 1,
        "gyms": 3,
        "businesses_that_typically_hire_students_within_about_2_km": 500,
        "percent_of_the_city_with_fewer_such_businesses_nearby": 95,
    }


def test_a_sample_rent_is_marked_and_a_missing_category_is_a_real_zero() -> None:
    nordend = facts_of(build_engine())[NORDEND]

    assert nordend["rent_figure_is_a_placeholder"] is True
    assert (nordend["cafes"], nordend["libraries"], nordend["gyms"]) == (4, 0, 0)


def test_a_missing_figure_is_written_as_unknown_and_never_compared() -> None:
    westend = facts_of(build_engine())[WESTEND]

    assert westend["typical_monthly_rent_eur"] == "unknown"
    assert "percent_of_the_citys_areas_with_higher_rent" not in westend
    assert "rent_figure_is_a_placeholder" not in westend
    assert westend["job_access"] == "unknown"


def test_without_places_data_amenities_and_job_access_are_unknown() -> None:
    altstadt = facts_of(build_engine(with_places=False))[ALTSTADT]

    assert altstadt["everyday_amenities"] == "unknown"
    assert altstadt["job_access"] == "unknown"
    assert "cafes" not in altstadt


def test_the_facts_are_plain_values_that_survive_being_stored() -> None:
    for facts in facts_of(build_engine()).values():
        assert all(type(value) in (str, int, bool) for value in facts.values())


# --- Writing -------------------------------------------------------------------------


def test_a_briefing_is_stored_with_its_facts_model_and_time() -> None:
    engine, briefings = build_engine(), InMemoryBriefings()

    report = writer(engine, briefings, "Altstadt costs 680 EUR.\n  It has 20 cafes.").refresh_city(
        CITY, limit=1
    )

    assert report.written == ["Altstadt"]
    assert briefings.stored[ALTSTADT] == AreaBriefing(
        area_id=ALTSTADT,
        content="Altstadt costs 680 EUR. It has 20 cafes.",
        facts=facts_of(engine)[ALTSTADT],
        model="scripted-model",
        generated_at=NOW,
    )


def test_the_model_is_given_the_rules_and_the_facts_line_by_line() -> None:
    engine = build_engine()
    llm = ScriptedLLMClient(plain("Altstadt"))
    BriefingWriter(llm, engine.catalog, engine.collector, InMemoryBriefings()).refresh_city(
        CITY, limit=1
    )

    (prompt,) = llm.prompts
    assert "Copy every figure exactly as given." in prompt
    assert "spelt exactly as in the facts" in prompt
    assert "never call them that" in prompt
    assert "neighbourhood: Altstadt\ncity: Testville\ntypical monthly rent in EUR: 680\n" in prompt
    # The page marks a placeholder rent itself; the model is not asked to.
    assert "placeholder" not in prompt
    assert prompt.endswith("percent of the city that has fewer such businesses nearby: 95")


def test_every_area_gets_a_briefing_and_a_second_run_calls_no_model() -> None:
    engine, briefings = build_engine(), InMemoryBriefings()

    first = writer(engine, briefings, *EVERY_AREA).refresh_city(CITY)
    second = writer(engine, briefings).refresh_city(CITY)

    assert first.written == IN_ORDER
    assert (second.written, second.unchanged) == ([], IN_ORDER)
    assert second.stopped_because is None


def test_force_rewrites_briefings_that_are_current() -> None:
    engine, briefings = build_engine(), InMemoryBriefings()
    writer(engine, briefings, *EVERY_AREA).refresh_city(CITY)
    rewritten = [f"{name}, rewritten." for name in IN_ORDER]

    report = writer(engine, briefings, *rewritten).refresh_city(CITY, force=True)

    assert len(report.written) == AREA_COUNT
    assert briefings.stored[OSTPARK].content == "Ostpark, rewritten."


def test_a_rewrite_can_carry_on_with_only_the_older_briefings() -> None:
    engine, briefings = build_engine(), InMemoryBriefings()
    writer(engine, briefings, *EVERY_AREA).refresh_city(CITY)
    newer = briefings.stored[OSTPARK]
    briefings.save(dataclasses.replace(newer, generated_at=NOW + timedelta(hours=1)))

    report = writer(engine, briefings, *EVERY_AREA).refresh_city(
        CITY, written_before=NOW + timedelta(minutes=30)
    )

    assert len(report.written) == AREA_COUNT - 1
    assert report.unchanged == ["Ostpark"]


@pytest.mark.parametrize(
    ("text", "problem"),
    [
        ("Altstadt costs about 700 EUR.", "figures that are not in the facts: 700"),
        (
            "Altstadt costs 680 EUR and is 15 minutes from the centre.",
            "figures that are not in the facts: 15",
        ),
        ("Altstat costs 680 EUR.", "the neighbourhood's name, Altstadt, is missing or misspelt"),
        ("The area costs 680 EUR.", "the neighbourhood's name, Altstadt, is missing or misspelt"),
        (
            "Altstadt costs 680 EUR and lies next to the Englischer Garten.",
            "names that are not in the facts: Englischer, Garten",
        ),
        ("Altstadt " + "word " * 90, "too long (91 words)"),
    ],
    ids=[
        "a rounded figure",
        "an invented figure",
        "a misspelt name",
        "no name",
        "an invented place",
        "too long",
    ],
)
def test_a_text_that_fails_a_check_twice_is_reported_and_not_stored(
    text: str, problem: str
) -> None:
    engine, briefings = build_engine(), InMemoryBriefings()

    report = writer(engine, briefings, text, text, plain("Fernweh")).refresh_city(CITY, limit=2)

    assert report.rejected == {"Altstadt": problem}
    assert report.written == ["Fernweh"]
    assert ALTSTADT not in briefings.stored


def test_a_rejected_text_gets_one_more_try_that_is_told_the_reason() -> None:
    engine, briefings = build_engine(), InMemoryBriefings()
    llm = ScriptedLLMClient("Altstadt costs about 700 EUR.", "Altstadt costs 680 EUR.")
    report = BriefingWriter(llm, engine.catalog, engine.collector, briefings).refresh_city(
        CITY, limit=1
    )

    assert (report.written, report.rejected) == (["Altstadt"], {})
    assert briefings.stored[ALTSTADT].content == "Altstadt costs 680 EUR."
    first, second = llm.prompts
    assert second == (
        f"{first}\n\nYour previous text was rejected: figures that are not in the facts: 700. "
        "Write it again and follow every rule."
    )


def test_figures_and_names_from_the_facts_may_be_used_freely() -> None:
    engine, briefings = build_engine(), InMemoryBriefings()
    text = (
        "In Testville, Altstadt's 20 cafes and 6 supermarkets stand out. "
        "Only 17 percent of the city's areas cost more than its 680 EUR."
    )

    report = writer(engine, briefings, text).refresh_city(CITY, limit=1)

    assert report.rejected == {}
    assert briefings.stored[ALTSTADT].content == text


def test_the_limit_caps_the_areas_attempted_and_says_what_is_left() -> None:
    engine, briefings = build_engine(), InMemoryBriefings()

    report = writer(engine, briefings, *EVERY_AREA).refresh_city(CITY, limit=2)

    assert report.written == IN_ORDER[:2]
    assert report.not_reached == IN_ORDER[2:]
    assert report.stopped_because is None


def test_when_the_model_stops_the_work_done_is_kept_and_the_next_run_carries_on() -> None:
    engine, briefings = build_engine(), InMemoryBriefings()

    first = writer(
        engine, briefings, *EVERY_AREA[:2], LLMUnavailableError("quota used up")
    ).refresh_city(CITY)
    second = writer(engine, briefings, *EVERY_AREA[2:]).refresh_city(CITY)

    assert first.written == IN_ORDER[:2]
    assert first.stopped_because == "quota used up"
    assert first.not_reached == IN_ORDER[2:]
    assert second.unchanged == IN_ORDER[:2]
    assert second.written == IN_ORDER[2:]
    assert len(briefings.stored) == AREA_COUNT


def test_the_job_is_told_after_each_stored_briefing() -> None:
    engine, briefings = build_engine(), InMemoryBriefings()
    calls: list[int] = []
    bad = "Fernweh costs 1 EUR."

    writer(engine, briefings, plain("Altstadt"), bad, bad, plain("Niemandsland")).refresh_city(
        CITY, limit=3, after_each=lambda: calls.append(len(briefings.stored))
    )

    assert calls == [1, 2], "the rejected text in between stores nothing and triggers nothing"


def test_an_unknown_city_is_an_error() -> None:
    engine = build_engine()

    with pytest.raises(NotFoundError, match="no city with id atlantis"):
        writer(engine, InMemoryBriefings()).refresh_city("atlantis")


# --- Reading ---------------------------------------------------------------------------


def test_a_current_briefing_is_returned_with_its_area() -> None:
    engine, briefings = build_engine(), InMemoryBriefings()
    writer(engine, briefings, plain("Altstadt")).refresh_city(CITY, limit=1)

    area, briefing = reader(engine, briefings).get(ALTSTADT)

    assert area.name == "Altstadt"
    assert briefing is not None and briefing.content == plain("Altstadt")


def test_an_area_without_a_briefing_has_none() -> None:
    engine = build_engine()

    area, briefing = reader(engine, InMemoryBriefings()).get(NORDEND)

    assert (area.name, briefing) == ("Nordend", None)


def test_a_briefing_written_from_older_figures_is_not_shown() -> None:
    engine, briefings = build_engine(), InMemoryBriefings()
    older = {**facts_of(engine)[ALTSTADT], "typical_monthly_rent_eur": 650}
    briefings.save(AreaBriefing(ALTSTADT, "Altstadt costs 650 EUR.", older, "scripted-model", NOW))

    assert reader(engine, briefings).get(ALTSTADT)[1] is None


def test_a_stored_text_that_no_longer_passes_the_checks_is_not_shown_and_is_rewritten() -> None:
    engine, briefings = build_engine(), InMemoryBriefings()
    # Stored by an earlier version of the checks: right figures, misspelt name.
    current = facts_of(engine)[ALTSTADT]
    briefings.save(AreaBriefing(ALTSTADT, "Altstat costs 680 EUR.", current, "old-model", NOW))

    shown = reader(engine, briefings).get(ALTSTADT)[1]
    report = writer(engine, briefings, plain("Altstadt")).refresh_city(CITY, limit=1)

    assert shown is None
    assert report.written == ["Altstadt"]
    assert briefings.stored[ALTSTADT].content == plain("Altstadt")


def test_reading_the_briefing_of_an_unknown_area_is_an_error() -> None:
    with pytest.raises(NotFoundError, match="no area with id 999"):
        reader(build_engine(), InMemoryBriefings()).get(999)


# --- The name check ----------------------------------------------------------------------


def test_a_capitalised_word_inside_a_sentence_must_come_from_the_sources() -> None:
    sources = ["neighbourhood: Prenzlauer Berg\ncity: Berlin"]

    assert unsupported_names("Prenzlauer Berg in Berlin costs 700 EUR.", sources, ["EUR"]) == set()
    assert unsupported_names("It is near Mauerpark and the U2 line.", sources) == {
        "Mauerpark",
        "U2",
    }
    assert unsupported_names("Rent in Berlin's centre is high.", sources) == set()


def test_the_first_word_of_each_sentence_is_not_treated_as_a_name() -> None:
    assert unsupported_names("Rent is low. Cafes are few! Gyms? None.", []) == set()

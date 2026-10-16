"""Search end to end on in-memory repositories: no database, no network."""

from decimal import Decimal

import pytest

from domain.constraints import Constraints
from domain.search import SearchResult
from domain.unknown import UNKNOWN
from services.errors import InvalidRequestError, NotFoundError
from services.search import SearchRequest
from tests.unit.engine_world import (
    EMPLOYER,
    EMPLOYER_ELSEWHERE,
    HOTSPOT,
    MAIN_CAMPUS,
    build_engine,
)


def constraints(**changes: object) -> Constraints:
    values: dict[str, object] = {
        "campus_id": MAIN_CAMPUS,
        "max_commute_minutes": 40,
        "max_rent_eur": Decimal("700"),
    } | changes
    return Constraints(**values)  # type: ignore[arg-type]


def search(**request: object) -> SearchResult:
    request.setdefault("constraints", constraints())
    return build_engine().search.search(SearchRequest(**request))  # type: ignore[arg-type]


def ranked_names(result: SearchResult) -> list[str]:
    return [item.facts.area.name for item in result.ranked]


# --- Filtering -------------------------------------------------------------


def test_areas_within_both_limits_are_ranked() -> None:
    result = search()

    assert result.city_id == "testville"
    assert result.campus.id == MAIN_CAMPUS
    assert ranked_names(result) == ["Altstadt", "Nordend", "Ostpark"]
    assert [item.rank for item in result.ranked] == [1, 2, 3]


def test_areas_over_a_limit_are_excluded_with_the_reason() -> None:
    result = search()

    assert {item.facts.area.name: item.violations for item in result.excluded} == {
        "Fernweh": ("Commute of 70 min is over your 40 min limit.",),
        "Teuerberg": ("Rent of 900 EUR is over your 700 EUR ceiling.",),
    }


def test_every_area_of_the_city_lands_in_exactly_one_group() -> None:
    result = search()

    groups = [
        ranked_names(result),
        [item.facts.area.name for item in result.excluded],
        [item.facts.area.name for item in result.unchecked],
    ]
    assert sorted(name for group in groups for name in group) == [
        "Altstadt",
        "Fernweh",
        "Niemandsland",
        "Nordend",
        "Ostpark",
        "Teuerberg",
        "Westend",
    ]


def test_tighter_limits_exclude_more_areas() -> None:
    result = search(constraints=constraints(max_commute_minutes=20, max_rent_eur=Decimal("690")))

    assert ranked_names(result) == ["Altstadt"]
    assert {item.facts.area.name for item in result.excluded} == {
        "Nordend",
        "Ostpark",
        "Fernweh",
        "Teuerberg",
    }


def test_an_optional_job_access_floor_is_a_hard_constraint_too() -> None:
    result = search(constraints=constraints(min_job_access=0.5))

    assert ranked_names(result) == ["Altstadt", "Nordend"]
    excluded = {item.facts.area.name: item.violations for item in result.excluded}
    assert excluded["Ostpark"] == ("Job access of 0.20 is below your minimum of 0.50.",)


# --- UNKNOWN ---------------------------------------------------------------


def test_an_area_with_a_missing_figure_is_neither_ranked_nor_dropped() -> None:
    result = search()

    assert {item.facts.area.name: item.missing for item in result.unchecked} == {
        "Westend": ("No rent figure is known for this area.",),
        "Niemandsland": ("No travel time to the campus is stored for this area.",),
    }
    assert all(item.facts.area.name not in ("Westend", "Niemandsland") for item in result.ranked)


def test_search_still_ranks_when_no_places_data_is_loaded() -> None:
    engine = build_engine(with_places=False)

    result = engine.search.search(SearchRequest(constraints()))

    # Only commute and rent can count now, half each, which lifts cheap Ostpark
    # above Nordend: 0.38 against 0.33.
    assert ranked_names(result) == ["Altstadt", "Ostpark", "Nordend"]
    top = result.ranked[0]
    assert top.facts.amenity_counts is UNKNOWN
    assert top.facts.job_access is UNKNOWN
    assert set(top.score.shares) == {"commute", "rent"}


def test_a_job_access_floor_cannot_be_checked_without_places_data() -> None:
    engine = build_engine(with_places=False)

    result = engine.search.search(SearchRequest(constraints(min_job_access=0.5)))

    assert result.ranked == ()
    assert "Job access has not been computed for this area." in result.unchecked[0].missing


# --- Ranking through the search ---------------------------------------------


def test_weights_reorder_the_same_matches() -> None:
    by_rent = search(weights={"rent": 1.0})

    assert ranked_names(by_rent) == ["Ostpark", "Nordend", "Altstadt"]
    assert {item.facts.area.name for item in by_rent.excluded} == {"Fernweh", "Teuerberg"}


def test_every_result_carries_its_reasons_and_one_trade_off() -> None:
    result = search()

    for item in result.ranked:
        assert len(item.reasons) == 4
        assert item.trade_off.startswith("Weakest point is ")
    nordend = result.ranked[1]
    expected = (
        "Rent about 600 EUR a month, 100 EUR under your 700 EUR ceiling (placeholder figure)."
    )
    assert expected in nordend.reasons


# --- Employer pin ----------------------------------------------------------


def test_without_a_pinned_employer_no_full_day_is_shown() -> None:
    assert all(item.full_day is None for item in search().ranked)


def test_a_pinned_employer_adds_the_full_day_and_the_extra_time() -> None:
    result = search(employer_destination_id=EMPLOYER)

    altstadt, nordend, _ = result.ranked
    assert altstadt.full_day is not None and nordend.full_day is not None
    # Altstadt: home to campus 10, campus to job 15, job to home 18.
    assert altstadt.full_day.employer.name == "Example Works"
    assert altstadt.full_day.total_minutes == 43
    # Without the job the day is 10 + 12 = 22 minutes, so the job adds 21.
    assert altstadt.full_day.extra_minutes == 21
    assert (nordend.full_day.total_minutes, nordend.full_day.extra_minutes) == (70, 18)


def test_a_pinned_employer_informs_but_never_excludes_or_reorders() -> None:
    plain, pinned = search(), search(employer_destination_id=EMPLOYER)

    assert ranked_names(pinned) == ranked_names(plain)
    assert [i.score.total for i in pinned.ranked] == [i.score.total for i in plain.ranked]
    assert len(pinned.excluded) == len(plain.excluded)


def test_a_missing_leg_makes_the_full_day_unknown_but_keeps_the_area() -> None:
    ostpark = search(employer_destination_id=EMPLOYER).ranked[2]

    assert ostpark.facts.area.name == "Ostpark"
    assert ostpark.full_day is not None
    assert ostpark.full_day.job_to_home is UNKNOWN
    assert ostpark.full_day.total_minutes is UNKNOWN
    assert ostpark.full_day.extra_minutes is UNKNOWN


# --- Requests that make no sense --------------------------------------------


def test_an_unknown_campus_is_reported() -> None:
    with pytest.raises(NotFoundError, match="no campus with id 999"):
        search(constraints=constraints(campus_id=999))


@pytest.mark.parametrize("destination", [999, HOTSPOT])
def test_a_pin_must_be_an_existing_employer(destination: int) -> None:
    with pytest.raises(NotFoundError, match=f"no employer with id {destination}"):
        search(employer_destination_id=destination)


def test_an_employer_in_another_city_is_refused() -> None:
    with pytest.raises(InvalidRequestError, match="Far Works is in elsewhere"):
        search(employer_destination_id=EMPLOYER_ELSEWHERE)


def test_misspelt_weights_are_refused() -> None:
    with pytest.raises(InvalidRequestError, match="no such preference"):
        search(weights={"rents": 1.0})

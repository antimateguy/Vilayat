"""Budget comparison across universities, on in-memory repositories."""

from decimal import Decimal

import pytest

from domain.constraints import Constraints
from domain.search import CityComparison
from services.errors import NotFoundError
from services.search import SearchRequest
from tests.unit.engine_world import (
    ALTSTADT,
    CITY,
    MAIN_CAMPUS,
    NORDEND,
    OSTPARK,
    build_engine,
)


def compare(max_rent: str = "700", max_commute: int = 40) -> CityComparison:
    return build_engine().comparison.compare(CITY, Decimal(max_rent), max_commute)


def test_feasible_areas_are_counted_per_campus_side_by_side() -> None:
    comparison = compare()

    assert comparison.total_areas == 7
    first, second = comparison.universities
    assert first.university.short_name == "FU"
    assert [(c.campus.name, c.feasible, c.excluded, c.unchecked) for c in first.campuses] == [
        ("Main Campus", 3, 2, 2)
    ]
    # Second University: areas with no stored travel time to a campus cannot be checked.
    assert [(c.campus.name, c.feasible, c.excluded, c.unchecked) for c in second.campuses] == [
        ("East Campus", 1, 1, 5),
        ("North Campus", 2, 2, 3),
    ]


def test_every_area_is_counted_once_per_campus() -> None:
    comparison = compare()

    for university in comparison.universities:
        for campus in university.campuses:
            assert campus.feasible + campus.excluded + campus.unchecked == comparison.total_areas


def test_a_university_counts_areas_that_work_for_any_of_its_campuses() -> None:
    second = compare().universities[1]

    east, north = second.campuses
    assert east.feasible_area_ids == {OSTPARK}
    assert north.feasible_area_ids == {ALTSTADT, NORDEND}
    assert second.feasible == 3


def test_a_tighter_budget_leaves_fewer_feasible_areas() -> None:
    generous, tight = compare("700", 40), compare("500", 40)

    assert [u.feasible for u in generous.universities] == [3, 3]
    # Only Ostpark (450 EUR) is under 500 EUR and within 40 minutes of some campus.
    assert [u.feasible for u in tight.universities] == [1, 1]


def test_comparison_and_search_agree_on_what_is_feasible() -> None:
    engine = build_engine()
    constraints = Constraints(MAIN_CAMPUS, 40, Decimal("700"))

    searched = engine.search.search(SearchRequest(constraints))
    compared = engine.comparison.compare(CITY, Decimal("700"), 40).universities[0].campuses[0]

    assert compared.feasible_area_ids == {item.facts.area.id for item in searched.ranked}
    assert compared.excluded == len(searched.excluded)
    assert compared.unchecked == len(searched.unchecked)


def test_an_unknown_city_is_reported() -> None:
    with pytest.raises(NotFoundError, match="no city with id atlantis"):
        build_engine().comparison.compare("atlantis", Decimal("700"), 40)

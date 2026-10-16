"""The scorers: each maps one aspect of an area to 0..1 and explains it."""

from decimal import Decimal

import pytest

from domain.area import Area, AreaFacts
from domain.constraints import Constraints
from domain.place import JobAccess, PlaceCategory
from domain.unknown import UNKNOWN
from services.scorers import (
    AmenityScorer,
    CommuteScorer,
    JobAccessScorer,
    RentScorer,
    default_scorers,
)
from tests.unit.engine_world import rent

EMPTY = AreaFacts(
    area=Area(id=1, city_id="x", name="Area"),
    cell_count=10,
    rent=UNKNOWN,
    commute_minutes=UNKNOWN,
    amenity_counts=UNKNOWN,
    job_access=UNKNOWN,
)


def facts(**changes: object) -> AreaFacts:
    values = {field: getattr(EMPTY, field) for field in EMPTY.__slots__} | changes
    return AreaFacts(**values)


@pytest.mark.parametrize(("minutes", "value"), [(0, 1.0), (10, 0.75), (40, 0.0), (60, 0.0)])
def test_commute_score_falls_to_zero_at_the_limit(minutes: int, value: float) -> None:
    assert CommuteScorer(40).score(facts(commute_minutes=minutes)).value == pytest.approx(value)


def test_commute_reason_names_the_figure_and_the_margin() -> None:
    component = CommuteScorer(40).score(facts(commute_minutes=24))

    assert component.scorer == "commute"
    assert component.reason == (
        "24 min to campus by public transport, 16 min under your 40 min limit."
    )


@pytest.mark.parametrize(
    ("eur", "value"), [("700", 0.0), ("525", 0.5), ("350", 1.0), ("200", 1.0), ("800", 0.0)]
)
def test_rent_score_is_full_at_half_the_ceiling_and_zero_at_it(eur: str, value: float) -> None:
    component = RentScorer(Decimal("700")).score(facts(rent=rent(eur)))

    assert component.value == pytest.approx(value)


def test_rent_reason_always_says_where_the_figure_comes_from() -> None:
    scorer = RentScorer(Decimal("700"))

    real = scorer.score(facts(rent=rent("650"))).reason
    sample = scorer.score(facts(rent=rent("650", is_sample=True))).reason

    assert real == (
        "Rent about 650 EUR a month, 50 EUR under your 700 EUR ceiling "
        "(Housing report, 2026-01-01)."
    )
    assert sample.endswith("(placeholder figure).")


def test_amenity_score_rises_with_density_and_levels_off() -> None:
    scorer = AmenityScorer()

    def value(cafes: int) -> float:
        component = scorer.score(facts(amenity_counts={PlaceCategory.CAFE: cafes}))
        assert component.value is not UNKNOWN
        return component.value

    # 10 cells are 7 km2, so 49 amenities are 7 per km2: the half-marks density.
    assert value(0) == 0
    assert value(49) == pytest.approx(0.5)
    assert value(49) - value(0) > value(98) - value(49) > 0
    assert value(10_000) < 1


def test_amenity_reason_lists_each_category_and_ignores_other_places() -> None:
    counts = {PlaceCategory.CAFE: 14, PlaceCategory.SUPERMARKET: 18, PlaceCategory.BAR: 99}

    component = AmenityScorer().score(facts(amenity_counts=counts))

    assert component.reason == (
        "32 everyday amenities (18 supermarkets, 14 cafes, 0 libraries, 0 gyms), about 5 per km²."
    )


def test_amenity_reason_uses_the_singular_for_one() -> None:
    counts = {PlaceCategory.LIBRARY: 1, PlaceCategory.GYM: 1, PlaceCategory.CAFE: 2}

    reason = AmenityScorer().score(facts(amenity_counts=counts)).reason

    assert "(0 supermarkets, 2 cafes, 1 library, 1 gym)" in reason


def test_job_access_score_is_the_stored_score() -> None:
    component = JobAccessScorer().score(facts(job_access=JobAccess(259, 0.71)))

    assert component.value == 0.71
    assert component.reason == (
        "About 259 cafes, restaurants, bars and shops within 2 km, more than in 71% of the city."
    )


def test_every_scorer_reports_unknown_instead_of_guessing() -> None:
    constraints = Constraints(campus_id=1, max_commute_minutes=40, max_rent_eur=Decimal("700"))

    components = [scorer.score(EMPTY) for scorer in default_scorers(constraints)]

    assert [c.scorer for c in components] == ["commute", "rent", "amenities", "job_access"]
    assert all(c.value is UNKNOWN for c in components)
    assert all("unknown" in c.reason for c in components)


def test_an_area_without_cells_has_no_amenity_density() -> None:
    component = AmenityScorer().score(facts(cell_count=0, amenity_counts={PlaceCategory.CAFE: 3}))

    assert component.value is UNKNOWN

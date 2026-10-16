"""Domain value objects: validation and the UNKNOWN value."""

from datetime import date
from decimal import Decimal

import pytest

from domain.area import RentEstimate
from domain.constraints import Constraints
from domain.document import EMBEDDING_DIMENSIONS, DocChunk, EmbeddedChunk
from domain.geo import Coordinate
from domain.place import AMENITY_CATEGORIES, STUDENT_JOB_CATEGORIES, PlaceCategory
from domain.score import ScoreComponent
from domain.unknown import UNKNOWN, Unknown


def describe_rent(rent: Decimal | Unknown) -> str:
    """Type-checks only if `is UNKNOWN` narrows the union, which is the point."""
    if rent is UNKNOWN:
        return "unknown"
    return f"{rent.quantize(Decimal('1'))} EUR"


def test_unknown_is_one_distinct_value() -> None:
    assert UNKNOWN is Unknown.UNKNOWN
    assert list(Unknown) == [UNKNOWN]
    assert repr(UNKNOWN) == "UNKNOWN"


def test_callers_must_handle_unknown_separately_from_a_figure() -> None:
    assert describe_rent(UNKNOWN) == "unknown"
    assert describe_rent(Decimal("649.50")) == "650 EUR"


@pytest.mark.parametrize(("lat", "lon"), [(91, 0), (-91, 0), (0, 181), (0, -181)])
def test_coordinate_rejects_values_outside_the_globe(lat: float, lon: float) -> None:
    with pytest.raises(ValueError, match="out of range"):
        Coordinate(lat, lon)


def test_coordinate_accepts_berlin() -> None:
    assert Coordinate(52.52, 13.405).lat == 52.52


def test_distance_between_berlin_and_munich_city_centres() -> None:
    berlin, munich = Coordinate(52.5200, 13.4050), Coordinate(48.1372, 11.5756)

    assert berlin.distance_km(munich) == pytest.approx(504, abs=2)
    assert berlin.distance_km(berlin) == 0


def test_rent_estimate_rejects_a_non_positive_rent() -> None:
    with pytest.raises(ValueError, match="positive"):
        RentEstimate(
            monthly_eur=Decimal("0"),
            basis="sample",
            source="sample",
            source_url=None,
            as_of=date(2026, 1, 1),
            is_sample=True,
        )


@pytest.mark.parametrize(
    "overrides",
    [
        {"max_commute_minutes": 0},
        {"max_commute_minutes": 181},
        {"max_rent_eur": Decimal("0")},
        {"min_job_access": 1.5},
    ],
)
def test_constraints_reject_impossible_limits(overrides: dict[str, object]) -> None:
    valid: dict[str, object] = {
        "campus_id": 1,
        "max_commute_minutes": 40,
        "max_rent_eur": Decimal("700"),
    }
    with pytest.raises(ValueError):
        Constraints(**(valid | overrides))  # type: ignore[arg-type]


def test_constraints_accept_sensible_limits() -> None:
    constraints = Constraints(campus_id=1, max_commute_minutes=40, max_rent_eur=Decimal("700"))

    assert constraints.min_job_access is None


def test_score_component_accepts_unknown_but_not_out_of_range_values() -> None:
    assert ScoreComponent("rent", UNKNOWN, "no rent figure for this area").value is UNKNOWN
    with pytest.raises(ValueError, match="0 to 1"):
        ScoreComponent("rent", 1.2, "too high")


def test_embedded_chunk_rejects_a_vector_of_the_wrong_length() -> None:
    chunk = DocChunk("doc", 0, "Title", "https://example.org", "text", date(2026, 1, 1))

    EmbeddedChunk(chunk, (0.0,) * EMBEDDING_DIMENSIONS, "model")
    with pytest.raises(ValueError, match="dimensions"):
        EmbeddedChunk(chunk, (0.0,) * 3, "model")


def test_a_cafe_counts_as_both_an_amenity_and_a_student_employer() -> None:
    assert PlaceCategory.CAFE in AMENITY_CATEGORIES
    assert PlaceCategory.CAFE in STUDENT_JOB_CATEGORIES
    assert PlaceCategory.LIBRARY not in STUDENT_JOB_CATEGORIES

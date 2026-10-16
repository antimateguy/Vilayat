"""Points of interest taken from OpenStreetMap."""

from dataclasses import dataclass
from enum import StrEnum
from typing import Final


class PlaceCategory(StrEnum):
    SUPERMARKET = "supermarket"
    CAFE = "cafe"
    LIBRARY = "library"
    GYM = "gym"
    RESTAURANT = "restaurant"
    BAR = "bar"
    RETAIL = "retail"


AMENITY_CATEGORIES: Final = frozenset(
    {
        PlaceCategory.SUPERMARKET,
        PlaceCategory.CAFE,
        PlaceCategory.LIBRARY,
        PlaceCategory.GYM,
    }
)
"""What a student wants within walking distance of home."""

STUDENT_JOB_CATEGORIES: Final = frozenset(
    {
        PlaceCategory.CAFE,
        PlaceCategory.RESTAURANT,
        PlaceCategory.BAR,
        PlaceCategory.RETAIL,
        PlaceCategory.SUPERMARKET,
    }
)
"""Businesses that typically hire students. A proxy for where such employers
cluster, not a count of vacancies."""


@dataclass(frozen=True, slots=True)
class JobAccess:
    """How many student-type employers are near a home, and how that compares
    with the rest of the city."""

    places_nearby: int
    """Businesses in STUDENT_JOB_CATEGORIES within about 2 km."""
    score: float
    """Share of the city's cells that have fewer such businesses nearby: 0 to 1."""

    def __post_init__(self) -> None:
        if self.places_nearby < 0:
            raise ValueError(f"places nearby cannot be negative: {self.places_nearby}")
        if not 0 <= self.score <= 1:
            raise ValueError(f"job access score must be 0 to 1: {self.score}")

"""The soft preferences: one small class per preference (Strategy pattern).

Each scorer turns one aspect of an area into a value from 0 (worst) to 1 (best)
and a sentence that explains it. A new preference is a new class here plus an
entry in `default_scorers`; the ranking service does not change.
"""

from collections.abc import Sequence
from decimal import Decimal

from domain.area import AreaFacts
from domain.constraints import Constraints
from domain.place import AMENITY_CATEGORIES, PlaceCategory
from domain.score import ScoreComponent
from domain.unknown import UNKNOWN
from ports.scorer import Scorer

CELL_AREA_KM2 = 0.7
"""Approximate area of one resolution-8 hexagon at German latitudes."""

FULL_MARKS_RENT_SHARE = 0.5
"""A rent at this share of the ceiling, or lower, gets the full score."""

HALF_MARKS_AMENITIES_PER_KM2 = 7.0
"""An area with this many everyday amenities per square kilometre scores 0.5."""

# Singular and plural, in the order they are listed in a reason.
_NAMES = {
    PlaceCategory.SUPERMARKET: ("supermarket", "supermarkets"),
    PlaceCategory.CAFE: ("cafe", "cafes"),
    PlaceCategory.LIBRARY: ("library", "libraries"),
    PlaceCategory.GYM: ("gym", "gyms"),
}


def _counted(count: int, category: PlaceCategory) -> str:
    singular, plural = _NAMES[category]
    return f"{count} {singular if count == 1 else plural}"


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


class CommuteScorer(Scorer):
    """Shorter is better: 1 at the doorstep, 0 at the student's own limit."""

    def __init__(self, limit_minutes: int) -> None:
        self._limit = limit_minutes

    @property
    def name(self) -> str:
        return "commute"

    def score(self, facts: AreaFacts) -> ScoreComponent:
        minutes = facts.commute_minutes
        if minutes is UNKNOWN:
            return ScoreComponent(self.name, UNKNOWN, "The commute to campus is unknown.")
        spare = self._limit - minutes
        margin = (
            f"{spare} min under your {self._limit} min limit"
            if spare >= 0
            else f"{-spare} min over your {self._limit} min limit"
        )
        return ScoreComponent(
            self.name,
            _clamp(1 - minutes / self._limit),
            f"{minutes} min to campus by public transport, {margin}.",
        )


class RentScorer(Scorer):
    """Cheaper is better: 0 at the student's ceiling, 1 at half the ceiling or less."""

    def __init__(self, ceiling_eur: Decimal) -> None:
        self._ceiling = ceiling_eur

    @property
    def name(self) -> str:
        return "rent"

    def score(self, facts: AreaFacts) -> ScoreComponent:
        rent = facts.rent
        if rent is UNKNOWN:
            return ScoreComponent(self.name, UNKNOWN, "The rent level is unknown.")
        saving = self._ceiling - rent.monthly_eur
        margin = (
            f"{saving:.0f} EUR under your {self._ceiling:.0f} EUR ceiling"
            if saving >= 0
            else f"{-saving:.0f} EUR over your {self._ceiling:.0f} EUR ceiling"
        )
        # The figure is never shown without saying where it comes from.
        origin = "placeholder figure" if rent.is_sample else f"{rent.source}, {rent.as_of}"
        return ScoreComponent(
            self.name,
            _clamp(float(saving / (self._ceiling * Decimal(str(FULL_MARKS_RENT_SHARE))))),
            f"Rent about {rent.monthly_eur:.0f} EUR a month, {margin} ({origin}).",
        )


class AmenityScorer(Scorer):
    """More everyday amenities per square kilometre is better, with diminishing returns."""

    @property
    def name(self) -> str:
        return "amenities"

    def score(self, facts: AreaFacts) -> ScoreComponent:
        counts = facts.amenity_counts
        if counts is UNKNOWN or facts.cell_count == 0:
            return ScoreComponent(self.name, UNKNOWN, "Everyday amenities are unknown.")
        total = sum(counts.get(category, 0) for category in AMENITY_CATEGORIES)
        per_km2 = total / (facts.cell_count * CELL_AREA_KM2)
        breakdown = ", ".join(_counted(counts.get(category, 0), category) for category in _NAMES)
        # density / (density + half) rises quickly at first and levels off: the
        # twentieth cafe matters less than the first.
        return ScoreComponent(
            self.name,
            per_km2 / (per_km2 + HALF_MARKS_AMENITIES_PER_KM2),
            f"{total} everyday amenities ({breakdown}), about {per_km2:.0f} per km².",
        )


class JobAccessScorer(Scorer):
    """More student-type employers nearby is better. A proxy, not a count of vacancies."""

    @property
    def name(self) -> str:
        return "job_access"

    def score(self, facts: AreaFacts) -> ScoreComponent:
        access = facts.job_access
        if access is UNKNOWN:
            return ScoreComponent(self.name, UNKNOWN, "Part-time job access is unknown.")
        return ScoreComponent(
            self.name,
            access.score,
            f"About {access.places_nearby} cafes, restaurants, bars and shops within 2 km, "
            f"more than in {access.score:.0%} of the city.",
        )


def default_scorers(constraints: Constraints) -> Sequence[Scorer]:
    """The scorers of a search. Two of them are measured against the student's own limits."""
    return (
        CommuteScorer(constraints.max_commute_minutes),
        RentScorer(constraints.max_rent_eur),
        AmenityScorer(),
        JobAccessScorer(),
    )

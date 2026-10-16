"""What a search and a comparison return."""

from dataclasses import dataclass

from domain.area import AreaFacts
from domain.city import Campus, University
from domain.destination import Destination
from domain.score import Score
from domain.unknown import UNKNOWN, Unknown


@dataclass(frozen=True, slots=True)
class FullDayTravel:
    """Travel for a day with a job: home, campus, job, home.

    Shown when the student pins an employer. It informs; it never excludes an
    area and does not change its score.
    """

    employer: Destination
    home_to_campus: int | Unknown
    """Morning."""
    campus_to_job: int | Unknown
    """Afternoon, taken from the evening window."""
    job_to_home: int | Unknown
    """Evening."""
    campus_to_home: int | Unknown
    """Evening. The way home on a day without the job, used for comparison."""

    @property
    def total_minutes(self) -> int | Unknown:
        """All three legs of the day; UNKNOWN if any leg is."""
        legs = (self.home_to_campus, self.campus_to_job, self.job_to_home)
        if any(leg is UNKNOWN for leg in legs):
            return UNKNOWN
        return sum(leg for leg in legs if leg is not UNKNOWN)

    @property
    def extra_minutes(self) -> int | Unknown:
        """How much longer the day's travel is than home, campus, home."""
        total = self.total_minutes
        if total is UNKNOWN or self.home_to_campus is UNKNOWN or self.campus_to_home is UNKNOWN:
            return UNKNOWN
        return max(0, total - (self.home_to_campus + self.campus_to_home))


@dataclass(frozen=True, slots=True)
class RankedArea:
    """An area that meets every hard constraint, with its score explained."""

    rank: int
    facts: AreaFacts
    score: Score
    reasons: tuple[str, ...]
    """One sentence per preference, the one that helped the score most first."""
    trade_off: str
    """The area's weakest point: what the student gives up by choosing it."""
    full_day: FullDayTravel | None = None
    """Present only when an employer is pinned."""


@dataclass(frozen=True, slots=True)
class ExcludedArea:
    facts: AreaFacts
    violations: tuple[str, ...]
    """Which limits the area breaks."""


@dataclass(frozen=True, slots=True)
class UncheckedArea:
    """An area that breaks no limit as far as is known, but a figure needed to
    check one is missing. It is not ranked and not silently dropped."""

    facts: AreaFacts
    missing: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SearchResult:
    city_id: str
    campus: Campus
    ranked: tuple[RankedArea, ...]
    excluded: tuple[ExcludedArea, ...]
    unchecked: tuple[UncheckedArea, ...]


@dataclass(frozen=True, slots=True)
class AreaDetail:
    """One area looked at closely, optionally in relation to a campus."""

    facts: AreaFacts
    campus: Campus | None
    return_minutes: int | Unknown
    """Evening travel from the campus back to the area; UNKNOWN without a campus."""


@dataclass(frozen=True, slots=True)
class CampusFeasibility:
    """How many areas work for one campus under a rent and commute limit."""

    campus: Campus
    feasible_area_ids: frozenset[int]
    excluded: int
    unchecked: int

    @property
    def feasible(self) -> int:
        return len(self.feasible_area_ids)


@dataclass(frozen=True, slots=True)
class UniversityFeasibility:
    university: University
    campuses: tuple[CampusFeasibility, ...]

    @property
    def feasible(self) -> int:
        """Areas that work for at least one of the university's campuses."""
        areas: set[int] = set()
        for campus in self.campuses:
            areas |= campus.feasible_area_ids
        return len(areas)


@dataclass(frozen=True, slots=True)
class CityComparison:
    city_id: str
    total_areas: int
    universities: tuple[UniversityFeasibility, ...]

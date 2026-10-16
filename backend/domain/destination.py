"""Places a student travels to."""

from dataclasses import dataclass
from datetime import date
from enum import StrEnum

from domain.geo import Coordinate


class DestinationKind(StrEnum):
    CAMPUS = "campus"
    JOB_HOTSPOT = "job_hotspot"
    """A cluster of businesses that typically hire students."""
    EMPLOYER = "employer"
    """A curated corporate site a student can pin."""


@dataclass(frozen=True, slots=True)
class Destination:
    """Anything travel times are computed to.

    Campuses, job hotspots and employer sites share this one shape, so the
    travel-time table and the commute code treat them alike.
    """

    id: int
    city_id: str
    kind: DestinationKind
    name: str
    location: Coordinate
    source: str | None = None
    as_of: date | None = None
    is_sample: bool = False
    """True for placeholder entries that real data must replace."""

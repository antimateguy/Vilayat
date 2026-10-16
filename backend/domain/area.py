"""Areas (neighbourhoods): the unit the product ranks."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from domain.place import JobAccess, PlaceCategory
from domain.unknown import Unknown


@dataclass(frozen=True, slots=True)
class Area:
    id: int
    city_id: str
    name: str


@dataclass(frozen=True, slots=True)
class RentEstimate:
    """An area-level rent estimate together with where it came from."""

    monthly_eur: Decimal
    basis: str
    """What the figure measures, for example "median asking rent, 1-room flat"."""
    source: str
    source_url: str | None
    as_of: date
    is_sample: bool
    """True for placeholder fixture data that real data must replace."""

    def __post_init__(self) -> None:
        if self.monthly_eur <= 0:
            raise ValueError(f"rent must be positive: {self.monthly_eur}")


@dataclass(frozen=True, slots=True)
class AreaFacts:
    """Everything the engine knows about one area for one search.

    Scorers and constraint checks read from this; they never query data sources
    themselves.
    """

    area: Area
    cell_count: int
    """Number of hexagon cells in the area: a measure of its size."""
    rent: RentEstimate | Unknown
    commute_minutes: int | Unknown
    """Public-transport minutes from the area to the chosen campus on a weekday morning."""
    amenity_counts: Mapping[PlaceCategory, int] | Unknown
    """Places per amenity category; a category that is absent means none.
    UNKNOWN when no places data is loaded for the city at all."""
    job_access: JobAccess | Unknown

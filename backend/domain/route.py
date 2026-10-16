"""One typical journey from an area to a campus, step by step.

The travel times behind the ranking are medians over many departures and many
starting points, so they say how long but not how. A stored route shows one
concrete journey that matches the area's typical time: walk to a stop, ride a
line, change, walk to the campus.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from domain.geo import Coordinate


class LegMode(StrEnum):
    WALK = "walk"
    BUS = "bus"
    TRAM = "tram"
    SUBWAY = "subway"
    """U-Bahn."""
    RAIL = "rail"
    """S-Bahn and regional trains."""
    FERRY = "ferry"
    OTHER = "other"

    @property
    def is_transit(self) -> bool:
        return self is not LegMode.WALK


@dataclass(frozen=True, slots=True)
class RouteLeg:
    mode: LegMode
    minutes: int
    """Time moving on this leg, rounded to whole minutes."""
    wait_minutes: int
    """Time spent waiting before this leg starts, for example on the platform."""
    distance_m: int
    path: tuple[Coordinate, ...]
    line: str | None = None
    """The line's public name, such as "U2" or "Bus 53"; None for walking."""
    from_stop: str | None = None
    to_stop: str | None = None
    line_colour: str | None = None
    """The line's colour from the timetable, as "#RRGGBB", when the timetable
    gives a real one; the map otherwise uses a colour per mode."""


@dataclass(frozen=True, slots=True)
class CommuteRoute:
    area_id: int
    destination_id: int
    cell_id: str
    """The hexagon the journey starts from: the one whose time is closest to
    the area's median, so the journey is typical, not the best case."""
    departs_at: datetime
    """Local time on the timetable day the journey was planned for."""
    total_minutes: int
    legs: tuple[RouteLeg, ...]
    computed_at: datetime

    @property
    def lines(self) -> tuple[str, ...]:
        return tuple(leg.line for leg in self.legs if leg.line)


@dataclass(frozen=True, slots=True)
class DestinationRoute:
    """A typical afternoon journey between two destinations, for example from a
    campus to the employer a student has pinned (the middle leg of a day)."""

    from_destination_id: int
    to_destination_id: int
    departs_at: datetime
    total_minutes: int
    legs: tuple[RouteLeg, ...]
    computed_at: datetime


@dataclass(frozen=True, slots=True)
class CommuteSpread:
    """How the typical commute varies inside one area."""

    cells: int
    """Hexagons of the area with a journey within the limit."""
    fastest: int
    median: int
    slowest: int

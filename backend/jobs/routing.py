"""The routing interface the travel-time job depends on.

The job knows only this interface. The real implementation (`jobs.r5_router`)
wraps the R5 routing engine and needs Java and the full feeds; tests use a small
fake, so they need neither.
"""

from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

from domain.geo import Coordinate


@dataclass(frozen=True)
class RoutePoint:
    id: str
    location: Coordinate


@dataclass(frozen=True)
class DepartureWindow:
    """Leave at any minute from `start` for `duration`; results are the median
    over those departures, so they include a typical wait for the first vehicle."""

    start: datetime
    duration: timedelta


class Router(ABC):
    @abstractmethod
    def travel_minutes(
        self,
        origins: Sequence[RoutePoint],
        destinations: Sequence[RoutePoint],
        departure: DepartureWindow,
        max_minutes: int,
    ) -> dict[tuple[str, str], int]:
        """Door-to-door public-transport minutes, keyed by (origin id, destination id).

        Walking to the first stop, waiting, riding, changing and walking from the
        last stop are all included. A pair with no journey within `max_minutes`
        is absent from the result.
        """


@dataclass(frozen=True)
class PlannedLeg:
    """One leg of a journey as the routing engine reports it."""

    mode: str
    """The engine's mode name: WALK, BUS, TRAM, SUBWAY, RAIL, FERRY and so on."""
    travel_seconds: float
    wait_seconds: float
    distance_m: float
    path: tuple[tuple[float, float], ...]
    """(longitude, latitude) points along the leg."""
    route_id: str | None = None
    """The GTFS route_id of a public-transport leg."""
    departure: datetime | None = None
    """When the leg starts, if the engine says; walking-only journeys have none."""

    @property
    def total_seconds(self) -> float:
        return self.travel_seconds + self.wait_seconds


type Itinerary = tuple[PlannedLeg, ...]


class ItineraryPlanner(ABC):
    @abstractmethod
    def itineraries(
        self,
        pairs: Sequence[tuple[RoutePoint, RoutePoint]],
        departure: DepartureWindow,
        max_minutes: int,
    ) -> dict[tuple[str, str], list[Itinerary]]:
        """Journey options for each (origin, destination) pair, keyed by their ids.

        Several options per pair: different departures within the window, and
        walking all the way. A pair with no journey is absent.
        """

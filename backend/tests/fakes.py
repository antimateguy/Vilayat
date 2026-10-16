"""Small stand-ins for slow or external collaborators, shared by the tests."""

from collections.abc import Sequence
from datetime import timedelta

from jobs.routing import (
    DepartureWindow,
    Itinerary,
    ItineraryPlanner,
    PlannedLeg,
    RoutePoint,
    Router,
)


class StraightLineRouter(Router):
    """A toy network: 5 minutes to get going, then 4 minutes per kilometre as the
    crow flies. Evening journeys take 3 minutes longer, so a test can tell the
    two windows and directions apart. Records every call it receives.
    """

    def __init__(self) -> None:
        self.calls: list[tuple[list[str], list[str], DepartureWindow]] = []

    def travel_minutes(
        self,
        origins: Sequence[RoutePoint],
        destinations: Sequence[RoutePoint],
        departure: DepartureWindow,
        max_minutes: int,
    ) -> dict[tuple[str, str], int]:
        self.calls.append(([o.id for o in origins], [d.id for d in destinations], departure))
        evening_extra = 3 if departure.start.hour >= 12 else 0
        result = {}
        for origin in origins:
            for destination in destinations:
                kilometres = origin.location.distance_km(destination.location)
                minutes = 5 + round(4 * kilometres) + evening_extra
                if minutes <= max_minutes:
                    result[origin.id, destination.id] = minutes
        return result


class TwoOptionPlanner(ItineraryPlanner):
    """For every pair: walking all the way (60 minutes), or a 20-minute journey of
    5 minutes' walk, 2 minutes' wait, 10 minutes on line R1 and 3 minutes' walk."""

    def __init__(self) -> None:
        self.calls: list[list[tuple[str, str]]] = []

    def itineraries(
        self,
        pairs: Sequence[tuple[RoutePoint, RoutePoint]],
        departure: DepartureWindow,
        max_minutes: int,
    ) -> dict[tuple[str, str], list[Itinerary]]:
        self.calls.append([(origin.id, target.id) for origin, target in pairs])
        result: dict[tuple[str, str], list[Itinerary]] = {}
        for origin, target in pairs:
            start = (origin.location.lon, origin.location.lat)
            stop_a, stop_b = (11.570, 48.140), (11.579, 48.149)
            end = (target.location.lon, target.location.lat)
            walk = PlannedLeg("WALK", 3600, 0, 4000, (start, end))
            ride = (
                PlannedLeg("WALK", 300, 0, 400, (start, stop_a)),
                PlannedLeg(
                    "BUS",
                    600,
                    120,
                    3000,
                    (stop_a, stop_b),
                    route_id="R1",
                    departure=departure.start + timedelta(minutes=12),
                ),
                PlannedLeg("WALK", 180, 0, 200, (stop_b, end)),
            )
            result[origin.id, target.id] = [(walk,), ride]
        return result

"""Port for the stored typical journeys and the spread of commute times in an area."""

from abc import ABC, abstractmethod

from domain.route import CommuteRoute, CommuteSpread, DestinationRoute


class CommuteRouteRepository(ABC):
    @abstractmethod
    def route(self, area_id: int, destination_id: int) -> CommuteRoute | None:
        """The stored typical morning journey, if the offline job found one."""

    @abstractmethod
    def between(self, from_destination_id: int, to_destination_id: int) -> DestinationRoute | None:
        """The stored typical afternoon journey from one destination to another."""

    @abstractmethod
    def spread(self, area_id: int, destination_id: int) -> CommuteSpread | None:
        """Fastest, median and slowest morning time over the area's hexagons;
        None when no hexagon of the area has a journey."""

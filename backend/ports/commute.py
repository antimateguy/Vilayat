"""Port for public-transport travel times."""

from abc import ABC, abstractmethod
from collections.abc import Mapping
from datetime import datetime

from domain.travel import TimeWindow
from domain.unknown import Unknown


class CommuteProvider(ABC):
    """Answers "how long from here to that destination".

    The interface says nothing about where the numbers come from: today a table
    filled by an offline job, later possibly a live routing service.
    """

    @abstractmethod
    def minutes_by_cell(self, destination_id: int, window: TimeWindow) -> Mapping[str, int]:
        """Minutes from each H3 cell to the destination.

        Cells with no route in the window are absent.
        """

    @abstractmethod
    def minutes_by_area(
        self, destination_id: int, window: TimeWindow
    ) -> Mapping[int, int | Unknown]:
        """Typical minutes from each area of the destination's city, keyed by area id.

        The figure is the median over the area's cells that have a route. Every
        area of the city is present; one with no routed cell maps to UNKNOWN.
        """

    @abstractmethod
    def minutes_between(
        self, from_destination_id: int, to_destination_id: int, window: TimeWindow
    ) -> int | Unknown:
        """Minutes from one destination to another, for example campus to employer.

        UNKNOWN when no journey between the two is stored.
        """

    @abstractmethod
    def last_computed(self, city_id: str) -> datetime | Unknown:
        """When the city's travel times were last computed; UNKNOWN if there are none."""

"""Port for area-level rent estimates."""

from abc import ABC, abstractmethod
from collections.abc import Mapping

from domain.area import RentEstimate
from domain.unknown import Unknown


class RentProvider(ABC):
    @abstractmethod
    def rents_by_area(self, city_id: str) -> Mapping[int, RentEstimate | Unknown]:
        """The latest rent estimate of every area in the city, keyed by area id.

        Every area of the city is present; one without a figure maps to UNKNOWN.
        """

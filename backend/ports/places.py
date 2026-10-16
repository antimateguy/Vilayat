"""Port for points of interest (amenities and student employers)."""

from abc import ABC, abstractmethod
from collections.abc import Collection, Mapping
from datetime import date

from domain.place import JobAccess, PlaceCategory
from domain.unknown import Unknown


class PlacesRepository(ABC):
    @abstractmethod
    def counts_by_area(
        self, city_id: str, categories: Collection[PlaceCategory]
    ) -> Mapping[int, Mapping[PlaceCategory, int]]:
        """Number of places per category in each area, keyed by area id.

        Only areas and categories with at least one place appear.
        """

    @abstractmethod
    def counts_by_cell(
        self, city_id: str, categories: Collection[PlaceCategory]
    ) -> Mapping[str, Mapping[PlaceCategory, int]]:
        """Number of places per category in each H3 cell, keyed by cell index.

        Only cells and categories with at least one place appear.
        """

    @abstractmethod
    def snapshot_date(self, city_id: str) -> date | Unknown:
        """The date the city's places were taken from OpenStreetMap.

        UNKNOWN when no places have been loaded. Callers use this to tell "no
        cafes here" (a real zero) from "no data for this city".
        """

    @abstractmethod
    def job_access_by_cell(self, city_id: str) -> Mapping[str, JobAccess]:
        """Job access of each H3 cell. Cells without a computed score are absent."""

    @abstractmethod
    def job_access_by_area(self, city_id: str) -> Mapping[int, JobAccess | Unknown]:
        """Typical job access of each area: the median over its cells.

        Every area of the city is present; one without a scored cell maps to UNKNOWN.
        """

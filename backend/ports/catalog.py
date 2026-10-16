"""Port for the fixed reference data: cities, universities, campuses, destinations."""

from abc import ABC, abstractmethod
from collections.abc import Sequence

from domain.city import Campus, City, University
from domain.destination import Destination, DestinationKind


class CatalogRepository(ABC):
    @abstractmethod
    def list_cities(self) -> Sequence[City]: ...

    @abstractmethod
    def list_universities(self, city_id: str) -> Sequence[University]: ...

    @abstractmethod
    def list_campuses(self, university_id: int) -> Sequence[Campus]: ...

    @abstractmethod
    def get_campus(self, campus_id: int) -> Campus | None: ...

    @abstractmethod
    def list_destinations(self, city_id: str, kind: DestinationKind) -> Sequence[Destination]: ...

    @abstractmethod
    def get_destination(self, destination_id: int) -> Destination | None: ...

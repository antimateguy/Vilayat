"""Port for areas (neighbourhoods) and the hexagon cells that cover them."""

from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence

from domain.area import Area
from domain.geo import GeoJsonGeometry


class AreaRepository(ABC):
    @abstractmethod
    def list_by_city(self, city_id: str) -> Sequence[Area]: ...

    @abstractmethod
    def get(self, area_id: int) -> Area | None: ...

    @abstractmethod
    def cells_by_area(self, city_id: str) -> Mapping[int, Sequence[str]]:
        """H3 cell indexes of every area in the city, keyed by area id.

        An area with no cells maps to an empty sequence.
        """

    @abstractmethod
    def outlines(self, city_id: str) -> Mapping[int, GeoJsonGeometry]:
        """The boundary of every area in the city for drawing on a map, keyed by area id.

        Simplified for display: precise enough to look right, small enough to send.
        """

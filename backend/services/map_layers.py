"""Map layers: the figures behind the area shading and the hexagon heatmaps."""

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum

from domain.area import AreaFacts
from domain.geo import GeoJsonGeometry
from domain.place import AMENITY_CATEGORIES
from domain.travel import TimeWindow
from domain.unknown import UNKNOWN, Unknown
from ports.areas import AreaRepository
from ports.catalog import CatalogRepository
from ports.commute import CommuteProvider
from ports.places import PlacesRepository
from services.errors import InvalidRequestError
from services.facts import AreaFactsCollector
from services.lookup import campus_and_city, require_city
from services.timing import stage


class CellMetric(StrEnum):
    COMMUTE = "commute"
    """Morning minutes to a campus."""
    AMENITIES = "amenities"
    """Supermarkets, cafes, libraries and gyms in the cell."""
    JOB_ACCESS = "job_access"
    """Service-job access score, 0 to 1."""


@dataclass(frozen=True, slots=True)
class AreaShape:
    facts: AreaFacts
    outline: GeoJsonGeometry


@dataclass(frozen=True, slots=True)
class CellValue:
    cell: str
    area_id: int
    value: float | Unknown


class MapLayerService:
    def __init__(
        self,
        catalog: CatalogRepository,
        areas: AreaRepository,
        facts: AreaFactsCollector,
        commute: CommuteProvider,
        places: PlacesRepository,
    ) -> None:
        self._catalog = catalog
        self._areas = areas
        self._facts = facts
        self._commute = commute
        self._places = places

    def areas(self, city_id: str, campus_id: int | None = None) -> list[AreaShape]:
        """Every area of the city with its outline and facts."""
        require_city(self._catalog, city_id)
        destination_id = self._campus_destination(campus_id, city_id)
        with stage("facts"):
            facts = self._facts.collect(city_id, destination_id)
        with stage("outlines"):
            outlines = self._areas.outlines(city_id)
        return [
            AreaShape(facts=item, outline=outlines[item.area.id])
            for item in facts
            if item.area.id in outlines
        ]

    def cells(
        self, city_id: str, metric: CellMetric, campus_id: int | None = None
    ) -> list[CellValue]:
        """One value per hexagon cell of the city. A cell without a figure is UNKNOWN."""
        require_city(self._catalog, city_id)
        if metric is CellMetric.COMMUTE and campus_id is None:
            raise InvalidRequestError("the commute layer needs a campus_id")
        destination_id = self._campus_destination(campus_id, city_id)

        with stage("cells"):
            cells = self._areas.cells_by_area(city_id)
        with stage("values"):
            values = self._values(city_id, metric, destination_id)
        return [
            CellValue(cell=cell, area_id=area_id, value=values.get(cell, UNKNOWN))
            for area_id, area_cells in cells.items()
            for cell in area_cells
        ]

    def _values(
        self, city_id: str, metric: CellMetric, destination_id: int | None
    ) -> Mapping[str, float | Unknown]:
        if metric is CellMetric.COMMUTE and destination_id is not None:
            return self._commute.minutes_by_cell(destination_id, TimeWindow.WEEKDAY_MORNING)
        if metric is CellMetric.JOB_ACCESS:
            return {
                cell: access.score
                for cell, access in self._places.job_access_by_cell(city_id).items()
            }
        if self._places.snapshot_date(city_id) is UNKNOWN:
            return {}
        # With a places snapshot, a cell that is not in the counts really has none.
        counts = self._places.counts_by_cell(city_id, AMENITY_CATEGORIES)
        all_cells = (c for cells in self._areas.cells_by_area(city_id).values() for c in cells)
        return {cell: float(sum(counts.get(cell, {}).values())) for cell in all_cells}

    def _campus_destination(self, campus_id: int | None, city_id: str) -> int | None:
        if campus_id is None:
            return None
        campus, campus_city = campus_and_city(self._catalog, campus_id)
        if campus_city != city_id:
            raise InvalidRequestError(f"campus {campus_id} is in {campus_city}, not in {city_id}")
        return campus.destination_id

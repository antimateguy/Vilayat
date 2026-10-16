"""In-memory implementations of the data ports.

They hold plain dictionaries and follow the same contracts as the PostgreSQL
repositories (every area present, UNKNOWN for a missing figure), so the services
can be tested with no database and no network.
"""

from collections.abc import Collection, Mapping, Sequence
from datetime import date, datetime

from domain.area import Area, RentEstimate
from domain.city import Campus, City, University
from domain.destination import Destination, DestinationKind
from domain.geo import GeoJsonGeometry
from domain.place import JobAccess, PlaceCategory
from domain.travel import TimeWindow
from domain.unknown import UNKNOWN, Unknown
from ports.areas import AreaRepository
from ports.catalog import CatalogRepository
from ports.commute import CommuteProvider
from ports.places import PlacesRepository
from ports.rent import RentProvider


class InMemoryCatalog(CatalogRepository):
    def __init__(
        self,
        cities: Sequence[City] = (),
        universities: Sequence[University] = (),
        campuses: Sequence[Campus] = (),
        destinations: Sequence[Destination] = (),
    ) -> None:
        self._cities = list(cities)
        self._universities = list(universities)
        self._campuses = list(campuses)
        self._destinations = list(destinations)

    def list_cities(self) -> Sequence[City]:
        return sorted(self._cities, key=lambda city: city.name)

    def list_universities(self, city_id: str) -> Sequence[University]:
        return sorted((u for u in self._universities if u.city_id == city_id), key=lambda u: u.name)

    def list_campuses(self, university_id: int) -> Sequence[Campus]:
        return sorted(
            (c for c in self._campuses if c.university_id == university_id), key=lambda c: c.name
        )

    def get_campus(self, campus_id: int) -> Campus | None:
        return next((c for c in self._campuses if c.id == campus_id), None)

    def list_destinations(self, city_id: str, kind: DestinationKind) -> Sequence[Destination]:
        return sorted(
            (d for d in self._destinations if d.city_id == city_id and d.kind is kind),
            key=lambda d: d.name,
        )

    def get_destination(self, destination_id: int) -> Destination | None:
        return next((d for d in self._destinations if d.id == destination_id), None)


class InMemoryAreas(AreaRepository):
    def __init__(
        self, areas: Sequence[Area], cells: Mapping[int, Sequence[str]] | None = None
    ) -> None:
        self._areas = list(areas)
        self._cells = dict(cells or {})

    def list_by_city(self, city_id: str) -> Sequence[Area]:
        return sorted((a for a in self._areas if a.city_id == city_id), key=lambda a: a.name)

    def get(self, area_id: int) -> Area | None:
        return next((a for a in self._areas if a.id == area_id), None)

    def cells_by_area(self, city_id: str) -> Mapping[int, Sequence[str]]:
        return {area.id: self._cells.get(area.id, ()) for area in self.list_by_city(city_id)}

    def outlines(self, city_id: str) -> Mapping[int, GeoJsonGeometry]:
        """Every area is the same small square: enough to test the map endpoints."""
        ring = [[11.5, 48.1], [11.6, 48.1], [11.6, 48.2], [11.5, 48.2], [11.5, 48.1]]
        return {
            area.id: {"type": "MultiPolygon", "coordinates": [[ring]]}
            for area in self.list_by_city(city_id)
        }


class InMemoryRents(RentProvider):
    def __init__(self, areas: AreaRepository, rents: Mapping[int, RentEstimate]) -> None:
        self._areas = areas
        self._rents = dict(rents)

    def rents_by_area(self, city_id: str) -> Mapping[int, RentEstimate | Unknown]:
        return {
            area.id: self._rents.get(area.id, UNKNOWN) for area in self._areas.list_by_city(city_id)
        }


class InMemoryCommute(CommuteProvider):
    """`by_area` is keyed by (destination id, window), `between` by (from, to, window)."""

    def __init__(
        self,
        by_area: Mapping[tuple[int, TimeWindow], Mapping[int, int]] | None = None,
        between: Mapping[tuple[int, int, TimeWindow], int] | None = None,
        by_cell: Mapping[tuple[int, TimeWindow], Mapping[str, int]] | None = None,
        area_ids: Collection[int] = (),
    ) -> None:
        self._by_area = dict(by_area or {})
        self._between = dict(between or {})
        self._by_cell = dict(by_cell or {})
        self._area_ids = list(area_ids)
        self.computed_at: datetime | None = None

    def minutes_by_cell(self, destination_id: int, window: TimeWindow) -> Mapping[str, int]:
        return self._by_cell.get((destination_id, window), {})

    def minutes_by_area(
        self, destination_id: int, window: TimeWindow
    ) -> Mapping[int, int | Unknown]:
        known = self._by_area.get((destination_id, window), {})
        return {area_id: known.get(area_id, UNKNOWN) for area_id in self._area_ids}

    def minutes_between(
        self, from_destination_id: int, to_destination_id: int, window: TimeWindow
    ) -> int | Unknown:
        return self._between.get((from_destination_id, to_destination_id, window), UNKNOWN)

    def last_computed(self, city_id: str) -> datetime | Unknown:
        return self.computed_at or UNKNOWN


class InMemoryPlaces(PlacesRepository):
    """Without a snapshot date the city has no places data at all."""

    def __init__(
        self,
        snapshot: date | None = None,
        counts: Mapping[int, Mapping[PlaceCategory, int]] | None = None,
        job_access: Mapping[int, JobAccess] | None = None,
        area_ids: Collection[int] = (),
        cell_counts: Mapping[str, Mapping[PlaceCategory, int]] | None = None,
        cell_job_access: Mapping[str, JobAccess] | None = None,
    ) -> None:
        self._snapshot = snapshot
        self._counts = dict(counts or {})
        self._job_access = dict(job_access or {})
        self._area_ids = list(area_ids)
        self._cell_counts = dict(cell_counts or {})
        self._cell_job_access = dict(cell_job_access or {})

    def counts_by_area(
        self, city_id: str, categories: Collection[PlaceCategory]
    ) -> Mapping[int, Mapping[PlaceCategory, int]]:
        return {
            area_id: {c: n for c, n in counts.items() if c in categories}
            for area_id, counts in self._counts.items()
        }

    def counts_by_cell(
        self, city_id: str, categories: Collection[PlaceCategory]
    ) -> Mapping[str, Mapping[PlaceCategory, int]]:
        return {
            cell: {c: n for c, n in counts.items() if c in categories}
            for cell, counts in self._cell_counts.items()
        }

    def snapshot_date(self, city_id: str) -> date | Unknown:
        return self._snapshot or UNKNOWN

    def job_access_by_cell(self, city_id: str) -> Mapping[str, JobAccess]:
        return self._cell_job_access

    def job_access_by_area(self, city_id: str) -> Mapping[int, JobAccess | Unknown]:
        return {area_id: self._job_access.get(area_id, UNKNOWN) for area_id in self._area_ids}

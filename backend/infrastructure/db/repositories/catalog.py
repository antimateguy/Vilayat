"""Cities, universities, campuses and destinations from PostgreSQL."""

from collections.abc import Sequence
from typing import Any

from sqlalchemy import Row, Select, func, select
from sqlalchemy.orm import Session

from domain.city import Campus, City, University
from domain.destination import Destination, DestinationKind
from domain.geo import Coordinate
from infrastructure.db.models import CampusRow, CityRow, DestinationRow, UniversityRow
from ports.catalog import CatalogRepository

# PostGIS stores a point as x = longitude, y = latitude.
_LAT = func.ST_Y(DestinationRow.geom)
_LON = func.ST_X(DestinationRow.geom)


def _campus_select() -> Select[*tuple[Any, ...]]:
    """A campus has no geometry of its own; its location is its destination's."""
    return select(
        CampusRow.id, CampusRow.university_id, CampusRow.name, CampusRow.destination_id, _LAT, _LON
    ).join(DestinationRow, DestinationRow.id == CampusRow.destination_id)


def _to_campus(row: Row[*tuple[Any, ...]]) -> Campus:
    campus_id, university_id, name, destination_id, lat, lon = row
    return Campus(
        id=campus_id,
        university_id=university_id,
        name=name,
        location=Coordinate(lat=lat, lon=lon),
        destination_id=destination_id,
    )


def _destination_select() -> Select[*tuple[Any, ...]]:
    return select(
        DestinationRow.id,
        DestinationRow.city_id,
        DestinationRow.kind,
        DestinationRow.name,
        _LAT,
        _LON,
        DestinationRow.source,
        DestinationRow.as_of,
        DestinationRow.is_sample,
    )


def _to_destination(row: Row[*tuple[Any, ...]]) -> Destination:
    destination_id, city_id, kind, name, lat, lon, source, as_of, is_sample = row
    return Destination(
        id=destination_id,
        city_id=city_id,
        kind=kind,
        name=name,
        location=Coordinate(lat=lat, lon=lon),
        source=source,
        as_of=as_of,
        is_sample=is_sample,
    )


class PostgresCatalogRepository(CatalogRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_cities(self) -> Sequence[City]:
        rows = self._session.execute(select(CityRow.id, CityRow.name).order_by(CityRow.name))
        return [City(id=city_id, name=name) for city_id, name in rows]

    def list_universities(self, city_id: str) -> Sequence[University]:
        statement = (
            select(UniversityRow.id, UniversityRow.name, UniversityRow.short_name)
            .where(UniversityRow.city_id == city_id)
            .order_by(UniversityRow.name)
        )
        return [
            University(id=university_id, city_id=city_id, name=name, short_name=short_name)
            for university_id, name, short_name in self._session.execute(statement)
        ]

    def list_campuses(self, university_id: int) -> Sequence[Campus]:
        statement = (
            _campus_select()
            .where(CampusRow.university_id == university_id)
            .order_by(CampusRow.name)
        )
        return [_to_campus(row) for row in self._session.execute(statement)]

    def get_campus(self, campus_id: int) -> Campus | None:
        row = self._session.execute(_campus_select().where(CampusRow.id == campus_id)).first()
        return _to_campus(row) if row else None

    def list_destinations(self, city_id: str, kind: DestinationKind) -> Sequence[Destination]:
        statement = (
            _destination_select()
            .where(DestinationRow.city_id == city_id, DestinationRow.kind == kind)
            .order_by(DestinationRow.name)
        )
        return [_to_destination(row) for row in self._session.execute(statement)]

    def get_destination(self, destination_id: int) -> Destination | None:
        statement = _destination_select().where(DestinationRow.id == destination_id)
        row = self._session.execute(statement).first()
        return _to_destination(row) if row else None

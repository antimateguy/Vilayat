"""Areas and their cells from PostgreSQL."""

import json
from collections.abc import Mapping, Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from domain.area import Area
from domain.geo import GeoJsonGeometry
from infrastructure.db.models import CellRow, NeighbourhoodRow
from ports.areas import AreaRepository

# About 10 m: invisible at city zoom, and it cuts the Berlin layer to a fraction.
OUTLINE_TOLERANCE_DEGREES = 0.0001
OUTLINE_DECIMALS = 5


class PostgresAreaRepository(AreaRepository):
    """Selects only the columns an Area needs, never the boundary polygons,
    which are large and only wanted by the map layers."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def list_by_city(self, city_id: str) -> Sequence[Area]:
        statement = (
            select(NeighbourhoodRow.id, NeighbourhoodRow.name)
            .where(NeighbourhoodRow.city_id == city_id)
            .order_by(NeighbourhoodRow.name)
        )
        return [
            Area(id=area_id, city_id=city_id, name=name)
            for area_id, name in self._session.execute(statement)
        ]

    def get(self, area_id: int) -> Area | None:
        statement = select(NeighbourhoodRow.city_id, NeighbourhoodRow.name).where(
            NeighbourhoodRow.id == area_id
        )
        row = self._session.execute(statement).first()
        if row is None:
            return None
        city_id, name = row
        return Area(id=area_id, city_id=city_id, name=name)

    def cells_by_area(self, city_id: str) -> Mapping[int, Sequence[str]]:
        # Outer join, so an area without cells still appears, with an empty list.
        statement = (
            select(NeighbourhoodRow.id, CellRow.h3_index)
            .outerjoin(CellRow, CellRow.neighbourhood_id == NeighbourhoodRow.id)
            .where(NeighbourhoodRow.city_id == city_id)
            .order_by(NeighbourhoodRow.id, CellRow.h3_index)
        )
        cells: dict[int, list[str]] = {}
        for area_id, h3_index in self._session.execute(statement):
            area_cells = cells.setdefault(area_id, [])
            if h3_index is not None:
                area_cells.append(h3_index)
        return cells

    def outlines(self, city_id: str) -> Mapping[int, GeoJsonGeometry]:
        # ST_Multi: simplifying can turn a one-part area into a plain Polygon, and
        # callers are promised a MultiPolygon every time.
        simplified = func.ST_Multi(
            func.ST_SimplifyPreserveTopology(NeighbourhoodRow.geom, OUTLINE_TOLERANCE_DEGREES)
        )
        statement = select(
            NeighbourhoodRow.id, func.ST_AsGeoJSON(simplified, OUTLINE_DECIMALS)
        ).where(NeighbourhoodRow.city_id == city_id)
        return {
            area_id: json.loads(geometry) for area_id, geometry in self._session.execute(statement)
        }

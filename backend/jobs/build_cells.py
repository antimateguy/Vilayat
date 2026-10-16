"""Cover each neighbourhood of a city with H3 hexagon cells (resolution 8).

Run for one city:  uv run python -m jobs.load_base_data --city berlin
"""

import logging
from collections import Counter
from collections.abc import Mapping

import h3
from geoalchemy2 import WKTElement
from geoalchemy2.shape import to_shape
from shapely.geometry.base import BaseGeometry
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from infrastructure.db.models import SRID_WGS84, CellRow, NeighbourhoodRow

logger = logging.getLogger(__name__)

H3_RESOLUTION = 8
"""A resolution-8 hexagon is about 0.7 km2, roughly 900 m across: a short walk."""


def assign_cells(areas: Mapping[int, BaseGeometry]) -> dict[str, int]:
    """Decide which area each cell belongs to. Returns {h3 index: area id}.

    A cell belongs to the area that contains its centre, so each cell is assigned
    exactly once. An area smaller than a cell can contain no cell centre; it then
    takes the cell around its own interior point from a neighbour, provided that
    neighbour has other cells left. Every area ends up with at least one cell.
    """
    assignment: dict[str, int] = {}
    for area_id, geometry in areas.items():
        for cell in h3.geo_to_cells(geometry, H3_RESOLUTION):
            assignment[cell] = area_id

    cell_counts = Counter(assignment.values())
    for area_id, geometry in areas.items():
        if cell_counts[area_id] > 0:
            continue
        point = geometry.representative_point()
        cell = h3.latlng_to_cell(point.y, point.x, H3_RESOLUTION)
        donor = assignment.get(cell)
        if donor is not None:
            if cell_counts[donor] <= 1:
                logger.warning("area %s is left without a cell", area_id)
                continue
            cell_counts[donor] -= 1
        assignment[cell] = area_id
        cell_counts[area_id] = 1
    return assignment


def build_cells(session: Session, city_id: str) -> int:
    """Create, re-assign and remove the city's cells to match its neighbourhoods.

    Cells that still exist are updated in place rather than deleted, because
    deleting a cell would also delete the travel times stored for it.
    """
    rows = session.execute(
        select(NeighbourhoodRow.id, NeighbourhoodRow.geom).where(
            NeighbourhoodRow.city_id == city_id
        )
    )
    assignment = assign_cells({area_id: to_shape(geom) for area_id, geom in rows})

    session.execute(
        delete(CellRow).where(CellRow.city_id == city_id, CellRow.h3_index.not_in(assignment))
    )
    if assignment:
        statement = insert(CellRow).values(
            [
                {
                    "h3_index": cell,
                    "city_id": city_id,
                    "neighbourhood_id": area_id,
                    "centroid": _centroid(cell),
                }
                for cell, area_id in assignment.items()
            ]
        )
        session.execute(
            statement.on_conflict_do_update(
                index_elements=["h3_index"],
                set_={"neighbourhood_id": statement.excluded.neighbourhood_id},
            )
        )
    logger.info("%s: built %d cells", city_id, len(assignment))
    return len(assignment)


def _centroid(cell: str) -> WKTElement:
    lat, lon = h3.cell_to_latlng(cell)
    return WKTElement(f"POINT({lon} {lat})", srid=SRID_WGS84)

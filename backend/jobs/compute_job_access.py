"""Compute the service-job access of every cell of a city.

For each cell: count the businesses that typically hire students within two
rings of hexagons (about 2 km), then rank the cell against the rest of the city.
The result is a proxy for where such employers cluster, not a count of vacancies.

Run for one city:  uv run python -m jobs.load_base_data --city berlin
"""

import bisect
import logging
from collections import Counter
from collections.abc import Collection, Iterable

import h3
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from domain.place import STUDENT_JOB_CATEGORIES, JobAccess
from infrastructure.db.models import CellRow, PlaceRow
from jobs.build_cells import H3_RESOLUTION

logger = logging.getLogger(__name__)

NEARBY_RINGS = 2
"""Two rings around a resolution-8 cell reach about 2 km from its centre."""


def job_access(cells: Collection[str], job_place_cells: Iterable[str]) -> dict[str, JobAccess]:
    """Job access of each cell, given the cell every job-type business falls in.

    The score is the share of the other cells with fewer businesses nearby, so it
    is 0 for the least and 1 for the best-served cell and is not distorted by a
    few extreme city-centre values.
    """
    places_per_cell = Counter(job_place_cells)
    nearby = {
        cell: sum(places_per_cell[neighbour] for neighbour in h3.grid_disk(cell, NEARBY_RINGS))
        for cell in cells
    }
    ordered = sorted(nearby.values())
    others = max(len(ordered) - 1, 1)
    return {
        cell: JobAccess(places_nearby=count, score=bisect.bisect_left(ordered, count) / others)
        for cell, count in nearby.items()
    }


def compute_job_access(session: Session, city_id: str) -> int:
    """Write job access to the city's cells. Without any places the columns are
    cleared, which the application reports as UNKNOWN rather than as zero."""
    cells = list(session.scalars(select(CellRow.h3_index).where(CellRow.city_id == city_id)))
    has_places = session.scalar(
        select(func.count()).select_from(PlaceRow).where(PlaceRow.city_id == city_id)
    )
    if not cells or not has_places:
        session.execute(
            update(CellRow)
            .where(CellRow.city_id == city_id)
            .values(job_places_nearby=None, job_access_score=None)
        )
        logger.warning("%s: no places loaded, job access left unknown", city_id)
        return 0

    # Includes places just outside the city: they have no cell_id but they are
    # near the cells at the edge.
    coordinates = session.execute(
        select(func.ST_Y(PlaceRow.geom), func.ST_X(PlaceRow.geom)).where(
            PlaceRow.city_id == city_id, PlaceRow.category.in_(STUDENT_JOB_CATEGORIES)
        )
    )
    place_cells = (h3.latlng_to_cell(lat, lon, H3_RESOLUTION) for lat, lon in coordinates)
    access = job_access(cells, place_cells)

    session.execute(
        update(CellRow),
        [
            {"h3_index": cell, "job_places_nearby": a.places_nearby, "job_access_score": a.score}
            for cell, a in access.items()
        ],
    )
    logger.info("%s: computed job access for %d cells", city_id, len(access))
    return len(access)

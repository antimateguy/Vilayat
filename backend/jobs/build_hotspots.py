"""Derive job hotspots: the places in a city where student-type employers cluster.

Method (density peaks on the hexagon grid, no extra library needed):
1. Count the job-type businesses in each cell.
2. For each cell add up its own count and its six neighbours' (a cluster of 7 cells).
3. A cell is a hotspot when that cluster total is the highest within two rings
   around it and reaches a minimum. Peaks are therefore at least three cells
   apart, so one busy district gives one hotspot, not ten.
4. The hotspot sits at the business nearest the average position of its cluster.
   The average itself is not used: between two river banks it can fall in the
   water or on an island, where no journey can start or end.

Hotspots become destinations, so travel times to them are computed like those to
campuses.

Run for one city:  uv run python -m jobs.load_base_data --city berlin
"""

import logging
from collections import Counter, defaultdict
from collections.abc import Collection, Sequence
from dataclasses import dataclass
from datetime import date

import h3
from geoalchemy2.shape import from_shape
from shapely.geometry import Point
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from domain.destination import DestinationKind
from domain.geo import Coordinate
from domain.place import STUDENT_JOB_CATEGORIES
from infrastructure.db.models import (
    SRID_WGS84,
    CellRow,
    DestinationRow,
    NeighbourhoodRow,
    PlaceRow,
)
from jobs.build_cells import H3_RESOLUTION

logger = logging.getLogger(__name__)

MAX_HOTSPOTS = 10
MIN_CLUSTER_PLACES = 40
CLUSTER_RINGS = 1
SEPARATION_RINGS = 2
SOURCE = "Derived from OpenStreetMap places (density peaks on the H3 grid)"


@dataclass(frozen=True)
class Hotspot:
    cell: str
    places: int
    location: Coordinate


def find_hotspots(
    places: Sequence[Coordinate],
    city_cells: Collection[str],
    *,
    max_hotspots: int = MAX_HOTSPOTS,
    min_places: int = MIN_CLUSTER_PLACES,
) -> list[Hotspot]:
    """The strongest density peaks among the city's cells, strongest first."""
    by_cell: dict[str, list[Coordinate]] = defaultdict(list)
    for place in places:
        by_cell[h3.latlng_to_cell(place.lat, place.lon, H3_RESOLUTION)].append(place)
    per_cell = Counter({cell: len(members) for cell, members in by_cell.items()})

    def cluster_total(cell: str) -> int:
        return sum(per_cell[neighbour] for neighbour in h3.grid_disk(cell, CLUSTER_RINGS))

    totals = {cell: cluster_total(cell) for cell in city_cells}

    def strength(cell: str) -> tuple[int, int, str]:
        # Equal cluster totals are common (every neighbour of one busy cell has
        # the same total), so the cell's own count and then its index break ties.
        # Exactly one cell of a tied group can then be the peak.
        total = totals[cell] if cell in totals else cluster_total(cell)
        return (total, per_cell[cell], cell)

    def is_peak(cell: str) -> bool:
        own = strength(cell)
        return totals[cell] >= min_places and all(
            strength(neighbour) <= own for neighbour in h3.grid_disk(cell, SEPARATION_RINGS)
        )

    peaks = sorted((cell for cell in city_cells if is_peak(cell)), key=strength, reverse=True)
    hotspots = []
    for cell in peaks[:max_hotspots]:
        members = [p for n in h3.grid_disk(cell, CLUSTER_RINGS) for p in by_cell.get(n, ())]
        centre = Coordinate(
            lat=sum(p.lat for p in members) / len(members),
            lon=sum(p.lon for p in members) / len(members),
        )
        location = min(members, key=centre.distance_km)
        hotspots.append(Hotspot(cell=cell, places=totals[cell], location=location))
    return hotspots


def hotspot_names(area_names: Sequence[str]) -> list[str]:
    """Name each hotspot after its area; number the second and later ones in an area."""
    seen: Counter[str] = Counter()
    names = []
    for area in area_names:
        seen[area] += 1
        names.append(f"Job hotspot: {area}" + (f" {seen[area]}" if seen[area] > 1 else ""))
    return names


def build_hotspots(session: Session, city_id: str) -> int:
    """Replace the city's job-hotspot destinations.

    A hotspot that keeps its name keeps its row and id, so the travel times
    already computed for it stay valid.
    """
    area_of_cell = dict(
        session.execute(
            select(CellRow.h3_index, NeighbourhoodRow.name)
            .join(NeighbourhoodRow, NeighbourhoodRow.id == CellRow.neighbourhood_id)
            .where(CellRow.city_id == city_id)
        ).all()
    )
    job_places = (PlaceRow.city_id == city_id, PlaceRow.category.in_(STUDENT_JOB_CATEGORIES))
    places = [
        Coordinate(lat=lat, lon=lon)
        for lat, lon in session.execute(
            select(func.ST_Y(PlaceRow.geom), func.ST_X(PlaceRow.geom)).where(*job_places)
        )
    ]
    snapshot_date: date | None = session.scalar(select(func.max(PlaceRow.as_of)).where(*job_places))

    hotspots = find_hotspots(places, area_of_cell.keys())
    names = hotspot_names([area_of_cell[hotspot.cell] for hotspot in hotspots])

    is_hotspot = (
        DestinationRow.city_id == city_id,
        DestinationRow.kind == DestinationKind.JOB_HOTSPOT,
    )
    session.execute(delete(DestinationRow).where(*is_hotspot, DestinationRow.name.not_in(names)))
    existing = {row.name: row for row in session.scalars(select(DestinationRow).where(*is_hotspot))}
    for name, hotspot in zip(names, hotspots, strict=True):
        row = existing.get(name) or DestinationRow(
            city_id=city_id, kind=DestinationKind.JOB_HOTSPOT, name=name
        )
        row.geom = from_shape(Point(hotspot.location.lon, hotspot.location.lat), srid=SRID_WGS84)
        row.source = SOURCE
        row.source_url = None
        row.as_of = snapshot_date or date.today()
        row.is_sample = False
        session.add(row)
    session.flush()
    logger.info("%s: built %d job hotspots", city_id, len(hotspots))
    return len(hotspots)

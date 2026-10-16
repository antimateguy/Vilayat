"""Load a downloaded OpenStreetMap snapshot into the places table.

Works offline: it reads the files written by `jobs.fetch_osm_places`.

Run for one city:  uv run python -m jobs.load_base_data --city berlin
"""

import csv
import json
import logging
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import h3
from sqlalchemy import delete, insert, select
from sqlalchemy.orm import Session

from domain.geo import Coordinate
from domain.place import PlaceCategory
from infrastructure.db.models import Base, CellRow, PlaceRow
from jobs.build_cells import H3_RESOLUTION
from jobs.fetch_osm_places import OSM_DIR, metadata_file, places_file
from jobs.osm_tags import classify

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class OsmPlace:
    osm_type: str
    osm_id: int
    name: str | None
    category: PlaceCategory
    location: Coordinate


@dataclass(frozen=True)
class PlacesSnapshot:
    places: list[OsmPlace]
    source: str
    source_url: str
    retrieved_on: date


def snapshot_exists(city_id: str, directory: Path = OSM_DIR) -> bool:
    return places_file(city_id, directory).is_file() and metadata_file(city_id, directory).is_file()


def read_snapshot(city_id: str, directory: Path = OSM_DIR) -> PlacesSnapshot:
    metadata = json.loads(metadata_file(city_id, directory).read_text(encoding="utf-8"))
    places: dict[tuple[str, int], OsmPlace] = {}
    with places_file(city_id, directory).open(encoding="utf-8", newline="") as file:
        # QUOTE_NONE: the file is plain tab-separated text, and names contain quotes.
        for row in csv.DictReader(file, delimiter="\t", quoting=csv.QUOTE_NONE):
            category = classify(row)
            if category is None or not row["lat"] or not row["lon"]:
                continue
            place = OsmPlace(
                osm_type=row["type"],
                osm_id=int(row["id"]),
                name=row["name"] or None,
                category=category,
                location=Coordinate(lat=float(row["lat"]), lon=float(row["lon"])),
            )
            places[place.osm_type, place.osm_id] = place
    return PlacesSnapshot(
        places=list(places.values()),
        source=metadata["source"],
        source_url=metadata["source_url"],
        retrieved_on=date.fromisoformat(metadata["retrieved_on"]),
    )


def ingest_places(session: Session, city_id: str, snapshot: PlacesSnapshot) -> int:
    """Replace the city's places with the snapshot.

    Nothing refers to a place row, so replacing all of them is safe and also
    removes businesses that have closed since the last snapshot.
    """
    city_cells = set(session.scalars(select(CellRow.h3_index).where(CellRow.city_id == city_id)))
    session.execute(delete(PlaceRow).where(PlaceRow.city_id == city_id))
    if not snapshot.places:
        return 0

    rows = []
    for place in snapshot.places:
        cell = h3.latlng_to_cell(place.location.lat, place.location.lon, H3_RESOLUTION)
        rows.append(
            {
                "city_id": city_id,
                "osm_type": place.osm_type,
                "osm_id": place.osm_id,
                "category": place.category,
                "name": place.name[:300] if place.name else None,
                "geom": f"SRID=4326;POINT({place.location.lon} {place.location.lat})",
                # A place just outside the city has no cell but still counts as
                # "nearby" for the cells at the edge.
                "cell_id": cell if cell in city_cells else None,
                "source": snapshot.source,
                "source_url": snapshot.source_url,
                "as_of": snapshot.retrieved_on,
                "is_sample": False,
            }
        )
    # Inserting through the table (not the mapped class) lets the driver send
    # all rows in one batch: about 5 s for Berlin instead of 90 s.
    session.execute(insert(Base.metadata.tables[PlaceRow.__tablename__]), rows)
    inside = sum(row["cell_id"] is not None for row in rows)
    logger.info("%s: ingested %d places (%d inside the city)", city_id, len(rows), inside)
    return len(rows)

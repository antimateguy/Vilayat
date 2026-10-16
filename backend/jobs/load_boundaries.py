"""Load the neighbourhood boundaries of a city from its official GeoJSON file.

Run for one city:  uv run python -m jobs.load_base_data --city berlin
"""

import json
import logging
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from geoalchemy2.shape import from_shape
from shapely import make_valid, unary_union
from shapely.geometry import MultiPolygon, Polygon, shape
from shapely.geometry.base import BaseGeometry
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from cities.base import CityConfig
from domain.geo import Coordinate
from infrastructure.db.models import SRID_WGS84, NeighbourhoodRow

logger = logging.getLogger(__name__)

BOUNDARY_DIR = Path(__file__).resolve().parents[1] / "data" / "boundaries"


@dataclass(frozen=True)
class Boundary:
    external_id: str
    name: str
    geometry: MultiPolygon


def read_boundaries(city: CityConfig, directory: Path = BOUNDARY_DIR) -> list[Boundary]:
    """Read the city's GeoJSON file into one Boundary per area.

    Features that share an id are merged: the source lists an area with a
    detached part (an exclave) as several features.
    """
    source = city.boundaries
    collection = json.loads((directory / source.file).read_text(encoding="utf-8"))

    parts: dict[str, list[BaseGeometry]] = {}
    names: dict[str, str] = {}
    for feature in collection["features"]:
        properties = feature["properties"]
        external_id = str(properties[source.id_property])
        names[external_id] = str(properties[source.name_property])
        parts.setdefault(external_id, []).append(shape(feature["geometry"]))

    boundaries = [
        Boundary(external_id, names[external_id], _to_multipolygon(unary_union(geometries)))
        for external_id, geometries in sorted(parts.items())
    ]
    for boundary in boundaries:
        _check_inside_city(city, boundary)
    return boundaries


def load_boundaries(session: Session, city: CityConfig, boundaries: Sequence[Boundary]) -> int:
    """Insert or update the city's neighbourhoods. Safe to run again."""
    source = city.boundaries
    statement = insert(NeighbourhoodRow).values(
        [
            {
                "city_id": city.id,
                "external_id": boundary.external_id,
                "name": boundary.name,
                "geom": from_shape(boundary.geometry, srid=SRID_WGS84),
                "source": f"{source.dataset}, {source.publisher} ({source.licence})",
                "source_url": source.url,
                "as_of": source.retrieved_on,
                "is_sample": False,
            }
            for boundary in boundaries
        ]
    )
    # The official key identifies an area, so a reload updates instead of duplicating.
    updated = ("name", "geom", "source", "source_url", "as_of", "is_sample")
    session.execute(
        statement.on_conflict_do_update(
            constraint="uq_neighbourhoods_city_id_external_id",
            set_={column: statement.excluded[column] for column in updated},
        )
    )
    logger.info("%s: loaded %d neighbourhoods", city.id, len(boundaries))
    return len(boundaries)


def _to_multipolygon(geometry: BaseGeometry) -> MultiPolygon:
    polygons = _polygons(make_valid(geometry))
    if not polygons:
        raise ValueError("boundary has no polygon")
    return MultiPolygon(polygons)


def _polygons(geometry: BaseGeometry) -> list[Polygon]:
    """Repairing a geometry can leave stray lines or points; keep only the polygons."""
    if isinstance(geometry, Polygon):
        return [geometry]
    return [polygon for part in getattr(geometry, "geoms", []) for polygon in _polygons(part)]


def _check_inside_city(city: CityConfig, boundary: Boundary) -> None:
    """Catches a file in the wrong coordinate system or with latitude and longitude swapped."""
    point = boundary.geometry.representative_point()
    if not city.bounds.contains(Coordinate(lat=point.y, lon=point.x)):
        raise ValueError(
            f"{boundary.name} lies outside the bounds of {city.name}: ({point.y}, {point.x})"
        )

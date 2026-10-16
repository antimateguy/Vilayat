"""Geographic value objects."""

import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

EARTH_RADIUS_KM = 6371.0088

type GeoJsonGeometry = Mapping[str, Any]
"""A GeoJSON geometry object: {"type": ..., "coordinates": ...}, longitude first."""


@dataclass(frozen=True, slots=True)
class Coordinate:
    """A point in WGS84, the coordinate system of GPS and OpenStreetMap."""

    lat: float
    lon: float

    def __post_init__(self) -> None:
        if not -90 <= self.lat <= 90:
            raise ValueError(f"latitude out of range: {self.lat}")
        if not -180 <= self.lon <= 180:
            raise ValueError(f"longitude out of range: {self.lon}")

    def distance_km(self, other: "Coordinate") -> float:
        """Straight-line distance over the Earth's surface (haversine formula)."""
        lat1, lat2 = math.radians(self.lat), math.radians(other.lat)
        half_dlat = (lat2 - lat1) / 2
        half_dlon = math.radians(other.lon - self.lon) / 2
        a = math.sin(half_dlat) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(half_dlon) ** 2
        return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))

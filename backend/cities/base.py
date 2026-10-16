"""The shape of a city configuration.

A city is described by data, not code: adding one means adding a module with a
CITY constant of this type. Nothing else changes.
"""

from dataclasses import dataclass
from datetime import date

from domain.geo import Coordinate


@dataclass(frozen=True, slots=True)
class BoundingBox:
    """A rectangle around the city, used to sanity-check loaded data."""

    south: float
    west: float
    north: float
    east: float

    def contains(self, point: Coordinate) -> bool:
        return self.south <= point.lat <= self.north and self.west <= point.lon <= self.east

    def expanded(self, degrees: float) -> "BoundingBox":
        """The same box grown by a margin on every side."""
        return BoundingBox(
            south=self.south - degrees,
            west=self.west - degrees,
            north=self.north + degrees,
            east=self.east + degrees,
        )


@dataclass(frozen=True, slots=True)
class BoundarySource:
    """Where the neighbourhood boundaries come from and how to read the file."""

    file: str
    """File name under backend/data/boundaries/."""
    dataset: str
    publisher: str
    url: str
    licence: str
    retrieved_on: date
    id_property: str
    """GeoJSON property holding the official key of an area."""
    name_property: str


@dataclass(frozen=True, slots=True)
class FeedSource:
    """A file the travel-time job downloads: a timetable or a street network."""

    file: str
    """File name under backend/data/raw/<city id>/."""
    url: str
    publisher: str
    licence: str


@dataclass(frozen=True, slots=True)
class TransitFeeds:
    gtfs: tuple[FeedSource, ...]
    """Public-transport timetables in GTFS format."""
    streets: FeedSource
    """OpenStreetMap extract (.osm.pbf) for walking to, from and between stops.
    Must reach every destination, including campuses outside the city boundary."""


@dataclass(frozen=True, slots=True)
class ListingPortal:
    """A rental portal's own search page for the city.

    The app ranks areas, not flats: once a student has picked an area it sends
    them here. Nothing is read from the portals.
    """

    name: str
    offers: str
    """What the portal lists, for example "Rooms in shared flats"."""
    url: str


@dataclass(frozen=True, slots=True)
class CampusConfig:
    name: str
    address: str
    location: Coordinate


@dataclass(frozen=True, slots=True)
class UniversityConfig:
    name: str
    short_name: str
    campuses: tuple[CampusConfig, ...]


@dataclass(frozen=True, slots=True)
class CityConfig:
    id: str
    name: str
    centre: Coordinate
    bounds: BoundingBox
    """Covers the city itself. A campus may lie outside it (TUM Garching does)."""
    boundaries: BoundarySource
    universities: tuple[UniversityConfig, ...]
    feeds: TransitFeeds
    campus_source: str
    """Where the campus coordinates come from."""
    campus_source_url: str
    campus_as_of: date
    listing_portals: tuple[ListingPortal, ...] = ()

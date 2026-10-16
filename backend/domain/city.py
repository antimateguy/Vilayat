"""Cities, universities and campuses."""

from dataclasses import dataclass

from domain.geo import Coordinate


@dataclass(frozen=True, slots=True)
class City:
    id: str
    """Registry key, for example "berlin"."""
    name: str


@dataclass(frozen=True, slots=True)
class University:
    id: int
    city_id: str
    name: str
    short_name: str


@dataclass(frozen=True, slots=True)
class Campus:
    """One site of a university. Students commute to a campus, not to a university."""

    id: int
    university_id: int
    name: str
    location: Coordinate
    destination_id: int
    """The campus as a travel destination; travel times are stored against this id."""

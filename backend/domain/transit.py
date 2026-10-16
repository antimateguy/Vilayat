"""The rail and tram network of a city, drawn as lines for the map."""

from dataclasses import dataclass

from domain.geo import Coordinate
from domain.route import LegMode


@dataclass(frozen=True, slots=True)
class TransitLine:
    label: str
    """What passengers read on the vehicle: "U2", "S1", "Tram 19"."""
    mode: LegMode
    colour: str | None
    """The line's colour from the timetable, as "#RRGGBB", when it gives one."""
    stops: tuple[Coordinate, ...]
    """The stops of the line's longest trip, in order: a schematic, not the track."""

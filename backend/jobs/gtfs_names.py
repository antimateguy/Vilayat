"""Public names of lines and stops, read from a GTFS timetable.

The routing engine reports a line by its GTFS route_id, which is a code, and a
stop by an id it shortens past recognition when the id contains a colon (as
German ids do: "de:09162:1"). Lines are therefore named through routes.txt, and
stops by position: the stop nearest to where a ride starts or ends.
"""

import csv
import io
import math
import re
import zipfile
from collections import Counter
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from domain.geo import Coordinate
from domain.route import LegMode

# GTFS route_type, basic and extended (https://gtfs.org, "Extended route types").
_ROUTE_TYPE_MODES = {
    0: LegMode.TRAM,
    1: LegMode.SUBWAY,
    2: LegMode.RAIL,
    3: LegMode.BUS,
    4: LegMode.FERRY,
}
_EXTENDED_MODES = (
    (100, 200, LegMode.RAIL),
    (200, 300, LegMode.BUS),  # coach
    (400, 500, LegMode.SUBWAY),  # urban railway, metro
    (700, 800, LegMode.BUS),
    (900, 1000, LegMode.TRAM),
    (1000, 1100, LegMode.FERRY),
)
_ENGINE_MODES = {
    "WALK": LegMode.WALK,
    "BUS": LegMode.BUS,
    "TRAM": LegMode.TRAM,
    "SUBWAY": LegMode.SUBWAY,
    "RAIL": LegMode.RAIL,
    "FERRY": LegMode.FERRY,
}
_PREFIXED = {LegMode.BUS: "Bus", LegMode.TRAM: "Tram"}
STOP_SEARCH_METRES = 150.0
"""A ride's end point lies on the track next to the platform; further away
than this, the nearest stop is probably not the one used."""
_GRID_DEGREES = 0.01


def engine_mode(name: str) -> LegMode:
    return _ENGINE_MODES.get(name.upper(), LegMode.OTHER)


def route_type_mode(route_type: int) -> LegMode:
    if route_type in _ROUTE_TYPE_MODES:
        return _ROUTE_TYPE_MODES[route_type]
    for low, high, mode in _EXTENDED_MODES:
        if low <= route_type < high:
            return mode
    return LegMode.OTHER


def line_label(short_name: str, long_name: str, mode: LegMode) -> str:
    """ "U2", "S1", "Bus 53", "Tram M10": what a passenger reads on the vehicle."""
    name = short_name.strip() or long_name.strip()
    prefix = _PREFIXED.get(mode)
    if prefix and name and not name.lower().startswith(prefix.lower()):
        return f"{prefix} {name}"
    return name


_GERMAN_RAIL_NAME = re.compile(r"^(?:(?:Tram|Bus)\s+)?([SU])\s?(\d{1,2})$")
"""In Germany "S1" is always an S-Bahn and "U2" always a U-Bahn line."""


def corrected(short_name: str, long_name: str, mode: LegMode) -> tuple[str, LegMode]:
    """The line's label and mode, trusting the line's name over the feed's type.

    Munich's timetable files several S-Bahn lines as trams and part of the U6
    as a bus, which would show as "Tram S6" and "Bus U6". The name decides.
    """
    found = _GERMAN_RAIL_NAME.match((short_name or long_name).strip())
    if found:
        letter, number = found.groups()
        return f"{letter}{number}", LegMode.RAIL if letter == "S" else LegMode.SUBWAY
    return line_label(short_name, long_name, mode), mode


@dataclass(frozen=True)
class Line:
    label: str
    mode: LegMode
    colour: str | None = None


def line_colour(value: str) -> str | None:
    """A timetable colour as "#RRGGBB". Black and white are left out: feeds
    use them as a default for every line (Munich's does), so they say nothing."""
    value = value.strip().upper()
    if len(value) != 6 or any(c not in "0123456789ABCDEF" for c in value):
        return None
    if value in ("000000", "FFFFFF"):
        return None
    return f"#{value}"


@dataclass(frozen=True)
class Stop:
    name: str
    location: Coordinate


class TimetableNames:
    def __init__(self, lines: dict[str, Line], stops: list[Stop]) -> None:
        self._lines = lines
        self._grid: dict[tuple[int, int], list[Stop]] = {}
        for stop in stops:
            self._grid.setdefault(_cell(stop.location), []).append(stop)

    @classmethod
    def read(cls, *feeds: Path) -> "TimetableNames":
        lines: dict[str, Line] = {}
        stops: list[Stop] = []
        for feed in feeds:
            with zipfile.ZipFile(feed) as archive:
                for row in _rows(archive, "routes.txt"):
                    label, mode = corrected(
                        row.get("route_short_name", ""),
                        row.get("route_long_name", ""),
                        route_type_mode(int(row.get("route_type") or -1)),
                    )
                    lines[row["route_id"]] = Line(
                        label, mode, line_colour(row.get("route_color", ""))
                    )
                parents = {
                    row["stop_id"]: row["stop_name"]
                    for row in _rows(archive, "stops.txt")
                    if row.get("location_type") == "1"
                }
                for row in _rows(archive, "stops.txt"):
                    if row.get("location_type", "0") not in ("", "0"):
                        continue
                    # A platform carries its station's name, without "Gleis 4".
                    name = parents.get(row.get("parent_station", ""), row["stop_name"])
                    location = Coordinate(lat=float(row["stop_lat"]), lon=float(row["stop_lon"]))
                    stops.append(Stop(_tidy(name), location))
        return cls(lines, stops)

    def line(self, route_id: str | None) -> Line | None:
        return None if route_id is None else self._lines.get(route_id)

    def colour_of(self, label: str) -> str | None:
        """The colour most of a label's routes carry; for journeys stored
        before colours were kept."""
        colours = Counter(
            line.colour for line in self._lines.values() if line.label == label and line.colour
        )
        return colours.most_common(1)[0][0] if colours else None

    def stop_near(self, point: Coordinate) -> str | None:
        """Name of the nearest stop within STOP_SEARCH_METRES, if any."""
        row, column = _cell(point)
        nearby = [
            stop
            for d_row in (-1, 0, 1)
            for d_column in (-1, 0, 1)
            for stop in self._grid.get((row + d_row, column + d_column), [])
        ]
        if not nearby:
            return None
        best = min(nearby, key=lambda stop: stop.location.distance_km(point))
        if best.location.distance_km(point) * 1000 > STOP_SEARCH_METRES:
            return None
        return best.name


def _cell(point: Coordinate) -> tuple[int, int]:
    return math.floor(point.lat / _GRID_DEGREES), math.floor(point.lon / _GRID_DEGREES)


def _tidy(name: str) -> str:
    """Berlin's feed adds "(Berlin)" to every stop in the city; it says nothing here."""
    return name.removesuffix(" (Berlin)").strip()


def _rows(archive: zipfile.ZipFile, member: str) -> Iterator[dict[str, str]]:
    if member not in archive.namelist():
        return
    with archive.open(member) as raw:
        yield from csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8-sig", newline=""))

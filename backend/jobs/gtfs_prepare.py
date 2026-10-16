"""Prepare a GTFS timetable for the routing engine.

A regional feed covers far more than one city (Berlin's covers all of
Brandenburg), and loading all of it needs more memory than a laptop has. This
module writes a smaller working copy next to the download:

- only stops inside the routing area are kept, and each trip is cut down to
  those stops (the times at the remaining stops are unchanged, so journeys
  inside the area come out the same);
- a trip left with fewer than two stops is dropped;
- the shapes table (the drawn path of each route, not needed for travel times)
  is left out, as is any table that has a header but no rows, which the routing
  engine rejects.

The downloaded file itself is never changed.
"""

import csv
import io
import logging
import shutil
import zipfile
from collections import Counter
from collections.abc import Callable, Iterator, Sequence
from pathlib import Path

from cities.base import BoundingBox
from domain.geo import Coordinate

logger = logging.getLogger(__name__)

SHAPES = "shapes.txt"
Row = dict[str, str]


def prepare_gtfs(source: Path, area: BoundingBox) -> Path:
    """Write `<name>.prepared.zip` beside the source (unless it is already up to date)."""
    target = source.with_name(f"{source.stem}.prepared.zip")
    if target.is_file() and target.stat().st_mtime >= source.stat().st_mtime:
        return target

    partial = target.with_name(target.name + ".part")
    with zipfile.ZipFile(source) as archive:
        stops = _stops_inside(archive, area)
        trips = _trips_with_two_stops(archive, stops)
        trips_or_none = trips | {""}
        rules: dict[str, tuple[Callable[[Row], bool], Sequence[str]]] = {
            "stops.txt": (lambda row: row["stop_id"] in stops, ()),
            "stop_times.txt": (
                lambda row: row["trip_id"] in trips and row["stop_id"] in stops,
                (),
            ),
            # The shapes are gone, so trips must not refer to them.
            "trips.txt": (lambda row: row["trip_id"] in trips, ("shape_id",)),
            "transfers.txt": (
                lambda row: (
                    row["from_stop_id"] in stops
                    and row["to_stop_id"] in stops
                    and row.get("from_trip_id", "") in trips_or_none
                    and row.get("to_trip_id", "") in trips_or_none
                ),
                (),
            ),
            "pathways.txt": (
                lambda row: row["from_stop_id"] in stops and row["to_stop_id"] in stops,
                (),
            ),
        }
        with zipfile.ZipFile(partial, "w", zipfile.ZIP_DEFLATED) as prepared:
            for name in archive.namelist():
                if name == SHAPES or _has_no_rows(archive, name):
                    logger.info("%s: leaving out %s", source.name, name)
                elif name in rules:
                    keep, blanked = rules[name]
                    kept, total = _copy_rows(archive, prepared, name, keep, blanked)
                    logger.info("%s: %s keeps %d of %d rows", source.name, name, kept, total)
                else:
                    with (
                        archive.open(name) as original,
                        prepared.open(name, "w", force_zip64=True) as copy,
                    ):
                        shutil.copyfileobj(original, copy, length=1024 * 1024)
    partial.replace(target)
    return target


def _rows(archive: zipfile.ZipFile, name: str) -> Iterator[Row]:
    with archive.open(name) as raw:
        # utf-8-sig: published feeds often start with a byte-order mark.
        yield from csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8-sig", newline=""))


def _has_no_rows(archive: zipfile.ZipFile, name: str) -> bool:
    with archive.open(name) as file:
        file.readline()
        return not file.readline().strip()


def _stops_inside(archive: zipfile.ZipFile, area: BoundingBox) -> set[str]:
    """Stops in the area, plus what belongs to them: their parent station, and
    entrances or platforms that carry no coordinate of their own."""
    rows = list(_rows(archive, "stops.txt"))
    inside = {
        row["stop_id"]
        for row in rows
        if row.get("stop_lat") and row.get("stop_lon") and _in_area(row, area)
    }
    parents = {
        row["parent_station"]
        for row in rows
        if row["stop_id"] in inside and row.get("parent_station")
    }
    without_coordinate = {
        row["stop_id"]
        for row in rows
        if not (row.get("stop_lat") and row.get("stop_lon"))
        and row.get("parent_station") in inside | parents
    }
    return inside | parents | without_coordinate


def _in_area(row: Row, area: BoundingBox) -> bool:
    try:
        return area.contains(Coordinate(lat=float(row["stop_lat"]), lon=float(row["stop_lon"])))
    except ValueError:
        return False


def _trips_with_two_stops(archive: zipfile.ZipFile, stops: set[str]) -> set[str]:
    """A trip is only useful if it still calls at two or more stops in the area."""
    calls = Counter(
        row["trip_id"] for row in _rows(archive, "stop_times.txt") if row["stop_id"] in stops
    )
    return {trip for trip, count in calls.items() if count >= 2}


def _copy_rows(
    archive: zipfile.ZipFile,
    prepared: zipfile.ZipFile,
    name: str,
    keep: Callable[[Row], bool],
    blanked: Sequence[str],
) -> tuple[int, int]:
    kept = total = 0
    with (
        archive.open(name) as raw,
        prepared.open(name, "w", force_zip64=True) as binary,
        io.TextIOWrapper(binary, encoding="utf-8", newline="") as text,
    ):
        reader = csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8-sig", newline=""))
        writer = csv.DictWriter(text, fieldnames=reader.fieldnames or [], lineterminator="\n")
        writer.writeheader()
        for row in reader:
            total += 1
            if keep(row):
                for column in blanked:
                    if column in row:
                        row[column] = ""
                writer.writerow(row)
                kept += 1
    return kept, total

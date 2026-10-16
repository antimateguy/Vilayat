"""Draw the city's U-Bahn, S-Bahn and tram lines from its timetable, for the map.

    uv run python -m jobs.build_transit_lines --city munich

Writes data/transit/<city>.geojson: one line per route name ("U2", "S1",
"Tram 19"), through the stops of its longest trip, like the schematic network
maps at stations. Buses, regional trains and replacement services are left
out so the map stays readable. The file is small and committed; the web
backend only serves it. Run again after fetching a new timetable.
"""

import argparse
import csv
import io
import json
import logging
import re
import zipfile
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cities.registry import discover_cities
from domain.route import LegMode
from jobs.build_travel_times import ROUTING_MARGIN_DEGREES
from jobs.fetch_feeds import feed_path, missing_feeds
from jobs.gtfs_names import corrected, line_colour, route_type_mode
from jobs.gtfs_prepare import prepare_gtfs
from jobs.runtime import configure_logging

logger = logging.getLogger("jobs.build_transit_lines")

TRANSIT_DIR = Path(__file__).resolve().parents[1] / "data" / "transit"
KEPT_MODES = (LegMode.SUBWAY, LegMode.RAIL, LegMode.TRAM)
S_BAHN = re.compile(r"^S\s?\d")
"""Of the rail lines only the S-Bahn: regional trains would clutter the map."""
NIGHT = re.compile(r"^(?:Tram |Bus )?N\d")
DECIMALS = 5


@dataclass(frozen=True)
class Line:
    label: str
    mode: LegMode
    colour: str | None


def _rows(archive: zipfile.ZipFile, member: str) -> Iterator[dict[str, str]]:
    with archive.open(member) as raw:
        yield from csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8-sig", newline=""))


def kept_line(short_name: str, long_name: str, route_type: int, colour: str) -> Line | None:
    """The line a route belongs to, or None for a route the map leaves out."""
    label, mode = corrected(short_name, long_name, route_type_mode(route_type))
    if mode not in KEPT_MODES or not re.search(r"\d", label):
        return None
    # Replacement services and night lines would draw over the day network.
    if label.upper().startswith("SEV") or NIGHT.match(label):
        return None
    if mode is LegMode.RAIL and not S_BAHN.match(label):
        return None
    return Line(label, mode, line_colour(colour))


def network(feed: Path) -> dict[str, Any]:
    """The lines of one timetable as a GeoJSON FeatureCollection."""
    with zipfile.ZipFile(feed) as archive:
        lines = {}
        for row in _rows(archive, "routes.txt"):
            line = kept_line(
                row.get("route_short_name", ""),
                row.get("route_long_name", ""),
                int(row.get("route_type") or -1),
                row.get("route_color", ""),
            )
            if line:
                lines[row["route_id"]] = line
        trip_line = {
            row["trip_id"]: lines[row["route_id"]]
            for row in _rows(archive, "trips.txt")
            if row["route_id"] in lines
        }
        # First pass: the trip with the most stops stands for each line.
        stops_per_trip: dict[str, int] = {}
        for row in _rows(archive, "stop_times.txt"):
            if row["trip_id"] in trip_line:
                stops_per_trip[row["trip_id"]] = stops_per_trip.get(row["trip_id"], 0) + 1
        longest: dict[str, str] = {}
        for trip, count in stops_per_trip.items():
            label = trip_line[trip].label
            if label not in longest or count > stops_per_trip[longest[label]]:
                longest[label] = trip
        chosen = set(longest.values())
        # Second pass: the stops of the chosen trips, in order.
        sequences: dict[str, list[tuple[int, str]]] = {trip: [] for trip in chosen}
        for row in _rows(archive, "stop_times.txt"):
            if row["trip_id"] in chosen:
                sequences[row["trip_id"]].append((int(row["stop_sequence"]), row["stop_id"]))
        places = {
            row["stop_id"]: (
                round(float(row["stop_lon"]), DECIMALS),
                round(float(row["stop_lat"]), DECIMALS),
            )
            for row in _rows(archive, "stops.txt")
        }

    order = {mode: position for position, mode in enumerate(KEPT_MODES)}
    features = []
    for label, trip in sorted(
        longest.items(), key=lambda item: (order[trip_line[item[1]].mode], item[0])
    ):
        line = trip_line[trip]
        coordinates = [places[stop] for _, stop in sorted(sequences[trip]) if stop in places]
        if len(coordinates) < 2:
            continue
        features.append(
            {
                "type": "Feature",
                "properties": {"label": label, "mode": line.mode.value, "colour": line.colour},
                "geometry": {"type": "LineString", "coordinates": coordinates},
            }
        )
    return {"type": "FeatureCollection", "features": features}


def main() -> None:
    registry = discover_cities()
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--city", required=True, choices=[city.id for city in registry.all()])
    arguments = parser.parse_args()

    configure_logging()
    city = registry.get(arguments.city)
    missing = missing_feeds(city)
    if missing:
        parser.error(f"missing {', '.join(missing)}; run jobs.fetch_feeds --city {city.id}")
    area = city.bounds.expanded(ROUTING_MARGIN_DEGREES)
    collections = [
        network(prepare_gtfs(feed_path(city.id, feed), area)) for feed in city.feeds.gtfs
    ]
    result = {
        "type": "FeatureCollection",
        "features": [feature for item in collections for feature in item["features"]],
    }
    TRANSIT_DIR.mkdir(parents=True, exist_ok=True)
    target = TRANSIT_DIR / f"{city.id}.geojson"
    target.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    logger.info(
        "%s: %d lines written to %s (%d KB)",
        city.id,
        len(result["features"]),
        target.name,
        target.stat().st_size // 1024,
    )


if __name__ == "__main__":
    main()

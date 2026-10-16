"""Trimming a timetable to the routing area, on a tiny hand-written feed.

The feed has three stops on one line: A and B inside the area, C outside it.
"""

import csv
import io
import zipfile
from pathlib import Path

from cities.base import BoundingBox
from jobs.gtfs_prepare import prepare_gtfs

AREA = BoundingBox(south=48.0, west=11.0, north=49.0, east=12.0)

FEED = {
    # The first line starts with a byte-order mark, as many published feeds do.
    "stops.txt": (
        "﻿stop_id,stop_name,stop_lat,stop_lon,parent_station\n"
        "A,Inside A,48.10,11.50,\n"
        "B,Inside B,48.20,11.60,STATION\n"
        "B-entrance,Entrance of B,,,B\n"
        "STATION,Station of B,49.50,11.60,\n"
        "C,Outside C,50.00,11.70,\n"
    ),
    "stop_times.txt": (
        "trip_id,arrival_time,departure_time,stop_id,stop_sequence\n"
        "through,08:00:00,08:00:00,A,1\n"
        "through,08:10:00,08:10:00,B,2\n"
        "through,08:40:00,08:40:00,C,3\n"
        "leaving,09:00:00,09:00:00,B,1\n"
        "leaving,09:30:00,09:30:00,C,2\n"
    ),
    "trips.txt": (
        "route_id,service_id,trip_id,shape_id\n"
        "line1,weekdays,through,shape1\n"
        "line1,weekdays,leaving,shape1\n"
    ),
    "transfers.txt": ("from_stop_id,to_stop_id,transfer_type\nA,B,2\nB,C,2\n"),
    "routes.txt": 'route_id,route_short_name,route_type\nline1,"Line 1, express",1\n',
    "shapes.txt": "shape_id,shape_pt_lat,shape_pt_lon,shape_pt_sequence\nshape1,48.1,11.5,1\n",
    "frequencies.txt": "trip_id,start_time,end_time,headway_secs\n",
}


def write_feed(directory: Path) -> Path:
    path = directory / "feed.zip"
    with zipfile.ZipFile(path, "w") as archive:
        for name, content in FEED.items():
            archive.writestr(name, content)
    return path


def table(archive: zipfile.ZipFile, name: str) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(archive.read(name).decode("utf-8"))))


def test_stops_outside_the_area_are_removed_but_parents_and_entrances_stay(
    tmp_path: Path,
) -> None:
    with zipfile.ZipFile(prepare_gtfs(write_feed(tmp_path), AREA)) as prepared:
        stops = {row["stop_id"] for row in table(prepared, "stops.txt")}

    # STATION lies outside but is B's parent; B-entrance has no coordinate of its own.
    assert stops == {"A", "B", "B-entrance", "STATION"}


def test_a_trip_is_cut_to_the_area_and_keeps_its_times(tmp_path: Path) -> None:
    with zipfile.ZipFile(prepare_gtfs(write_feed(tmp_path), AREA)) as prepared:
        stop_times = table(prepared, "stop_times.txt")
        trips = table(prepared, "trips.txt")

    assert [(row["trip_id"], row["stop_id"], row["departure_time"]) for row in stop_times] == [
        ("through", "A", "08:00:00"),
        ("through", "B", "08:10:00"),
    ]
    # "leaving" would call at one stop only, which is no journey, so it is dropped.
    assert [row["trip_id"] for row in trips] == ["through"]


def test_shapes_and_empty_tables_are_left_out_and_nothing_refers_to_them(
    tmp_path: Path,
) -> None:
    with zipfile.ZipFile(prepare_gtfs(write_feed(tmp_path), AREA)) as prepared:
        names = set(prepared.namelist())
        trips = table(prepared, "trips.txt")
        transfers = table(prepared, "transfers.txt")
        routes = prepared.read("routes.txt").decode("utf-8")

    assert names == {"stops.txt", "stop_times.txt", "trips.txt", "transfers.txt", "routes.txt"}
    assert [row["shape_id"] for row in trips] == [""]
    assert [(row["from_stop_id"], row["to_stop_id"]) for row in transfers] == [("A", "B")]
    # Tables without a rule are copied unchanged.
    assert routes == FEED["routes.txt"]


def test_the_download_is_untouched_and_the_copy_is_reused(tmp_path: Path) -> None:
    source = write_feed(tmp_path)
    original_bytes = source.read_bytes()

    first = prepare_gtfs(source, AREA)
    written_at = first.stat().st_mtime_ns
    second = prepare_gtfs(source, AREA)

    assert first == second == tmp_path / "feed.prepared.zip"
    assert second.stat().st_mtime_ns == written_at
    assert source.read_bytes() == original_bytes


def test_bounding_box_grows_by_a_margin_on_every_side() -> None:
    assert AREA.expanded(0.5) == BoundingBox(south=47.5, west=10.5, north=49.5, east=12.5)

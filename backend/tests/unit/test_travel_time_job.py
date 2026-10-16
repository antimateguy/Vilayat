"""The travel-time job without Java, feeds or a database: a toy router stands in for R5."""

import zipfile
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

from domain.geo import Coordinate
from domain.travel import TimeWindow
from jobs.build_travel_times import (
    MAX_MINUTES,
    Part,
    TravelTimeRecord,
    compute_travel_times,
    gtfs_validity,
    next_tuesday,
)
from jobs.fetch_feeds import all_feeds, feed_path, missing_feeds, retrieved_on
from jobs.routing import RoutePoint
from tests.fakes import StraightLineRouter
from tests.unit.test_cities import minimal_city

HOME = RoutePoint("cell-home", Coordinate(48.137, 11.575))
SUBURB = RoutePoint("cell-suburb", Coordinate(48.137, 11.709))  # about 10 km east
CAMPUS = RoutePoint("7", Coordinate(48.149, 11.568))  # about 1.4 km from home
FAR_AWAY = RoutePoint("9", Coordinate(48.137, 12.100))  # about 39 km east
SERVICE_DAY = date(2026, 10, 6)


@pytest.mark.parametrize(
    ("today", "expected"),
    [
        (date(2026, 10, 5), date(2026, 10, 6)),  # Monday -> tomorrow
        (date(2026, 10, 6), date(2026, 10, 13)),  # Tuesday -> a week later, never today
        (date(2026, 10, 7), date(2026, 10, 13)),  # Wednesday
        (date(2026, 10, 11), date(2026, 10, 13)),  # Sunday
    ],
)
def test_service_day_is_the_first_tuesday_after_today(today: date, expected: date) -> None:
    assert next_tuesday(today) == expected
    assert expected.weekday() == 1


def test_morning_runs_from_home_and_evening_runs_back_home() -> None:
    router = StraightLineRouter()

    compute_travel_times(router, [HOME, SUBURB], [CAMPUS], SERVICE_DAY)

    (morning_from, morning_to, morning), (evening_from, evening_to, evening) = router.calls
    assert (morning_from, morning_to) == (["cell-home", "cell-suburb"], ["7"])
    assert (evening_from, evening_to) == (["7"], ["cell-home", "cell-suburb"])
    assert morning.start == datetime(2026, 10, 6, 7, 30)
    assert morning.duration == timedelta(minutes=90)
    assert evening.start == datetime(2026, 10, 6, 17, 0)
    assert evening.duration == timedelta(minutes=120)


def test_both_directions_are_stored_under_destination_window_and_cell() -> None:
    records = compute_travel_times(StraightLineRouter(), [HOME, SUBURB], [CAMPUS], SERVICE_DAY)

    morning, evening = TimeWindow.WEEKDAY_MORNING, TimeWindow.WEEKDAY_EVENING
    # Home: 5 + 4 x 1.4 km = 11 minutes; the toy evening is 3 minutes slower.
    assert sorted(records, key=lambda r: (r.window, r.cell_id)) == [
        TravelTimeRecord(7, evening, "cell-home", 14),
        TravelTimeRecord(7, evening, "cell-suburb", 50),
        TravelTimeRecord(7, morning, "cell-home", 11),
        TravelTimeRecord(7, morning, "cell-suburb", 47),
    ]


def test_a_pair_beyond_the_time_limit_gets_no_record() -> None:
    records = compute_travel_times(StraightLineRouter(), [HOME], [CAMPUS, FAR_AWAY], SERVICE_DAY)

    # 39 km would take 5 + 156 minutes in the toy network: over the limit.
    assert {record.destination_id for record in records} == {7}
    assert all(record.minutes <= MAX_MINUTES for record in records)


# --- Feeds -----------------------------------------------------------------


def write_gtfs(path: Path, files: dict[str, str]) -> Path:
    """A tiny GTFS feed: only the files the validity check reads."""
    with zipfile.ZipFile(path, "w") as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return path


def test_gtfs_validity_spans_the_calendar_and_its_exceptions(tmp_path: Path) -> None:
    feed = write_gtfs(
        tmp_path / "feed.zip",
        {
            "calendar.txt": (
                "service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,"
                "start_date,end_date\n"
                "weekdays,1,1,1,1,1,0,0,20260901,20261130\n"
                "weekend,0,0,0,0,0,1,1,20260905,20261129\n"
            ),
            "calendar_dates.txt": "service_id,date,exception_type\nweekdays,20261212,1\n",
            "stops.txt": "stop_id,stop_name\n1,Example\n",
        },
    )

    assert gtfs_validity(feed) == (date(2026, 9, 1), date(2026, 12, 12))


def test_gtfs_validity_reads_a_feed_that_only_lists_single_days(tmp_path: Path) -> None:
    # A byte-order mark at the start of the file is common in published feeds.
    dates = "﻿service_id,date,exception_type\na,20261001,1\na,20261015,1\n"
    feed = write_gtfs(tmp_path / "feed.zip", {"calendar_dates.txt": dates})

    assert gtfs_validity(feed) == (date(2026, 10, 1), date(2026, 10, 15))


def test_gtfs_validity_is_none_when_the_feed_has_no_calendar(tmp_path: Path) -> None:
    feed = write_gtfs(tmp_path / "feed.zip", {"stops.txt": "stop_id\n1\n"})

    assert gtfs_validity(feed) is None


def test_missing_feeds_are_named_before_any_routing_starts(tmp_path: Path) -> None:
    city = minimal_city("x")
    (streets,) = all_feeds(city)

    assert missing_feeds(city, tmp_path) == ["none.osm.pbf"]
    assert retrieved_on(city.id, streets, tmp_path) is None

    feed_path(city.id, streets, tmp_path).parent.mkdir(parents=True)
    feed_path(city.id, streets, tmp_path).write_bytes(b"pbf")

    assert missing_feeds(city, tmp_path) == []


# --- Running in parts ------------------------------------------------------


def test_parts_deal_every_cell_out_exactly_once() -> None:
    cells = [RoutePoint(f"cell-{index:02d}", Coordinate(48.1, 11.5)) for index in range(10)]

    parts = [Part(number, 3).select(cells) for number in (1, 2, 3)]

    assert [len(part) for part in parts] == [4, 3, 3]
    assert sorted(cell.id for part in parts for cell in part) == [cell.id for cell in cells]
    # The split does not depend on the order the cells arrive in.
    assert Part(1, 3).select(list(reversed(cells))) == parts[0]


def test_part_is_written_as_number_slash_total() -> None:
    assert Part.parse("2/3") == Part(number=2, total=3)


@pytest.mark.parametrize("text", ["0/3", "4/3", "two/3", "2", ""])
def test_an_impossible_part_is_rejected(text: str) -> None:
    with pytest.raises(ValueError, match="part"):
        Part.parse(text)

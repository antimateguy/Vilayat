"""Compute public-transport travel times between every cell and every destination.

This is the slow part of the system, which is why it runs offline: the web
backend only looks the results up.

Two windows on an ordinary weekday:
- morning, leaving 07:30 to 09:00, from home (the cell) to the destination;
- evening, leaving 17:00 to 19:00, from the destination back home.
Both are stored against the same (destination, window, cell) key. A pair with
no journey within two hours gets no row, which the application shows as UNKNOWN.

Needs Java 21, the `routing` dependency group and the downloaded feeds:
    uv run python -m jobs.fetch_feeds --city munich
    uv run --group routing python -m jobs.build_travel_times --city munich

A large city can be routed in slices (about 6 minutes each for Berlin). A slice
routes cells only, so finish with the destination-to-destination times:
    uv run --group routing python -m jobs.build_travel_times --city berlin --part 1/3
    uv run --group routing python -m jobs.build_travel_times --city berlin --destinations-only
"""

import argparse
import csv
import io
import logging
import zipfile
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path

from sqlalchemy import delete, func, insert, select
from sqlalchemy.orm import Session

from cities.registry import discover_cities
from domain.geo import Coordinate
from domain.travel import TimeWindow
from infrastructure.db.models import (
    Base,
    CellRow,
    DestinationRow,
    DestinationTravelTimeRow,
    TravelTimeRow,
)
from jobs.fetch_feeds import RAW_DIR, feed_path, missing_feeds
from jobs.gtfs_prepare import prepare_gtfs
from jobs.routing import DepartureWindow, RoutePoint, Router
from jobs.runtime import configure_logging, job_session

logger = logging.getLogger(__name__)

MAX_MINUTES = 120
# The timetable is trimmed to the city plus this margin (about 10 km), which
# keeps the campuses and employers just outside the boundary reachable.
ROUTING_MARGIN_DEGREES = 0.1
TUESDAY = 1

DEPARTURES = {
    TimeWindow.WEEKDAY_MORNING: (time(7, 30), timedelta(minutes=90)),
    TimeWindow.WEEKDAY_EVENING: (time(17, 0), timedelta(minutes=120)),
}


@dataclass(frozen=True)
class TravelTimeRecord:
    destination_id: int
    window: TimeWindow
    cell_id: str
    minutes: int


def next_tuesday(today: date) -> date:
    """The first Tuesday after today: an ordinary working day inside the timetable."""
    days_ahead = (TUESDAY - today.weekday() - 1) % 7 + 1
    return today + timedelta(days=days_ahead)


def gtfs_validity(path: Path) -> tuple[date, date] | None:
    """First and last day a GTFS feed has service for, or None if it does not say."""
    days: list[date] = []
    with zipfile.ZipFile(path) as archive:
        names = set(archive.namelist())
        for member, columns in (
            ("calendar.txt", ("start_date", "end_date")),
            ("calendar_dates.txt", ("date",)),
        ):
            if member not in names:
                continue
            with archive.open(member) as raw:
                for row in csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8-sig")):
                    days.extend(datetime.strptime(row[c].strip(), "%Y%m%d").date() for c in columns)
    return (min(days), max(days)) if days else None


def compute_travel_times(
    router: Router,
    cells: Sequence[RoutePoint],
    destinations: Sequence[RoutePoint],
    service_day: date,
) -> list[TravelTimeRecord]:
    records: list[TravelTimeRecord] = []
    for window, (start, duration) in DEPARTURES.items():
        departure = DepartureWindow(datetime.combine(service_day, start), duration)
        if window is TimeWindow.WEEKDAY_MORNING:
            # To the destination: home is the origin.
            found = router.travel_minutes(cells, destinations, departure, MAX_MINUTES)
            pairs = {(destination, cell): minutes for (cell, destination), minutes in found.items()}
        else:
            # Back home: the destination is the origin.
            pairs = router.travel_minutes(destinations, cells, departure, MAX_MINUTES)
        records.extend(
            TravelTimeRecord(int(destination), window, cell, minutes)
            for (destination, cell), minutes in pairs.items()
        )
        possible = len(cells) * len(destinations)
        logger.info(
            "%s: %d of %d pairs have a journey within %d minutes",
            window.value,
            len(pairs),
            possible,
            MAX_MINUTES,
        )
    return records


@dataclass(frozen=True)
class Part:
    """One slice of a city's cells, so a long run can be split into shorter ones.

    Routing a large city takes longer than some machines can run in one go.
    `--part 1/3`, `--part 2/3` and `--part 3/3` together do the same work as one
    run without `--part`; each replaces only the travel times of its own cells.
    """

    number: int
    total: int

    def __post_init__(self) -> None:
        if not 1 <= self.number <= self.total:
            raise ValueError(f"part must be between 1/{self.total} and {self.total}/{self.total}")

    @classmethod
    def parse(cls, text: str) -> "Part":
        number, _, total = text.partition("/")
        try:
            return cls(int(number), int(total))
        except ValueError:
            raise ValueError(f"expected a part like 2/3, got {text!r}") from None

    def select(self, cells: Sequence[RoutePoint]) -> list[RoutePoint]:
        """Every cell falls in exactly one part: they are dealt out in turn, in id order."""
        ordered = sorted(cells, key=lambda cell: cell.id)
        return [cell for index, cell in enumerate(ordered) if index % self.total == self.number - 1]


def build_travel_times(
    session: Session,
    city_id: str,
    router: Router,
    service_day: date,
    computed_at: datetime,
    part: Part | None = None,
) -> int:
    """Replace the travel times of the city's cells, or of one part of them.

    Run again after cells or destinations change.
    """
    cells = [
        RoutePoint(cell, Coordinate(lat=lat, lon=lon))
        for cell, lat, lon in session.execute(
            select(
                CellRow.h3_index, func.ST_Y(CellRow.centroid), func.ST_X(CellRow.centroid)
            ).where(CellRow.city_id == city_id)
        )
    ]
    if part is not None:
        cells = part.select(cells)
    destinations = [
        RoutePoint(str(destination_id), Coordinate(lat=lat, lon=lon))
        for destination_id, lat, lon in session.execute(
            select(
                DestinationRow.id,
                func.ST_Y(DestinationRow.geom),
                func.ST_X(DestinationRow.geom),
            ).where(DestinationRow.city_id == city_id)
        )
    ]
    if not cells or not destinations:
        raise RuntimeError(f"{city_id}: load the base data first (jobs.load_base_data)")
    logger.info(
        "%s: routing %d cells x %d destinations for %s",
        city_id,
        len(cells),
        len(destinations),
        service_day,
    )
    records = compute_travel_times(router, cells, destinations, service_day)

    # Only the rows of the cells just routed are replaced, so parts do not undo each other.
    session.execute(
        delete(TravelTimeRow).where(TravelTimeRow.cell_id.in_([cell.id for cell in cells]))
    )
    if records:
        # Through the table, not the mapped class, so the driver sends one batch.
        session.execute(
            insert(Base.metadata.tables[TravelTimeRow.__tablename__]),
            [
                {
                    "destination_id": record.destination_id,
                    "time_window": record.window,
                    "cell_id": record.cell_id,
                    "minutes": record.minutes,
                    "computed_at": computed_at,
                }
                for record in records
            ],
        )
    logger.info("%s: stored %d travel times", city_id, len(records))
    return len(records)


def build_destination_times(
    session: Session, city_id: str, router: Router, service_day: date, computed_at: datetime
) -> int:
    """Replace the city's destination-to-destination times, for both windows.

    These give the middle leg of a day, campus to job. There are only a few dozen
    destinations per city, so this takes seconds once the network is loaded.
    """
    destinations = [
        RoutePoint(str(destination_id), Coordinate(lat=lat, lon=lon))
        for destination_id, lat, lon in session.execute(
            select(
                DestinationRow.id,
                func.ST_Y(DestinationRow.geom),
                func.ST_X(DestinationRow.geom),
            ).where(DestinationRow.city_id == city_id)
        )
    ]
    rows: list[dict[str, object]] = []
    for window, (start, duration) in DEPARTURES.items():
        departure = DepartureWindow(datetime.combine(service_day, start), duration)
        found = router.travel_minutes(destinations, destinations, departure, MAX_MINUTES)
        rows.extend(
            {
                "from_destination_id": int(origin),
                "to_destination_id": int(destination),
                "time_window": window,
                "minutes": minutes,
                "computed_at": computed_at,
            }
            for (origin, destination), minutes in found.items()
            if origin != destination
        )

    city_destinations = select(DestinationRow.id).where(DestinationRow.city_id == city_id)
    session.execute(
        delete(DestinationTravelTimeRow).where(
            DestinationTravelTimeRow.from_destination_id.in_(city_destinations)
        )
    )
    if rows:
        session.execute(insert(Base.metadata.tables[DestinationTravelTimeRow.__tablename__]), rows)
    logger.info("%s: stored %d destination-to-destination times", city_id, len(rows))
    return len(rows)


def main() -> None:
    registry = discover_cities()
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--city", required=True, choices=[city.id for city in registry.all()])
    parser.add_argument(
        "--date",
        type=date.fromisoformat,
        help="service day to route for, YYYY-MM-DD (default: next Tuesday)",
    )
    parser.add_argument(
        "--max-memory", help="memory for the routing engine, for example 6G (read by r5py)"
    )
    parser.add_argument(
        "--part",
        type=Part.parse,
        help="route only one slice of the cells, for example 1/3; run every slice to finish",
    )
    parser.add_argument(
        "--destinations-only",
        action="store_true",
        help="refresh only the destination-to-destination times (for example campus to employer)",
    )
    arguments = parser.parse_args()
    if arguments.part and arguments.destinations_only:
        parser.error("--part and --destinations-only cannot be combined")

    configure_logging()
    city = registry.get(arguments.city)
    missing = missing_feeds(city)
    if missing:
        parser.error(f"missing {', '.join(missing)}; run jobs.fetch_feeds --city {city.id}")

    service_day = arguments.date or next_tuesday(date.today())
    gtfs_files = [feed_path(city.id, feed) for feed in city.feeds.gtfs]
    for path in gtfs_files:
        validity = gtfs_validity(path)
        if validity and not validity[0] <= service_day <= validity[1]:
            parser.error(
                f"{service_day} is outside the timetable in {path.name} "
                f"({validity[0]} to {validity[1]}); pass --date or fetch a newer feed"
            )
        logger.info("%s covers %s", path.name, validity or "an unstated period")

    # Imported late: it needs the routing dependency group, which tests do not install.
    from jobs.r5_router import R5Router

    routing_area = city.bounds.expanded(ROUTING_MARGIN_DEGREES)
    router = R5Router(
        feed_path(city.id, city.feeds.streets),
        [prepare_gtfs(path, routing_area) for path in gtfs_files],
    )
    computed_at = datetime.now(UTC)
    with job_session() as session:
        if not arguments.destinations_only:
            build_travel_times(session, city.id, router, service_day, computed_at, arguments.part)
        # A run for one part routes cells only; the few destination-to-destination
        # times belong to a full run or to --destinations-only.
        if arguments.part is None:
            build_destination_times(session, city.id, router, service_day, computed_at)
    logger.info("feeds read from %s", RAW_DIR / city.id)


if __name__ == "__main__":
    main()

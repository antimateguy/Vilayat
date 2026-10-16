"""Plan one typical morning journey from every area to every campus, step by step.

    uv run --group routing python -m jobs.build_commute_routes --city munich

The travel times in the ranking are medians over departures (07:30 to 09:00)
and over the hexagons of an area, so they say how long a commute takes but not
how. This job picks, for each area and campus, the hexagon whose time is
closest to the area's median, plans that hexagon's journeys with the same
engine, settings and departure window as the travel times, and keeps the option
whose duration is closest to the hexagon's median. The result is one concrete,
typical journey: walk to a stop, ride a line, change, walk to the campus.

Run it after jobs.build_travel_times. It needs Java 21 and the feeds, takes
about 8 seconds per journey (Munich, 150 journeys: about 20 minutes; Berlin,
679: about 1.5 hours), and keeps what it stored when stopped: a second run
carries on with the pairs that are missing. `--force` plans every pair again.
"""

import argparse
import logging
import statistics
import time
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from itertools import batched

from shapely import LineString
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from cities.registry import discover_cities
from domain.destination import DestinationKind
from domain.geo import Coordinate
from domain.route import CommuteRoute, DestinationRoute, LegMode, RouteLeg
from domain.travel import TimeWindow
from infrastructure.db.models import (
    CampusRow,
    CellRow,
    CommuteRouteRow,
    DestinationRouteRow,
    DestinationRow,
    DestinationTravelTimeRow,
    NeighbourhoodRow,
    TravelTimeRow,
)
from infrastructure.db.repositories.routes import leg_to_json
from jobs.build_travel_times import (
    DEPARTURES,
    MAX_MINUTES,
    ROUTING_MARGIN_DEGREES,
    gtfs_validity,
    next_tuesday,
)
from jobs.fetch_feeds import feed_path, missing_feeds
from jobs.gtfs_names import TimetableNames, corrected, engine_mode
from jobs.gtfs_prepare import prepare_gtfs
from jobs.routing import DepartureWindow, Itinerary, ItineraryPlanner, RoutePoint
from jobs.runtime import configure_logging, job_sessions

logger = logging.getLogger("jobs.build_commute_routes")

BATCH_SIZE = 25
"""Journeys planned per call to the engine; the work is committed after each."""
PATH_TOLERANCE_DEGREES = 0.00003
"""Points closer than about 3 m to the simplified line are dropped from a path."""
SHORTEST_LEG_SECONDS = 20
"""Shorter walking legs (stepping between two platforms) are not worth a line."""


@dataclass(frozen=True)
class CellTime:
    cell_id: str
    location: Coordinate
    minutes: int


@dataclass(frozen=True)
class Pair:
    area_id: int
    destination_id: int
    start: CellTime
    destination: Coordinate


def representative_cell(cells: Sequence[CellTime], centre: Coordinate) -> CellTime:
    """The hexagon whose time is closest to the area's median, so the journey
    shown is a typical one. Ties go to the hexagon nearest the area's centre."""
    median = statistics.median(cell.minutes for cell in cells)
    return min(
        cells,
        key=lambda cell: (
            abs(cell.minutes - median),
            cell.location.distance_km(centre),
            cell.cell_id,
        ),
    )


def choose_itinerary(options: Sequence[Itinerary], target_minutes: int) -> Itinerary:
    """The option whose duration is closest to the hexagon's median time;
    among equals, the quicker one."""
    return min(
        options,
        key=lambda option: (
            abs(_total_seconds(option) / 60 - target_minutes),
            _total_seconds(option),
        ),
    )


def to_route_legs(itinerary: Itinerary, names: TimetableNames) -> tuple[RouteLeg, ...]:
    legs: list[RouteLeg] = []
    for leg in itinerary:
        mode = engine_mode(leg.mode)
        if mode is LegMode.WALK and leg.travel_seconds < SHORTEST_LEG_SECONDS:
            continue
        path = _simplified(leg.path)
        line = names.line(leg.route_id) if mode.is_transit else None
        legs.append(
            RouteLeg(
                mode=line.mode if line and line.mode is not LegMode.OTHER else mode,
                minutes=max(1, round(leg.travel_seconds / 60)),
                wait_minutes=round(leg.wait_seconds / 60),
                distance_m=round(leg.distance_m),
                path=path,
                line=line.label if line else None,
                line_colour=line.colour if line else None,
                from_stop=names.stop_near(path[0]) if mode.is_transit else None,
                to_stop=names.stop_near(path[-1]) if mode.is_transit else None,
            )
        )
    return tuple(legs)


def departure_of(itinerary: Itinerary, window_start: datetime) -> datetime:
    """When the journey starts: the first timed leg, less the legs before it.
    A walk-only journey has no timetable, so it starts at the window's start."""
    before = 0.0
    for leg in itinerary:
        if leg.departure is not None:
            return (leg.departure - timedelta(seconds=before)).replace(second=0, microsecond=0)
        before += leg.total_seconds
    return window_start


def build_commute_routes(
    session: Session,
    city_id: str,
    planner: ItineraryPlanner,
    names: TimetableNames,
    service_day: date,
    computed_at: datetime,
    *,
    force: bool = False,
    batch_size: int = BATCH_SIZE,
) -> int:
    """Plan and store the city's typical journeys; returns how many were stored."""
    start, duration = DEPARTURES[TimeWindow.WEEKDAY_MORNING]
    window = DepartureWindow(datetime.combine(service_day, start), duration)
    pairs = _pairs(session, city_id)
    if not force:
        done = set(
            session.execute(
                select(CommuteRouteRow.neighbourhood_id, CommuteRouteRow.destination_id)
            )
        )
        pairs = [pair for pair in pairs if (pair.area_id, pair.destination_id) not in done]
    logger.info("%s: %d journeys to plan", city_id, len(pairs))

    stored = 0
    started = time.perf_counter()
    for number, batch in enumerate(batched(pairs, batch_size), start=1):
        found = planner.itineraries(
            [
                (
                    RoutePoint(f"{pair.area_id}-{pair.destination_id}", pair.start.location),
                    RoutePoint(str(pair.destination_id), pair.destination),
                )
                for pair in batch
            ],
            window,
            MAX_MINUTES,
        )
        rows = []
        for pair in batch:
            options = found.get((f"{pair.area_id}-{pair.destination_id}", str(pair.destination_id)))
            if not options:
                logger.warning(
                    "no journey from area %d to destination %d", pair.area_id, pair.destination_id
                )
                continue
            chosen = choose_itinerary(options, pair.start.minutes)
            route = CommuteRoute(
                area_id=pair.area_id,
                destination_id=pair.destination_id,
                cell_id=pair.start.cell_id,
                departs_at=departure_of(chosen, window.start),
                total_minutes=round(_total_seconds(chosen) / 60),
                legs=to_route_legs(chosen, names),
                computed_at=computed_at,
            )
            rows.append(_row(route))
        if rows:
            statement = insert(CommuteRouteRow).values(rows)
            session.execute(
                statement.on_conflict_do_update(
                    index_elements=["neighbourhood_id", "destination_id"],
                    set_={
                        column: statement.excluded[column]
                        for column in (
                            "cell_id",
                            "departs_at",
                            "total_minutes",
                            "legs",
                            "computed_at",
                        )
                    },
                )
            )
        session.commit()
        stored += len(rows)
        logger.info(
            "%s: batch %d done, %d of %d journeys stored, %.0f s so far",
            city_id,
            number,
            stored,
            len(pairs),
            time.perf_counter() - started,
        )
    return stored


def build_destination_routes(
    session: Session,
    city_id: str,
    planner: ItineraryPlanner,
    names: TimetableNames,
    service_day: date,
    computed_at: datetime,
    *,
    force: bool = False,
) -> int:
    """Plan the afternoon journey from every campus to every employer: the middle
    leg of a day with a job. Same window (17:00 to 19:00) and choice rule as the
    campus-to-employer times the ranking uses."""
    start, duration = DEPARTURES[TimeWindow.WEEKDAY_EVENING]
    window = DepartureWindow(datetime.combine(service_day, start), duration)
    places = {
        destination_id: (kind, Coordinate(lat=lat, lon=lon))
        for destination_id, kind, lat, lon in session.execute(
            select(
                DestinationRow.id,
                DestinationRow.kind,
                func.ST_Y(DestinationRow.geom),
                func.ST_X(DestinationRow.geom),
            ).where(
                DestinationRow.city_id == city_id,
                DestinationRow.kind.in_([DestinationKind.CAMPUS, DestinationKind.EMPLOYER]),
            )
        )
    }
    campuses = sorted(i for i, (kind, _) in places.items() if kind is DestinationKind.CAMPUS)
    employers = sorted(i for i, (kind, _) in places.items() if kind is DestinationKind.EMPLOYER)
    typical = {
        (origin, target): minutes
        for origin, target, minutes in session.execute(
            select(
                DestinationTravelTimeRow.from_destination_id,
                DestinationTravelTimeRow.to_destination_id,
                DestinationTravelTimeRow.minutes,
            ).where(DestinationTravelTimeRow.time_window == TimeWindow.WEEKDAY_EVENING)
        )
    }
    pairs = [(campus, employer) for campus in campuses for employer in employers]
    if not force:
        done = {
            (origin, target)
            for origin, target in session.execute(
                select(
                    DestinationRouteRow.from_destination_id, DestinationRouteRow.to_destination_id
                )
            )
        }
        pairs = [pair for pair in pairs if pair not in done]
    logger.info("%s: %d campus-to-employer journeys to plan", city_id, len(pairs))

    stored = 0
    for batch in batched(pairs, BATCH_SIZE):
        found = planner.itineraries(
            [
                (
                    RoutePoint(str(origin), places[origin][1]),
                    RoutePoint(str(target), places[target][1]),
                )
                for origin, target in batch
            ],
            window,
            MAX_MINUTES,
        )
        rows = []
        for origin, target in batch:
            options = found.get((str(origin), str(target)))
            if not options:
                logger.warning("no journey from destination %d to %d", origin, target)
                continue
            target_minutes = typical.get((origin, target))
            chosen = (
                choose_itinerary(options, target_minutes)
                if target_minutes is not None
                else min(options, key=_total_seconds)
            )
            route = DestinationRoute(
                from_destination_id=origin,
                to_destination_id=target,
                departs_at=departure_of(chosen, window.start),
                total_minutes=round(_total_seconds(chosen) / 60),
                legs=to_route_legs(chosen, names),
                computed_at=computed_at,
            )
            rows.append(
                {
                    "from_destination_id": route.from_destination_id,
                    "to_destination_id": route.to_destination_id,
                    "departs_at": route.departs_at,
                    "total_minutes": route.total_minutes,
                    "legs": [leg_to_json(leg) for leg in route.legs],
                    "computed_at": route.computed_at,
                }
            )
        if rows:
            statement = insert(DestinationRouteRow).values(rows)
            session.execute(
                statement.on_conflict_do_update(
                    index_elements=["from_destination_id", "to_destination_id"],
                    set_={
                        column: statement.excluded[column]
                        for column in ("departs_at", "total_minutes", "legs", "computed_at")
                    },
                )
            )
        session.commit()
        stored += len(rows)
        logger.info("%s: %d of %d campus-to-employer journeys stored", city_id, stored, len(pairs))
    return stored


def recolour(session: Session, city_id: str, names: TimetableNames) -> int:
    """Tidy the rides of stored journeys without new routing: correct line
    names the feed filed under the wrong mode ("Tram S6" is the S6) and add
    line colours where they are missing, by line name."""
    changed = 0
    city_destinations = select(DestinationRow.id).where(DestinationRow.city_id == city_id)
    rows: list[CommuteRouteRow | DestinationRouteRow] = [
        *session.scalars(
            select(CommuteRouteRow).where(CommuteRouteRow.destination_id.in_(city_destinations))
        ),
        *session.scalars(
            select(DestinationRouteRow).where(
                DestinationRouteRow.from_destination_id.in_(city_destinations)
            )
        ),
    ]
    for row in rows:
        legs = [dict(leg) for leg in row.legs]
        touched = False
        for leg in legs:
            if leg.get("line"):
                label, mode = corrected(leg["line"], "", LegMode(leg["mode"]))
                if (label, mode.value) != (leg["line"], leg["mode"]):
                    leg["line"], leg["mode"] = label, mode.value
                    touched = True
            if leg.get("line") and not leg.get("line_colour"):
                colour = names.colour_of(leg["line"])
                if colour:
                    leg["line_colour"] = colour
                    touched = True
        if touched:
            row.legs = legs
            changed += 1
    session.commit()
    logger.info("%s: line names or colours corrected in %d journeys", city_id, changed)
    return changed


def _pairs(session: Session, city_id: str) -> list[Pair]:
    """Every (area, campus) pair with at least one routed hexagon, with the
    hexagon the journey will start from."""
    campuses = {
        destination_id: Coordinate(lat=lat, lon=lon)
        for destination_id, lat, lon in session.execute(
            select(
                DestinationRow.id, func.ST_Y(DestinationRow.geom), func.ST_X(DestinationRow.geom)
            )
            .join(CampusRow, CampusRow.destination_id == DestinationRow.id)
            .where(DestinationRow.city_id == city_id)
            .order_by(DestinationRow.id)
        )
    }
    inside = func.ST_PointOnSurface(NeighbourhoodRow.geom)
    centres = {
        area_id: Coordinate(lat=lat, lon=lon)
        for area_id, lat, lon in session.execute(
            select(NeighbourhoodRow.id, func.ST_Y(inside), func.ST_X(inside)).where(
                NeighbourhoodRow.city_id == city_id
            )
        )
    }
    times: dict[tuple[int, int], list[CellTime]] = {}
    for destination_id, area_id, cell_id, lat, lon, minutes in session.execute(
        select(
            TravelTimeRow.destination_id,
            CellRow.neighbourhood_id,
            CellRow.h3_index,
            func.ST_Y(CellRow.centroid),
            func.ST_X(CellRow.centroid),
            TravelTimeRow.minutes,
        )
        .join(CellRow, CellRow.h3_index == TravelTimeRow.cell_id)
        .where(
            TravelTimeRow.destination_id.in_(list(campuses)),
            TravelTimeRow.time_window == TimeWindow.WEEKDAY_MORNING,
        )
    ):
        times.setdefault((area_id, destination_id), []).append(
            CellTime(cell_id, Coordinate(lat=lat, lon=lon), minutes)
        )
    return [
        Pair(
            area_id,
            destination_id,
            representative_cell(cells, centres[area_id]),
            campuses[destination_id],
        )
        for (area_id, destination_id), cells in sorted(times.items())
    ]


def _row(route: CommuteRoute) -> dict[str, object]:
    return {
        "neighbourhood_id": route.area_id,
        "destination_id": route.destination_id,
        "cell_id": route.cell_id,
        "departs_at": route.departs_at,
        "total_minutes": route.total_minutes,
        "legs": [leg_to_json(leg) for leg in route.legs],
        "computed_at": route.computed_at,
    }


def _total_seconds(itinerary: Itinerary) -> float:
    return sum(leg.total_seconds for leg in itinerary)


def _simplified(path: Sequence[tuple[float, float]]) -> tuple[Coordinate, ...]:
    if len(path) > 2:
        path = list(LineString(path).simplify(PATH_TOLERANCE_DEGREES).coords)
    points = [Coordinate(lat=round(lat, 5), lon=round(lon, 5)) for lon, lat in path]
    return tuple(point for n, point in enumerate(points) if n == 0 or point != points[n - 1])


def main() -> None:
    registry = discover_cities()
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--city", required=True, choices=[city.id for city in registry.all()])
    parser.add_argument(
        "--date",
        type=date.fromisoformat,
        help="timetable day to plan for, YYYY-MM-DD (default: next Tuesday)",
    )
    parser.add_argument("--force", action="store_true", help="plan every journey again")
    parser.add_argument(
        "--recolour",
        action="store_true",
        help="only add line colours to stored journeys; no routing, no Java needed",
    )
    arguments = parser.parse_args()

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
            parser.error(f"{service_day} is outside the timetable in {path.name}; pass --date")

    routing_area = city.bounds.expanded(ROUTING_MARGIN_DEGREES)
    prepared = [prepare_gtfs(path, routing_area) for path in gtfs_files]
    names = TimetableNames.read(*prepared)
    if arguments.recolour:
        with job_sessions() as sessions, sessions() as session:
            recolour(session, city.id, names)
        return

    # Imported late: it needs the routing dependency group, which tests do not install.
    from jobs.r5_router import R5Router

    planner = R5Router(feed_path(city.id, city.feeds.streets), prepared)
    computed_at = datetime.now(UTC)
    # Committed batch by batch inside, so a stopped run keeps its work.
    with job_sessions() as sessions, sessions() as session:
        stored = build_commute_routes(
            session, city.id, planner, names, service_day, computed_at, force=arguments.force
        )
        logger.info("%s: %d journeys stored", city.id, stored)
        build_destination_routes(
            session, city.id, planner, names, service_day, computed_at, force=arguments.force
        )
        recolour(session, city.id, names)


if __name__ == "__main__":
    main()

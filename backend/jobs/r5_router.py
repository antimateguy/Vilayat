"""Router backed by R5, the open-source engine behind Conveyal's accessibility tools.

R5 reads a street network (OpenStreetMap) and timetables (GTFS) and finds the
fastest door-to-door journeys. It runs on the Java virtual machine; the r5py
library starts one inside this Python process.

Needs the `routing` dependency group and Java 21:
    uv run --group routing python -m jobs.build_travel_times --city munich
"""

import logging
import math
import os
import re
import subprocess
from collections.abc import Sequence
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from jobs.routing import (
    DepartureWindow,
    Itinerary,
    ItineraryPlanner,
    PlannedLeg,
    RoutePoint,
    Router,
)

logger = logging.getLogger(__name__)

REQUIRED_JAVA_VERSION = 21
WALKING_SPEED_KMH = 4.8
"""A usual planning value for an adult on foot. The library's own default of
3.6 km/h makes every short trip look several minutes longer than it is."""
WGS84 = "EPSG:4326"


def use_installed_java() -> None:
    """Point this process at the JDK behind the `java` command.

    r5py locates Java through JAVA_HOME. It is set here for this process only,
    never system-wide, and an existing value is left alone.
    """
    if os.environ.get("JAVA_HOME"):
        return
    # `java -XshowSettings:properties -version` prints, among others,
    # "java.home = <path>" and "java.specification.version = 21".
    output = subprocess.run(
        ["java", "-XshowSettings:properties", "-version"],
        capture_output=True,
        text=True,
        check=True,
    ).stderr
    home = re.search(r"java\.home = (.+)", output)
    version = re.search(r"java\.specification\.version = (\d+)", output)
    if home is None or version is None:
        raise RuntimeError("could not find the Java installation; set JAVA_HOME")
    if int(version.group(1)) < REQUIRED_JAVA_VERSION:
        raise RuntimeError(
            f"R5 needs Java {REQUIRED_JAVA_VERSION} or newer; found {version.group(1)}"
        )
    os.environ["JAVA_HOME"] = home.group(1).strip()
    logger.info("using Java at %s", os.environ["JAVA_HOME"])


class R5Router(Router, ItineraryPlanner):
    def __init__(self, streets: Path, gtfs: Sequence[Path]) -> None:
        use_installed_java()
        # Imported here, not at the top: importing r5py starts the Java virtual
        # machine, which should only happen when routing is really wanted.
        import geopandas
        import r5py

        self._geopandas = geopandas
        self._r5py = r5py
        logger.info("building the transport network (this takes a few minutes)")
        self._network = r5py.TransportNetwork(str(streets), [str(path) for path in gtfs])

    def travel_minutes(
        self,
        origins: Sequence[RoutePoint],
        destinations: Sequence[RoutePoint],
        departure: DepartureWindow,
        max_minutes: int,
    ) -> dict[tuple[str, str], int]:
        r5py = self._r5py
        matrix = r5py.TravelTimeMatrix(
            self._network,
            origins=self._points(origins),
            destinations=self._points(destinations),
            departure=departure.start,
            departure_time_window=departure.duration,
            # Median over the departure window.
            percentiles=[50],
            # WALK as well, so a walk that beats public transport is found.
            transport_modes=[r5py.TransportMode.TRANSIT, r5py.TransportMode.WALK],
            max_time=timedelta(minutes=max_minutes),
            speed_walking=WALKING_SPEED_KMH,
            # A cell centre can fall in a park or a river; start from the nearest street.
            snap_to_network=True,
        )
        result: dict[tuple[str, str], int] = {}
        for origin, destination, minutes in zip(
            matrix["from_id"], matrix["to_id"], matrix["travel_time"], strict=True
        ):
            # R5 reports "no journey within the limit" as NaN.
            if not math.isnan(minutes) and minutes <= max_minutes:
                result[str(origin), str(destination)] = round(minutes)
        return result

    def itineraries(
        self,
        pairs: Sequence[tuple[RoutePoint, RoutePoint]],
        departure: DepartureWindow,
        max_minutes: int,
    ) -> dict[tuple[str, str], list[Itinerary]]:
        r5py = self._r5py
        if not pairs:
            return {}
        # Origins and destinations of equal length are routed pair by pair
        # (origin 1 to destination 1, ...), not every origin to every destination.
        # Pair ids keep the two frames distinct even when two pairs share a point.
        origins = [RoutePoint(f"{n}", origin.location) for n, (origin, _) in enumerate(pairs)]
        targets = [RoutePoint(f"{n}", target.location) for n, (_, target) in enumerate(pairs)]
        table = r5py.DetailedItineraries(
            self._network,
            origins=self._points(origins),
            destinations=self._points(targets),
            departure=departure.start,
            departure_time_window=departure.duration,
            transport_modes=[r5py.TransportMode.TRANSIT, r5py.TransportMode.WALK],
            max_time=timedelta(minutes=max_minutes),
            speed_walking=WALKING_SPEED_KMH,
            snap_to_network=True,
            force_all_to_all=False,
        )
        legs: dict[tuple[int, int], list[tuple[int, PlannedLeg]]] = {}
        for row in table.itertuples(index=False):
            if row.geometry is None or row.travel_time is None:
                continue
            leg = PlannedLeg(
                mode=str(row.transport_mode).rsplit(".", 1)[-1],
                travel_seconds=_seconds(row.travel_time),
                wait_seconds=_seconds(row.wait_time),
                distance_m=float(row.distance) if not _missing(row.distance) else 0.0,
                path=_path(row.geometry),
                route_id=None if _missing(row.route_id) else str(row.route_id),
                departure=_moment(row.departure_time),
            )
            legs.setdefault((int(row.from_id), int(row.option)), []).append((int(row.segment), leg))

        result: dict[tuple[str, str], list[Itinerary]] = {}
        for (pair, _option), segments in sorted(legs.items()):
            origin, target = pairs[pair]
            itinerary = tuple(leg for _, leg in sorted(segments, key=lambda item: item[0]))
            result.setdefault((origin.id, target.id), []).append(itinerary)
        return result

    def _points(self, points: Sequence[RoutePoint]) -> Any:
        geopandas = self._geopandas
        return geopandas.GeoDataFrame(
            {"id": [point.id for point in points]},
            geometry=geopandas.points_from_xy(
                [point.location.lon for point in points],
                [point.location.lat for point in points],
            ),
            crs=WGS84,
        )


def _missing(value: Any) -> bool:
    return value is None or (isinstance(value, float) and math.isnan(value))


def _seconds(value: Any) -> float:
    """A pandas Timedelta, or NaT when the engine has no figure."""
    if _missing(value) or str(value) == "NaT":
        return 0.0
    return float(value.total_seconds())


def _moment(value: Any) -> datetime | None:
    """A pandas Timestamp as a plain datetime; None for NaT."""
    if _missing(value) or str(value) == "NaT":
        return None
    return value.to_pydatetime().replace(tzinfo=None)  # type: ignore[no-any-return]


def _path(geometry: Any) -> tuple[tuple[float, float], ...]:
    """(longitude, latitude) points of a leg. A ride whose track pieces could not
    be joined into one line arrives as several; they are chained in order."""
    parts = geometry.geoms if hasattr(geometry, "geoms") else [geometry]
    return tuple((round(x, 6), round(y, 6)) for part in parts for x, y in part.coords)

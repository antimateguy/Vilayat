"""Spot-check stored travel times against a few journeys whose rough duration is known.

Each check names a well-known starting point and a destination, and a range the
door-to-door time should fall in. The ranges are estimates from general
knowledge of the two networks (ride time plus walking and waiting); they catch
gross errors such as a wrong date, a missing line or swapped coordinates, not
small ones.

Run:  uv run python -m jobs.check_travel_times
"""

import argparse
from dataclasses import dataclass

import h3
from sqlalchemy import func, select

from domain.destination import DestinationKind
from domain.geo import Coordinate
from domain.travel import TimeWindow
from infrastructure.db.models import CellRow, DestinationRow, TravelTimeRow
from infrastructure.db.repositories.catalog import PostgresCatalogRepository
from infrastructure.db.repositories.commute import PrecomputedCommuteProvider
from jobs.build_cells import H3_RESOLUTION
from jobs.runtime import configure_logging, job_session
from ports.catalog import CatalogRepository
from ports.commute import CommuteProvider


@dataclass(frozen=True)
class SpotCheck:
    city_id: str
    origin_name: str
    origin: Coordinate
    destination_name: str
    expected_minutes: tuple[int, int]


SPOT_CHECKS = (
    SpotCheck(
        "berlin",
        "Alexanderplatz",
        Coordinate(52.5219, 13.4132),
        "TU Berlin, Campus Charlottenburg",
        (20, 40),
    ),
    SpotCheck(
        "berlin",
        "Alexanderplatz",
        Coordinate(52.5219, 13.4132),
        "HU Berlin, Campus Adlershof",
        (35, 55),
    ),
    SpotCheck(
        "berlin",
        "Rathaus Spandau",
        Coordinate(52.5352, 13.1997),
        "TU Berlin, Campus Charlottenburg",
        (25, 45),
    ),
    SpotCheck(
        "berlin",
        "Rathaus Steglitz",
        Coordinate(52.4565, 13.3221),
        "FU Berlin, Campus Dahlem",
        (12, 30),
    ),
    SpotCheck(
        "berlin",
        "S-Bahnhof Köpenick",
        Coordinate(52.4587, 13.5815),
        "HTW Berlin, Campus Wilhelminenhof",
        (15, 35),
    ),
    SpotCheck("munich", "Marienplatz", Coordinate(48.1372, 11.5756), "TUM, City Campus", (10, 25)),
    SpotCheck(
        "munich", "Marienplatz", Coordinate(48.1372, 11.5756), "TUM, Campus Garching", (35, 55)
    ),
    SpotCheck(
        "munich", "Marienplatz", Coordinate(48.1372, 11.5756), "LMU, Campus Großhadern", (25, 45)
    ),
    SpotCheck(
        "munich", "Bahnhof Pasing", Coordinate(48.1499, 11.4614), "LMU, Main Campus", (25, 45)
    ),
    SpotCheck(
        "munich", "Ostbahnhof", Coordinate(48.1273, 11.6047), "HM, Campus Lothstraße", (20, 40)
    ),
)


@dataclass(frozen=True)
class SpotResult:
    check: SpotCheck
    window: TimeWindow
    minutes: int | None

    @property
    def plausible(self) -> bool:
        low, high = self.check.expected_minutes
        return self.minutes is not None and low <= self.minutes <= high


def run_spot_checks(catalog: CatalogRepository, commute: CommuteProvider) -> list[SpotResult]:
    results = []
    for check in SPOT_CHECKS:
        campuses = catalog.list_destinations(check.city_id, DestinationKind.CAMPUS)
        destination = next(d for d in campuses if d.name == check.destination_name)
        cell = h3.latlng_to_cell(check.origin.lat, check.origin.lon, H3_RESOLUTION)
        for window in TimeWindow:
            minutes = commute.minutes_by_cell(destination.id, window).get(cell)
            results.append(SpotResult(check, window, minutes))
    return results


def main() -> None:
    argparse.ArgumentParser(description=__doc__.splitlines()[0]).parse_args()
    configure_logging()
    with job_session() as session:
        for city_id, window, pairs, cells, destinations, computed in session.execute(
            select(
                DestinationRow.city_id,
                TravelTimeRow.time_window,
                func.count(),
                func.count(TravelTimeRow.cell_id.distinct()),
                func.count(TravelTimeRow.destination_id.distinct()),
                func.max(TravelTimeRow.computed_at),
            )
            .join(DestinationRow, DestinationRow.id == TravelTimeRow.destination_id)
            .group_by(DestinationRow.city_id, TravelTimeRow.time_window)
            .order_by(DestinationRow.city_id, TravelTimeRow.time_window)
        ):
            all_cells = session.scalar(
                select(func.count()).select_from(CellRow).where(CellRow.city_id == city_id)
            )
            print(
                f"{city_id} {window.value}: {pairs} travel times, "
                f"{cells} of {all_cells} cells, {destinations} destinations, "
                f"computed {computed:%Y-%m-%d %H:%M} UTC"
            )

        results = run_spot_checks(
            PostgresCatalogRepository(session), PrecomputedCommuteProvider(session)
        )
        print()
        for result in results:
            low, high = result.check.expected_minutes
            found = "no journey" if result.minutes is None else f"{result.minutes} min"
            verdict = "ok" if result.plausible else "CHECK"
            direction = "to" if result.window is TimeWindow.WEEKDAY_MORNING else "back from"
            print(
                f"{verdict:<5} {result.check.city_id:<6} {result.window.value:<15} "
                f"{result.check.origin_name} {direction} {result.check.destination_name}: "
                f"{found} (expected {low} to {high})"
            )
        implausible = sum(not result.plausible for result in results)
        print(f"\n{len(results) - implausible} of {len(results)} spot checks are plausible")


if __name__ == "__main__":
    main()

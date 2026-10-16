"""The route job and repository on the real database, with a scripted planner."""

from datetime import UTC, date, datetime

import pytest
from sqlalchemy.orm import Session

from domain.geo import Coordinate
from domain.route import CommuteSpread, LegMode
from infrastructure.db.repositories.routes import PostgresCommuteRouteRepository
from jobs.build_commute_routes import (
    build_commute_routes,
    build_destination_routes,
    recolour,
)
from jobs.gtfs_names import Line, Stop, TimetableNames
from tests.fakes import TwoOptionPlanner
from tests.integration.world import A2, B1, World, build_world

pytestmark = pytest.mark.integration

SERVICE_DAY = date(2026, 10, 20)
COMPUTED_AT = datetime(2026, 10, 16, 12, 0, tzinfo=UTC)
NAMES = TimetableNames(
    {"R1": Line("Bus 7", LegMode.BUS)}, [Stop("Odeonsplatz", Coordinate(lat=48.140, lon=11.570))]
)


@pytest.fixture
def world(session: Session) -> World:
    return build_world(session)


def test_every_area_with_a_routed_hexagon_gets_one_typical_journey_per_campus(
    session: Session, world: World
) -> None:
    planner = TwoOptionPlanner()

    stored = build_commute_routes(session, world.city_id, planner, NAMES, SERVICE_DAY, COMPUTED_AT)
    routes = PostgresCommuteRouteRepository(session)

    # Altstadt and Nordend have routed hexagons; Ostpark has none. The employer
    # is not a campus, so no journey goes there.
    assert stored == 2
    altstadt = routes.route(world.altstadt, world.campus_destination_id)
    nordend = routes.route(world.nordend, world.campus_destination_id)
    assert routes.route(world.ostpark, world.campus_destination_id) is None
    assert routes.route(world.altstadt, world.employer_destination_id) is None
    assert altstadt is not None and nordend is not None
    # Altstadt's hexagons take 10, 20 and 40 minutes: A2 holds the median.
    assert (altstadt.cell_id, nordend.cell_id) == (A2, B1)
    # The 20-minute bus journey is closer to both medians than the 60-minute walk.
    assert altstadt.total_minutes == 20
    assert [leg.mode for leg in altstadt.legs] == [LegMode.WALK, LegMode.BUS, LegMode.WALK]
    assert (altstadt.legs[1].line, altstadt.legs[1].from_stop) == ("Bus 7", "Odeonsplatz")
    assert altstadt.departs_at == datetime(2026, 10, 20, 7, 37)
    assert altstadt.computed_at == COMPUTED_AT


def test_a_second_run_plans_only_what_is_missing_unless_forced(
    session: Session, world: World
) -> None:
    build_commute_routes(
        session, world.city_id, TwoOptionPlanner(), NAMES, SERVICE_DAY, COMPUTED_AT
    )
    again, forced = TwoOptionPlanner(), TwoOptionPlanner()

    build_commute_routes(session, world.city_id, again, NAMES, SERVICE_DAY, COMPUTED_AT)
    build_commute_routes(
        session, world.city_id, forced, NAMES, SERVICE_DAY, COMPUTED_AT, force=True
    )

    assert again.calls == []
    assert len(forced.calls[0]) == 2


def test_the_spread_covers_the_areas_routed_hexagons(session: Session, world: World) -> None:
    routes = PostgresCommuteRouteRepository(session)

    assert routes.spread(world.altstadt, world.campus_destination_id) == CommuteSpread(
        cells=3, fastest=10, median=20, slowest=40
    )
    assert routes.spread(world.nordend, world.campus_destination_id) == CommuteSpread(1, 30, 30, 30)
    assert routes.spread(world.ostpark, world.campus_destination_id) is None


def test_every_campus_gets_an_afternoon_journey_to_every_employer(
    session: Session, world: World
) -> None:
    stored = build_destination_routes(
        session, world.city_id, TwoOptionPlanner(), NAMES, SERVICE_DAY, COMPUTED_AT
    )
    routes = PostgresCommuteRouteRepository(session)

    route = routes.between(world.campus_destination_id, world.employer_destination_id)
    assert stored == 1
    assert route is not None
    # The fixture's campus-to-employer time is 15 minutes: the bus is closest.
    assert route.total_minutes == 20
    # The evening window starts at 17:00; the bus leaves 12 minutes in, after a 5-minute walk.
    assert route.departs_at == datetime(2026, 10, 20, 17, 7)


def test_stored_rides_get_their_line_colour_without_new_routing(
    session: Session, world: World
) -> None:
    build_commute_routes(
        session, world.city_id, TwoOptionPlanner(), NAMES, SERVICE_DAY, COMPUTED_AT
    )
    coloured = TimetableNames({"R1": Line("Bus 7", LegMode.BUS, "#7D4894")}, [])

    changed = recolour(session, world.city_id, coloured)
    route = PostgresCommuteRouteRepository(session).route(
        world.altstadt, world.campus_destination_id
    )

    assert changed == 2
    assert route is not None
    assert [leg.line_colour for leg in route.legs] == [None, "#7D4894", None]

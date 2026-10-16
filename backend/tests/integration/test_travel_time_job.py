"""The travel-time job writing to the real database, with a toy router instead of R5."""

from datetime import UTC, date, datetime

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from domain.travel import TimeWindow
from domain.unknown import UNKNOWN
from infrastructure.db.models import DestinationTravelTimeRow, TravelTimeRow
from infrastructure.db.repositories.commute import PrecomputedCommuteProvider
from jobs.build_travel_times import Part, build_destination_times, build_travel_times
from tests.fakes import StraightLineRouter
from tests.integration.world import A1, A2, A3, B1, B2, World, build_world

pytestmark = pytest.mark.integration

SERVICE_DAY = date(2026, 10, 6)
COMPUTED_AT = datetime(2026, 10, 5, 12, 0, tzinfo=UTC)
CITY_CELLS = {A1, A2, A3, B1, B2}


@pytest.fixture
def world(session: Session) -> World:
    return build_world(session)


def test_every_cell_gets_a_time_to_every_destination_in_both_windows(
    session: Session, world: World
) -> None:
    stored = build_travel_times(
        session, world.city_id, StraightLineRouter(), SERVICE_DAY, COMPUTED_AT
    )
    commute = PrecomputedCommuteProvider(session)

    # 5 cells x 2 destinations x 2 windows; the 6 rows of the fixture are replaced.
    assert stored == 20
    assert session.scalar(select(func.count()).select_from(TravelTimeRow)) == 20
    for destination in (world.campus_destination_id, world.employer_destination_id):
        for window in TimeWindow:
            assert set(commute.minutes_by_cell(destination, window)) == CITY_CELLS
    assert session.scalars(select(TravelTimeRow.computed_at).distinct()).all() == [COMPUTED_AT]


def test_morning_and_evening_times_differ_as_the_router_reported(
    session: Session, world: World
) -> None:
    build_travel_times(session, world.city_id, StraightLineRouter(), SERVICE_DAY, COMPUTED_AT)
    commute = PrecomputedCommuteProvider(session)

    morning = commute.minutes_by_cell(world.campus_destination_id, TimeWindow.WEEKDAY_MORNING)
    evening = commute.minutes_by_cell(world.campus_destination_id, TimeWindow.WEEKDAY_EVENING)

    # Every cell centre is 1.7 km from the campus: 5 + round(4 x 1.7) = 12 minutes
    # in the toy network, and its evenings are 3 minutes slower.
    assert set(morning.values()) == {12}
    assert set(evening.values()) == {15}


def test_area_figures_follow_from_the_stored_cell_times(session: Session, world: World) -> None:
    build_travel_times(session, world.city_id, StraightLineRouter(), SERVICE_DAY, COMPUTED_AT)

    by_area = PrecomputedCommuteProvider(session).minutes_by_area(
        world.campus_destination_id, TimeWindow.WEEKDAY_MORNING
    )

    # Ostpark has no cells, so nothing can be routed from it.
    assert by_area == {world.altstadt: 12, world.nordend: 12, world.ostpark: UNKNOWN}


def test_running_again_replaces_the_rows_instead_of_adding_to_them(
    session: Session, world: World
) -> None:
    later = datetime(2026, 11, 1, 9, 0, tzinfo=UTC)
    build_travel_times(session, world.city_id, StraightLineRouter(), SERVICE_DAY, COMPUTED_AT)

    build_travel_times(session, world.city_id, StraightLineRouter(), SERVICE_DAY, later)

    assert session.scalar(select(func.count()).select_from(TravelTimeRow)) == 20
    assert session.scalars(select(TravelTimeRow.computed_at).distinct()).all() == [later]


def test_a_city_without_base_data_is_refused(session: Session, world: World) -> None:
    with pytest.raises(RuntimeError, match="load the base data first"):
        build_travel_times(session, "no-such-city", StraightLineRouter(), SERVICE_DAY, COMPUTED_AT)


def stored_times(session: Session) -> set[tuple[int, str, str, int]]:
    rows = session.execute(
        select(
            TravelTimeRow.destination_id,
            TravelTimeRow.time_window,
            TravelTimeRow.cell_id,
            TravelTimeRow.minutes,
        )
    )
    return {
        (destination, window.value, cell, minutes) for destination, window, cell, minutes in rows
    }


def test_running_in_parts_gives_the_same_result_as_one_run(session: Session, world: World) -> None:
    build_travel_times(session, world.city_id, StraightLineRouter(), SERVICE_DAY, COMPUTED_AT)
    in_one_run = stored_times(session)

    for number in (1, 2):
        build_travel_times(
            session, world.city_id, StraightLineRouter(), SERVICE_DAY, COMPUTED_AT, Part(number, 2)
        )

    assert stored_times(session) == in_one_run
    assert len(in_one_run) == 20


def test_one_part_replaces_only_the_times_of_its_own_cells(session: Session, world: World) -> None:
    before = stored_times(session)

    # In id order the cells are A1, A2, A3, B1, B2; part 2 of 2 takes A2 and B1.
    build_travel_times(
        session, world.city_id, StraightLineRouter(), SERVICE_DAY, COMPUTED_AT, Part(2, 2)
    )
    after = stored_times(session)

    untouched = {row for row in before if row[2] not in (A2, B1)}
    assert untouched <= after
    assert {row[2] for row in after - before} == {A2, B1}


def test_destination_to_destination_times_cover_every_ordered_pair(
    session: Session, world: World
) -> None:
    stored = build_destination_times(
        session, world.city_id, StraightLineRouter(), SERVICE_DAY, COMPUTED_AT
    )
    commute = PrecomputedCommuteProvider(session)
    campus, employer = world.campus_destination_id, world.employer_destination_id

    # 2 destinations: 2 ordered pairs x 2 windows. A destination is never paired with itself.
    assert stored == 4
    assert session.scalar(select(func.count()).select_from(DestinationTravelTimeRow)) == 4
    # Campus and employer are 2.7 km apart: 5 + round(4 x 2.7) = 16 minutes, 19 in the evening.
    assert commute.minutes_between(campus, employer, TimeWindow.WEEKDAY_MORNING) == 16
    assert commute.minutes_between(employer, campus, TimeWindow.WEEKDAY_EVENING) == 19

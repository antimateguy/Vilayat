"""Choosing and describing the typical journey of an area, without the routing engine."""

import zipfile
from datetime import datetime
from pathlib import Path

import pytest

from domain.geo import Coordinate
from domain.route import LegMode
from jobs.build_commute_routes import (
    CellTime,
    choose_itinerary,
    departure_of,
    representative_cell,
    to_route_legs,
)
from jobs.build_transit_lines import kept_line
from jobs.gtfs_names import (
    Line,
    Stop,
    TimetableNames,
    corrected,
    line_colour,
    line_label,
    route_type_mode,
)
from jobs.routing import PlannedLeg

CENTRE = Coordinate(lat=48.15, lon=11.58)
WINDOW_START = datetime(2026, 10, 20, 7, 30)


def cell(cell_id: str, minutes: int, lat: float = 48.15) -> CellTime:
    return CellTime(cell_id, Coordinate(lat=lat, lon=11.58), minutes)


# --- Which hexagon the journey starts from ---------------------------------------


def test_the_journey_starts_from_the_hexagon_closest_to_the_median() -> None:
    cells = [cell("a", 17), cell("b", 29), cell("c", 31), cell("d", 46)]

    # The median of 17, 29, 31 and 46 is 30; b and c are equally close.
    chosen = representative_cell(cells, CENTRE)

    assert chosen.cell_id == "b"


def test_a_tie_goes_to_the_hexagon_nearest_the_centre_of_the_area() -> None:
    cells = [cell("far", 20, lat=48.20), cell("near", 20, lat=48.151)]

    assert representative_cell(cells, CENTRE).cell_id == "near"


# --- Which option is kept ------------------------------------------------------------


def walk(seconds: float) -> PlannedLeg:
    return PlannedLeg("WALK", seconds, 0, seconds, ((11.57, 48.14), (11.58, 48.15)))


def ride(seconds: float, wait: float = 0, route_id: str = "R1") -> PlannedLeg:
    return PlannedLeg(
        "SUBWAY",
        seconds,
        wait,
        seconds * 10,
        ((11.570, 48.140), (11.575, 48.145), (11.580, 48.150)),
        route_id=route_id,
        departure=datetime(2026, 10, 20, 7, 52),
    )


def test_the_option_closest_to_the_hexagons_median_is_kept() -> None:
    quick = (walk(240), ride(600), walk(180))  # 17 minutes
    typical = (walk(240), ride(600, wait=420), walk(780))  # 34 minutes
    on_foot = (walk(3300),)  # 55 minutes

    assert choose_itinerary([quick, typical, on_foot], target_minutes=30) == typical
    assert choose_itinerary([quick, typical, on_foot], target_minutes=60) == on_foot


def test_the_departure_is_the_first_timed_leg_less_the_walk_before_it() -> None:
    journey = (walk(480), ride(600))

    assert departure_of(journey, WINDOW_START) == datetime(2026, 10, 20, 7, 44)
    assert departure_of((walk(600),), WINDOW_START) == WINDOW_START


# --- Describing the legs -------------------------------------------------------------


def names() -> TimetableNames:
    return TimetableNames(
        {"R1": Line("U2", LegMode.SUBWAY)},
        [
            Stop("Scheidplatz", Coordinate(lat=48.1401, lon=11.5701)),
            Stop("Hauptbahnhof", Coordinate(lat=48.1500, lon=11.5801)),
        ],
    )


def test_a_ride_is_named_by_its_line_and_its_stops() -> None:
    legs = to_route_legs((walk(240), ride(600, wait=120), walk(180)), names())

    assert [leg.mode for leg in legs] == [LegMode.WALK, LegMode.SUBWAY, LegMode.WALK]
    middle = legs[1]
    assert (middle.line, middle.from_stop, middle.to_stop) == ("U2", "Scheidplatz", "Hauptbahnhof")
    assert (middle.minutes, middle.wait_minutes) == (10, 2)
    assert legs[0].line is None and legs[0].from_stop is None


def test_a_short_step_between_platforms_is_left_out() -> None:
    legs = to_route_legs((ride(300), walk(10), ride(300)), names())

    assert [leg.mode for leg in legs] == [LegMode.SUBWAY, LegMode.SUBWAY]


def test_an_unknown_line_or_a_stop_too_far_away_stays_unnamed() -> None:
    far = PlannedLeg("BUS", 600, 0, 5000, ((11.0, 48.0), (11.1, 48.1)), route_id="missing")

    (leg,) = to_route_legs((far,), names())

    assert (leg.mode, leg.line, leg.from_stop, leg.to_stop) == (LegMode.BUS, None, None, None)


# --- Names from the timetable --------------------------------------------------------


@pytest.mark.parametrize(
    ("route_type", "mode"),
    [(0, LegMode.TRAM), (1, LegMode.SUBWAY), (2, LegMode.RAIL), (3, LegMode.BUS),
     (109, LegMode.RAIL), (400, LegMode.SUBWAY), (700, LegMode.BUS), (900, LegMode.TRAM),
     (1300, LegMode.OTHER)],
)  # fmt: skip
def test_route_types_basic_and_extended(route_type: int, mode: LegMode) -> None:
    assert route_type_mode(route_type) is mode


@pytest.mark.parametrize(
    ("short", "long", "mode", "label"),
    [
        ("U2", "", LegMode.SUBWAY, "U2"),
        ("53", "", LegMode.BUS, "Bus 53"),
        ("M10", "", LegMode.TRAM, "Tram M10"),
        ("", "Flughafen-Express", LegMode.RAIL, "Flughafen-Express"),
    ],
)
def test_lines_are_labelled_as_passengers_read_them(
    short: str, long: str, mode: LegMode, label: str
) -> None:
    assert line_label(short, long, mode) == label


def test_names_are_read_from_a_feed(tmp_path: Path) -> None:
    feed = tmp_path / "feed.zip"
    with zipfile.ZipFile(feed, "w") as archive:
        archive.writestr(
            "routes.txt",
            "route_id,route_short_name,route_long_name,route_type,route_color\n"
            "r:1,U2,,1,DA421E\nr:2,100,,700,000000\n",
        )
        archive.writestr(
            "stops.txt",
            "stop_id,stop_name,stop_lat,stop_lon,location_type,parent_station\n"
            "de:1,S Hackescher Markt (Berlin),52.5225,13.4022,1,\n"
            "de:1:1,S Hackescher Markt Gleis 1,52.5226,13.4023,0,de:1\n",
        )

    timetable = TimetableNames.read(feed)

    assert timetable.line("r:1") == Line("U2", LegMode.SUBWAY, "#DA421E")
    assert timetable.colour_of("U2") == "#DA421E"
    assert timetable.line("r:2") == Line("Bus 100", LegMode.BUS)
    # A platform takes its station's name, without the city suffix.
    assert timetable.stop_near(Coordinate(lat=52.5227, lon=13.4024)) == "S Hackescher Markt"


@pytest.mark.parametrize(
    ("value", "colour"),
    [("da421e", "#DA421E"), ("000000", None), ("FFFFFF", None), ("", None), ("red", None)],
)
def test_only_real_line_colours_are_kept(value: str, colour: str | None) -> None:
    assert line_colour(value) == colour


def test_a_ride_keeps_its_line_colour() -> None:
    timetable = TimetableNames({"R1": Line("U2", LegMode.SUBWAY, "#DA421E")}, [])

    (leg,) = to_route_legs((ride(600),), timetable)

    assert leg.line_colour == "#DA421E"


@pytest.mark.parametrize(
    ("short", "mode", "expected"),
    [
        ("S6", LegMode.TRAM, ("S6", LegMode.RAIL)),
        ("U6", LegMode.BUS, ("U6", LegMode.SUBWAY)),
        ("Tram S1", LegMode.TRAM, ("S1", LegMode.RAIL)),
        ("19", LegMode.TRAM, ("Tram 19", LegMode.TRAM)),
        ("SEV S1", LegMode.BUS, ("Bus SEV S1", LegMode.BUS)),
    ],
)
def test_the_line_name_decides_over_a_misfiled_mode(
    short: str, mode: LegMode, expected: tuple[str, LegMode]
) -> None:
    assert corrected(short, "", mode) == expected


@pytest.mark.parametrize(
    ("short", "route_type", "kept"),
    [
        ("U2", 1, "U2"),
        ("S8", 0, "S8"),  # an S-Bahn filed as a tram
        ("19", 0, "Tram 19"),
        ("RB 87", 2, None),  # regional trains are left out
        ("N17", 0, None),  # night trams too
        ("53", 3, None),  # and buses
        ("SEV S1", 3, None),
    ],
)
def test_the_line_map_keeps_rail_and_day_trams(
    short: str, route_type: int, kept: str | None
) -> None:
    line = kept_line(short, "", route_type, "")
    assert (line.label if line else None) == kept

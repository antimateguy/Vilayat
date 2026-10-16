"""GET /areas/{id}/commute: the spread of times and the stored typical journey."""

from datetime import UTC, datetime

from httpx2 import Response

from domain.geo import Coordinate
from domain.route import CommuteRoute, CommuteSpread, DestinationRoute, LegMode, RouteLeg
from infrastructure.fakes.routes import InMemoryCommuteRoutes
from tests.unit.api_client import V1, make_client
from tests.unit.engine_world import (
    ALTSTADT,
    EMPLOYER,
    EMPLOYER_ELSEWHERE,
    MAIN_CAMPUS,
    MAIN_CAMPUS_DESTINATION,
    NORDEND,
)

HOME, STOP_A, STOP_B, CAMPUS = (
    Coordinate(48.140, 11.570),
    Coordinate(48.142, 11.572),
    Coordinate(48.150, 11.580),
    Coordinate(48.151, 11.581),
)
ROUTE = CommuteRoute(
    area_id=ALTSTADT,
    destination_id=MAIN_CAMPUS_DESTINATION,
    cell_id="881f8d44a7fffff",
    departs_at=datetime(2026, 10, 20, 7, 52),
    total_minutes=19,
    legs=(
        RouteLeg(LegMode.WALK, 4, 0, 300, (HOME, STOP_A)),
        RouteLeg(LegMode.SUBWAY, 9, 2, 3000, (STOP_A, STOP_B), "U2", "Scheidplatz", "Hauptbahnhof"),
        RouteLeg(LegMode.WALK, 4, 0, 250, (STOP_B, CAMPUS)),
    ),
    computed_at=datetime(2026, 10, 16, 12, tzinfo=UTC),
)
SPREAD = CommuteSpread(cells=19, fastest=17, median=30, slowest=46)


def get(
    area: int, campus: int = MAIN_CAMPUS, routes: InMemoryCommuteRoutes | None = None
) -> Response:
    client = make_client(routes=routes)[0]
    return client.get(f"{V1}/areas/{area}/commute", params={"campus_id": campus})


def test_the_typical_journey_comes_with_the_spread_of_the_area() -> None:
    routes = InMemoryCommuteRoutes(
        {(ALTSTADT, MAIN_CAMPUS_DESTINATION): ROUTE}, {(ALTSTADT, MAIN_CAMPUS_DESTINATION): SPREAD}
    )

    response = get(ALTSTADT, routes=routes)

    assert response.status_code == 200
    body = response.json()
    assert body["area"] == {"id": ALTSTADT, "name": "Altstadt"}
    assert body["spread"] == {
        "cells": 19,
        "fastest_minutes": 17,
        "median_minutes": 30,
        "slowest_minutes": 46,
    }
    route = body["route"]
    assert (route["departs_at"], route["total_minutes"]) == ("07:52", 19)
    assert route["start"] == [11.570, 48.140]
    assert [leg["mode"] for leg in route["legs"]] == ["walk", "subway", "walk"]
    ride = route["legs"][1]
    assert (ride["line"], ride["from_stop"], ride["to_stop"]) == (
        "U2",
        "Scheidplatz",
        "Hauptbahnhof",
    )
    assert ride["path"] == {"type": "LineString", "coordinates": [[11.572, 48.142], [11.58, 48.15]]}


def test_before_the_job_has_run_both_parts_are_null() -> None:
    body = get(NORDEND).json()

    assert (body["spread"], body["route"]) == (None, None)


def test_an_unknown_area_or_campus_is_a_404() -> None:
    assert get(999).status_code == 404
    assert get(ALTSTADT, campus=999).status_code == 404


def test_with_a_pinned_employer_the_afternoon_leg_comes_too() -> None:
    to_job = DestinationRoute(
        from_destination_id=MAIN_CAMPUS_DESTINATION,
        to_destination_id=EMPLOYER,
        departs_at=datetime(2026, 10, 20, 17, 4),
        total_minutes=15,
        legs=(
            RouteLeg(LegMode.TRAM, 15, 3, 4000, (STOP_B, CAMPUS), "Tram 19", "A", "B", "#7D4894"),
        ),
        computed_at=datetime(2026, 10, 16, 12, tzinfo=UTC),
    )
    routes = InMemoryCommuteRoutes(transfers={(MAIN_CAMPUS_DESTINATION, EMPLOYER): to_job})
    client = make_client(routes=routes)[0]

    body = client.get(
        f"{V1}/areas/{ALTSTADT}/commute",
        params={"campus_id": MAIN_CAMPUS, "employer_id": EMPLOYER},
    ).json()

    assert body["employer"]["id"] == EMPLOYER
    assert body["to_job"]["departs_at"] == "17:04"
    assert body["to_job"]["legs"][0]["line_colour"] == "#7D4894"


def test_an_employer_that_is_not_one_or_is_elsewhere_is_refused() -> None:
    client = make_client()[0]
    url = f"{V1}/areas/{ALTSTADT}/commute"

    assert client.get(url, params={"campus_id": MAIN_CAMPUS, "employer_id": 999}).status_code == 404
    elsewhere = client.get(
        url, params={"campus_id": MAIN_CAMPUS, "employer_id": EMPLOYER_ELSEWHERE}
    )
    assert elsewhere.status_code == 422


def test_the_transit_lines_of_a_city_come_as_geojson() -> None:
    client = make_client()[0]

    body = client.get(f"{V1}/cities/testville/layers/transit").json()

    (line,) = body["features"]
    assert line["properties"] == {"label": "U1", "mode": "subway", "colour": "#3C7233"}
    assert line["geometry"]["coordinates"] == [[11.5, 48.1], [11.55, 48.12]]
    assert client.get(f"{V1}/cities/nowhere/layers/transit").status_code == 404


def test_the_committed_line_files_are_readable() -> None:
    from infrastructure.transit_files import FileTransitNetwork

    network = FileTransitNetwork()
    for city in ("munich", "berlin"):
        labels = {line.label for line in network.lines(city)}
        assert {"U2", "S1"} <= labels, city
        assert not any(label.startswith(("Tram S", "Bus U")) for label in labels)

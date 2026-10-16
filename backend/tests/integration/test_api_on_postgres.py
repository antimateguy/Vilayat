"""The API with its real wiring: routes, services and PostgreSQL repositories.

Only the session provider is replaced, so the routes read the Testville fixture
that the test wrote inside its own transaction.
"""

import dataclasses
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from api.dependencies import get_registry, get_session
from api.main import create_app
from cities.registry import CityRegistry
from infrastructure.settings import Settings
from tests.integration.world import A1, B2, World, build_world
from tests.unit.api_client import TESTVILLE, V1

pytestmark = pytest.mark.integration


@pytest.fixture
def world(session: Session) -> World:
    return build_world(session)


@pytest.fixture
def client(session: Session, world: World) -> Iterator[TestClient]:
    app = create_app(Settings(rate_limit_per_minute=0))
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_registry] = lambda: CityRegistry(
        [dataclasses.replace(TESTVILLE, id=world.city_id)]
    )
    yield TestClient(app)


def test_catalog_endpoints_read_the_database(client: TestClient, world: World) -> None:
    cities = client.get(f"{V1}/cities").json()
    universities = client.get(f"{V1}/cities/{world.city_id}/universities").json()
    employers = client.get(f"{V1}/cities/{world.city_id}/employers").json()

    assert [city["id"] for city in cities] == ["elsewhere", "testville"]
    assert universities[0]["campuses"][0]["lat"] == pytest.approx(48.15)
    assert [(e["name"], e["is_sample"]) for e in employers] == [("Example Works", True)]


def test_search_over_http_on_the_database(client: TestClient, world: World) -> None:
    response = client.post(
        f"{V1}/search",
        json={
            "campus_id": world.campus_id,
            "max_commute_minutes": 40,
            "max_rent_eur": 800,
            "employer_id": world.employer_destination_id,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert [item["area"]["name"] for item in body["ranked"]] == ["Nordend", "Altstadt"]
    assert body["ranked"][0]["facts"]["rent"]["is_sample"] is True
    assert body["ranked"][0]["full_day"]["campus_to_job"] == 15
    assert body["ranked"][0]["full_day"]["total_minutes"] == "UNKNOWN"
    (ostpark,) = body["unchecked"]
    assert ostpark["facts"]["rent"] == "UNKNOWN"
    assert "facts" in response.headers["Server-Timing"]


def test_area_detail_on_the_database(client: TestClient, world: World) -> None:
    body = client.get(f"{V1}/areas/{world.altstadt}", params={"campus_id": world.campus_id}).json()

    assert body["area"]["name"] == "Altstadt"
    assert body["facts"]["commute_minutes"] == 20
    # Evening times in the fixture: 10 and 21 minutes, median 15.5, rounded up.
    assert body["return_minutes"] == 16
    assert body["facts"]["rent"]["monthly_eur"] == 720.0
    assert body["listing_hint"] == "Enter 'Altstadt' as the district on the portal."


def test_area_layer_is_built_by_postgis(client: TestClient, world: World) -> None:
    body = client.get(
        f"{V1}/cities/{world.city_id}/layers/areas", params={"campus_id": world.campus_id}
    ).json()

    assert len(body["features"]) == 3
    altstadt = next(f for f in body["features"] if f["id"] == world.altstadt)
    assert altstadt["geometry"]["type"] == "MultiPolygon"
    ring = altstadt["geometry"]["coordinates"][0][0]
    # The fixture square has four corners; the ring repeats the first one.
    assert len(ring) == 5
    assert ring[0] == [11.57, 48.13]
    assert altstadt["properties"]["commute_minutes"] == 20
    ostpark = next(f for f in body["features"] if f["id"] == world.ostpark)
    assert ostpark["properties"]["rent_eur"] == "UNKNOWN"


def test_cell_layers_on_the_database(client: TestClient, world: World) -> None:
    def values(metric: str) -> dict[str, object]:
        body = client.get(
            f"{V1}/cities/{world.city_id}/layers/cells",
            params={"metric": metric, "campus_id": world.campus_id},
        ).json()
        return {f["id"]: f["properties"]["value"] for f in body["features"]}

    commute, jobs, amenities = values("commute"), values("job_access"), values("amenities")

    assert len(commute) == 5
    assert (commute[A1], commute[B2]) == (10, "UNKNOWN")
    assert (jobs[A1], jobs[B2]) == (0.2, "UNKNOWN")
    # Two cafes in A1; B2 has no places, which is a real zero.
    assert (amenities[A1], amenities[B2]) == (2, 0)


def test_sources_report_when_travel_times_were_computed(client: TestClient, world: World) -> None:
    sources = client.get(f"{V1}/cities/{world.city_id}/sources").json()

    travel = [s for s in sources if s["used_for"] == "Travel times"]
    rents = [s for s in sources if s["used_for"] == "Rent estimates"]
    assert {s["as_of"] for s in travel} == {"2026-01-02"}
    assert [(s["name"], s["is_sample"]) for s in rents] == [
        ("official report", False),
        ("sample fixture", True),
    ]


def test_comparison_on_the_database(client: TestClient, world: World) -> None:
    body = client.get(
        f"{V1}/cities/{world.city_id}/comparison",
        params={"max_rent_eur": 800, "max_commute_minutes": 40},
    ).json()

    assert body["total_areas"] == 3
    assert body["universities"][0]["feasible"] == 2

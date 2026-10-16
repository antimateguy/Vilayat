"""Every v1 endpoint over HTTP, on in-memory data: no database, no network."""

from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.unit.api_client import V1, make_client
from tests.unit.engine_world import (
    ALTSTADT,
    CELL_COUNT,
    CELLS,
    EMPLOYER,
    EMPLOYER_ELSEWHERE,
    MAIN_CAMPUS,
    NORDEND,
    OSTPARK,
    WESTEND,
)

SEARCH = {"campus_id": MAIN_CAMPUS, "max_commute_minutes": 40, "max_rent_eur": 700}


@pytest.fixture
def client() -> TestClient:
    return make_client()[0]


def names(items: list[dict[str, Any]]) -> list[str]:
    return [item["area"]["name"] for item in items]


# --- Catalog ---------------------------------------------------------------


def test_cities_are_listed(client: TestClient) -> None:
    response = client.get(f"{V1}/cities")

    assert response.status_code == 200
    assert response.json() == [
        {"id": "elsewhere", "name": "Elsewhere"},
        {"id": "testville", "name": "Testville"},
    ]


def test_universities_come_with_their_campuses(client: TestClient) -> None:
    universities = client.get(f"{V1}/cities/testville/universities").json()

    assert [(u["short_name"], [c["name"] for c in u["campuses"]]) for u in universities] == [
        ("FU", ["Main Campus"]),
        ("SU", ["East Campus", "North Campus"]),
    ]
    assert universities[0]["campuses"][0] == {
        "id": MAIN_CAMPUS,
        "university_id": 1,
        "name": "Main Campus",
        "lat": 48.1,
        "lon": 11.5,
    }


def test_employers_say_when_they_are_sample_data(client: TestClient) -> None:
    assert client.get(f"{V1}/cities/testville/employers").json() == [
        {"id": EMPLOYER, "name": "Example Works", "lat": 48.1, "lon": 11.5, "is_sample": True}
    ]


def test_sources_list_every_dataset_with_publisher_licence_and_date(client: TestClient) -> None:
    sources = client.get(f"{V1}/cities/testville/sources").json()

    by_use: dict[str, list[dict[str, Any]]] = {}
    for source in sources:
        by_use.setdefault(source["used_for"], []).append(source)
    assert set(by_use) == {
        "Area boundaries",
        "Campus locations",
        "Amenities, job access and job hotspots",
        "Travel times",
        "Rent estimates",
        "Employer sites",
    }
    assert by_use["Amenities, job access and job hotspots"][0]["as_of"] == "2026-10-05"
    assert [(s["publisher"], s["licence"]) for s in by_use["Travel times"]] == [
        ("Testville Transit", "CC BY"),
        ("OpenStreetMap", "ODbL"),
    ]
    # No travel times have been computed in this fixture, and the API says so.
    assert {s["as_of"] for s in by_use["Travel times"]} == {"UNKNOWN"}
    assert [(s["name"], s["is_sample"]) for s in by_use["Rent estimates"]] == [
        ("Housing report", False),
        ("sample fixture", True),
    ]
    assert by_use["Employer sites"][0]["is_sample"] is True


@pytest.mark.parametrize("path", ["universities", "employers", "sources"])
def test_an_unknown_city_is_a_404(client: TestClient, path: str) -> None:
    response = client.get(f"{V1}/cities/atlantis/{path}")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"
    assert response.json()["error"]["message"] == "no city with id atlantis"


# --- Search ----------------------------------------------------------------


def test_search_returns_three_groups(client: TestClient) -> None:
    response = client.post(f"{V1}/search", json=SEARCH)

    assert response.status_code == 200
    body = response.json()
    assert body["city_id"] == "testville"
    assert body["campus"]["name"] == "Main Campus"
    assert names(body["ranked"]) == ["Altstadt", "Nordend", "Ostpark"]
    assert names(body["excluded"]) == ["Fernweh", "Teuerberg"]
    assert names(body["unchecked"]) == ["Niemandsland", "Westend"]


def test_a_ranked_area_carries_facts_score_reasons_and_trade_off(client: TestClient) -> None:
    top = client.post(f"{V1}/search", json=SEARCH).json()["ranked"][0]

    assert top["rank"] == 1
    assert top["area"] == {"id": ALTSTADT, "name": "Altstadt"}
    assert top["facts"] == {
        "cell_count": 4,
        "rent": {
            "monthly_eur": 680.0,
            "basis": "median asking rent, 1-room flat",
            "source": "Housing report",
            "source_url": None,
            "as_of": "2026-01-01",
            "is_sample": False,
        },
        "commute_minutes": 10,
        "amenities": {"cafe": 20, "gym": 3, "library": 1, "supermarket": 6},
        "job_access": {"score": 0.95, "places_nearby": 500},
    }
    assert top["score"]["total"] == pytest.approx(0.5157, abs=1e-3)
    assert [(c["name"], c["share"]) for c in top["score"]["components"]] == [
        ("commute", 0.35),
        ("rent", 0.35),
        ("amenities", 0.15),
        ("job_access", 0.15),
    ]
    assert len(top["reasons"]) == 4
    assert top["trade_off"].startswith("Weakest point is rent")
    assert top["full_day"] is None


def test_a_missing_figure_is_the_string_unknown_never_null(client: TestClient) -> None:
    body = client.post(f"{V1}/search", json=SEARCH).json()
    unchecked = {item["area"]["name"]: item for item in body["unchecked"]}

    assert unchecked["Westend"]["facts"]["rent"] == "UNKNOWN"
    assert unchecked["Westend"]["missing"] == ["No rent figure is known for this area."]
    assert unchecked["Niemandsland"]["facts"]["commute_minutes"] == "UNKNOWN"
    assert unchecked["Westend"]["facts"]["job_access"] == "UNKNOWN"
    # Places data is loaded, so "no amenities" here is a real zero, not unknown.
    assert unchecked["Westend"]["facts"]["amenities"] == {
        "cafe": 0,
        "gym": 0,
        "library": 0,
        "supermarket": 0,
    }


def test_excluded_areas_say_which_limit_they_break(client: TestClient) -> None:
    excluded = client.post(f"{V1}/search", json=SEARCH).json()["excluded"]

    assert {item["area"]["name"]: item["violations"] for item in excluded} == {
        "Fernweh": ["Commute of 70 min is over your 40 min limit."],
        "Teuerberg": ["Rent of 900 EUR is over your 700 EUR ceiling."],
    }


def test_weights_can_be_sent_as_slider_positions(client: TestClient) -> None:
    by_rent = client.post(
        f"{V1}/search",
        json=SEARCH | {"weights": {"commute": 0, "rent": 100, "amenities": 0, "job_access": 0}},
    ).json()

    assert names(by_rent["ranked"]) == ["Ostpark", "Nordend", "Altstadt"]
    assert by_rent["ranked"][0]["score"]["components"][1]["share"] == 1.0


def test_a_pinned_employer_adds_full_day_travel(client: TestClient) -> None:
    ranked = client.post(f"{V1}/search", json=SEARCH | {"employer_id": EMPLOYER}).json()["ranked"]

    assert names(ranked) == ["Altstadt", "Nordend", "Ostpark"]
    assert ranked[0]["full_day"] == {
        "employer": {"id": EMPLOYER, "name": "Example Works"},
        "home_to_campus": 10,
        "campus_to_job": 15,
        "job_to_home": 18,
        "campus_to_home": 12,
        "total_minutes": 43,
        "extra_minutes": 21,
    }
    assert ranked[2]["full_day"]["job_to_home"] == "UNKNOWN"
    assert ranked[2]["full_day"]["total_minutes"] == "UNKNOWN"


def test_search_works_without_places_data() -> None:
    client, _ = make_client(with_places=False)

    ranked = client.post(f"{V1}/search", json=SEARCH).json()["ranked"]

    assert len(ranked) == 3
    assert ranked[0]["facts"]["amenities"] == "UNKNOWN"
    assert ranked[0]["score"]["components"][2] == {
        "name": "amenities",
        "value": "UNKNOWN",
        "share": 0.0,
        "reason": "Everyday amenities are unknown.",
    }


@pytest.mark.parametrize(
    ("change", "field"),
    [
        ({"max_commute_minutes": 0}, "max_commute_minutes"),
        ({"max_commute_minutes": 181}, "max_commute_minutes"),
        ({"max_rent_eur": -5}, "max_rent_eur"),
        ({"min_job_access": 1.5}, "min_job_access"),
        ({"weights": {"rent": -1}}, "weights.rent"),
        ({"weights": {"rents": 1}}, "weights.rents"),
        ({"radius_km": 3}, "radius_km"),
        ({"campus_id": "main"}, "campus_id"),
    ],
)
def test_an_invalid_search_names_the_field(
    client: TestClient, change: dict[str, Any], field: str
) -> None:
    response = client.post(f"{V1}/search", json=SEARCH | change)

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "invalid_request"
    assert field in [detail["field"] for detail in error["details"]]


def test_a_search_without_required_fields_lists_them(client: TestClient) -> None:
    error = client.post(f"{V1}/search", json={}).json()["error"]

    assert {detail["field"] for detail in error["details"]} == {
        "campus_id",
        "max_commute_minutes",
        "max_rent_eur",
    }


def test_all_weights_at_zero_are_refused(client: TestClient) -> None:
    zero = {"commute": 0, "rent": 0, "amenities": 0, "job_access": 0}

    response = client.post(f"{V1}/search", json=SEARCH | {"weights": zero})

    assert response.status_code == 422
    assert response.json()["error"]["message"] == "at least one weight must be above zero"


def test_an_unknown_campus_or_employer_is_a_404(client: TestClient) -> None:
    campus = client.post(f"{V1}/search", json=SEARCH | {"campus_id": 999})
    employer = client.post(f"{V1}/search", json=SEARCH | {"employer_id": 999})

    assert (campus.status_code, campus.json()["error"]["message"]) == (404, "no campus with id 999")
    assert (employer.status_code, employer.json()["error"]["message"]) == (
        404,
        "no employer with id 999",
    )


def test_an_employer_in_another_city_is_a_422(client: TestClient) -> None:
    response = client.post(f"{V1}/search", json=SEARCH | {"employer_id": EMPLOYER_ELSEWHERE})

    assert response.status_code == 422
    assert "Far Works is in elsewhere" in response.json()["error"]["message"]


# --- Area detail -----------------------------------------------------------


def test_area_detail_for_a_campus(client: TestClient) -> None:
    body = client.get(f"{V1}/areas/{ALTSTADT}", params={"campus_id": MAIN_CAMPUS}).json()

    assert body["area"] == {"id": ALTSTADT, "name": "Altstadt"}
    assert body["city_id"] == "testville"
    assert body["campus"]["id"] == MAIN_CAMPUS
    assert body["facts"]["commute_minutes"] == 10
    assert body["return_minutes"] == 12
    assert body["listing_portals"] == [
        {
            "name": "Flatfinder",
            "offers": "Rooms in shared flats",
            "url": "https://example.org/testville",
        }
    ]
    assert body["listing_hint"] == "Enter 'Altstadt' as the district on the portal."


def test_area_detail_without_a_campus_has_no_commute(client: TestClient) -> None:
    body = client.get(f"{V1}/areas/{ALTSTADT}").json()

    assert body["campus"] is None
    assert body["facts"]["commute_minutes"] == "UNKNOWN"
    assert body["return_minutes"] == "UNKNOWN"
    assert body["facts"]["rent"]["monthly_eur"] == 680.0


@pytest.mark.parametrize(
    ("path", "status", "message"),
    [
        ("/areas/999", 404, "no area with id 999"),
        (f"/areas/{ALTSTADT}?campus_id=999", 404, "no campus with id 999"),
        (f"/areas/99?campus_id={MAIN_CAMPUS}", 422, "Faraway is in elsewhere"),
    ],
)
def test_area_detail_errors(client: TestClient, path: str, status: int, message: str) -> None:
    response = client.get(f"{V1}{path}")

    assert response.status_code == status
    assert message in response.json()["error"]["message"]


def test_area_ids_must_be_positive_numbers(client: TestClient) -> None:
    assert client.get(f"{V1}/areas/0").status_code == 422
    assert client.get(f"{V1}/areas/altstadt").status_code == 422


# --- Comparison ------------------------------------------------------------


def test_comparison_counts_feasible_areas_per_university_and_campus(client: TestClient) -> None:
    response = client.get(
        f"{V1}/cities/testville/comparison",
        params={"max_rent_eur": 700, "max_commute_minutes": 40},
    )

    assert response.status_code == 200
    body = response.json()
    assert (body["max_rent_eur"], body["max_commute_minutes"], body["total_areas"]) == (700, 40, 7)
    first, second = body["universities"]
    assert (first["university"]["short_name"], first["feasible"]) == ("FU", 3)
    assert first["campuses"][0]["feasible_area_ids"] == [ALTSTADT, NORDEND, OSTPARK]
    assert (second["university"]["short_name"], second["feasible"]) == ("SU", 3)
    assert [
        (c["campus"]["name"], c["feasible"], c["excluded"], c["unchecked"])
        for c in second["campuses"]
    ] == [
        ("East Campus", 1, 1, 5),
        ("North Campus", 2, 2, 3),
    ]


@pytest.mark.parametrize(
    "params",
    [
        {},
        {"max_rent_eur": 700},
        {"max_rent_eur": 0, "max_commute_minutes": 40},
        {"max_rent_eur": 700, "max_commute_minutes": 500},
    ],
)
def test_comparison_needs_both_limits_in_range(client: TestClient, params: dict[str, int]) -> None:
    assert client.get(f"{V1}/cities/testville/comparison", params=params).status_code == 422


def test_comparison_of_an_unknown_city_is_a_404(client: TestClient) -> None:
    response = client.get(
        f"{V1}/cities/atlantis/comparison", params={"max_rent_eur": 700, "max_commute_minutes": 40}
    )

    assert response.status_code == 404


# --- Map layers ------------------------------------------------------------


def test_area_layer_is_a_geojson_feature_collection(client: TestClient) -> None:
    body = client.get(
        f"{V1}/cities/testville/layers/areas", params={"campus_id": MAIN_CAMPUS}
    ).json()

    assert body["type"] == "FeatureCollection"
    assert len(body["features"]) == 7
    by_id = {feature["id"]: feature for feature in body["features"]}
    altstadt = by_id[ALTSTADT]
    assert altstadt["type"] == "Feature"
    assert altstadt["geometry"]["type"] == "MultiPolygon"
    assert altstadt["properties"] == {
        "area_id": ALTSTADT,
        "name": "Altstadt",
        "cell_count": 4,
        "rent_eur": 680.0,
        "rent_is_sample": False,
        "commute_minutes": 10,
        "amenities_total": 30,
        "job_access_score": 0.95,
    }
    assert by_id[NORDEND]["properties"]["rent_is_sample"] is True
    assert by_id[WESTEND]["properties"]["rent_eur"] == "UNKNOWN"


def test_area_layer_without_a_campus_has_unknown_commutes(client: TestClient) -> None:
    features = client.get(f"{V1}/cities/testville/layers/areas").json()["features"]

    assert {feature["properties"]["commute_minutes"] for feature in features} == {"UNKNOWN"}


def test_cell_layer_draws_one_hexagon_per_cell(client: TestClient) -> None:
    body = client.get(f"{V1}/cities/testville/layers/cells", params={"metric": "job_access"}).json()

    assert (body["type"], body["metric"]) == ("FeatureCollection", "job_access")
    assert len(body["features"]) == CELL_COUNT
    first = next(f for f in body["features"] if f["id"] == CELLS[ALTSTADT][0])
    assert first["properties"] == {"cell": CELLS[ALTSTADT][0], "area_id": ALTSTADT, "value": 0.95}
    ring = first["geometry"]["coordinates"][0]
    assert first["geometry"]["type"] == "Polygon"
    # Six corners plus the first one repeated; longitude (about 11.5) comes first.
    assert len(ring) == 7
    assert ring[0] == ring[-1]
    assert all(11 < lon < 12 and 48 < lat < 49 for lon, lat in ring)
    unscored = next(f for f in body["features"] if f["id"] == CELLS[OSTPARK][0])
    assert unscored["properties"]["value"] == "UNKNOWN"


def test_commute_cell_layer_needs_a_campus(client: TestClient) -> None:
    without = client.get(f"{V1}/cities/testville/layers/cells", params={"metric": "commute"})
    with_campus = client.get(
        f"{V1}/cities/testville/layers/cells",
        params={"metric": "commute", "campus_id": MAIN_CAMPUS},
    )

    assert without.status_code == 422
    assert without.json()["error"]["message"] == "the commute layer needs a campus_id"
    values = {f["id"]: f["properties"]["value"] for f in with_campus.json()["features"]}
    assert values[CELLS[ALTSTADT][0]] == 8
    assert values[CELLS[ALTSTADT][1]] == 12
    assert values[CELLS[ALTSTADT][2]] == "UNKNOWN"


def test_amenity_cell_layer_counts_only_amenities_and_shows_real_zeros(client: TestClient) -> None:
    features = client.get(
        f"{V1}/cities/testville/layers/cells", params={"metric": "amenities"}
    ).json()["features"]
    values = {f["id"]: f["properties"]["value"] for f in features}

    # 5 cafes and 1 supermarket; the 9 bars are not everyday amenities.
    assert values[CELLS[ALTSTADT][0]] == 6
    assert values[CELLS[NORDEND][0]] == 0


def test_amenity_cell_layer_is_unknown_without_places_data() -> None:
    client, _ = make_client(with_places=False)

    features = client.get(
        f"{V1}/cities/testville/layers/cells", params={"metric": "amenities"}
    ).json()["features"]

    assert {f["properties"]["value"] for f in features} == {"UNKNOWN"}


def test_an_unknown_metric_or_city_is_refused(client: TestClient) -> None:
    metric = client.get(f"{V1}/cities/testville/layers/cells", params={"metric": "noise"})
    city = client.get(f"{V1}/cities/atlantis/layers/areas")

    assert (metric.status_code, city.status_code) == (422, 404)

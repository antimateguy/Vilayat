"""What every endpoint has in common: request IDs, timing, errors, rate limiting, CORS, docs."""

import logging
import re

import pytest
from fastapi.testclient import TestClient

from api.dependencies import get_catalog
from api.rate_limit import SlidingWindowRateLimiter
from infrastructure.settings import Settings
from tests.unit.api_client import V1, make_client
from tests.unit.engine_world import MAIN_CAMPUS

SEARCH = {"campus_id": MAIN_CAMPUS, "max_commute_minutes": 40, "max_rent_eur": 700}


@pytest.fixture
def client() -> TestClient:
    return make_client()[0]


# --- Request IDs and timing ------------------------------------------------


def test_every_response_gets_a_request_id(client: TestClient) -> None:
    first = client.get(f"{V1}/cities").headers["X-Request-ID"]
    second = client.get(f"{V1}/cities").headers["X-Request-ID"]

    assert re.fullmatch(r"[0-9a-f]{32}", first)
    assert first != second


def test_a_callers_request_id_is_kept_if_it_is_harmless(client: TestClient) -> None:
    kept = client.get(f"{V1}/cities", headers={"X-Request-ID": "frontend-42.a_b"})
    replaced = client.get(f"{V1}/cities", headers={"X-Request-ID": "bad id\twith spaces"})

    assert kept.headers["X-Request-ID"] == "frontend-42.a_b"
    assert re.fullmatch(r"[0-9a-f]{32}", replaced.headers["X-Request-ID"])


def test_an_error_body_carries_the_same_request_id_as_the_header(client: TestClient) -> None:
    response = client.get(f"{V1}/areas/999")

    assert response.status_code == 404
    assert response.json()["error"]["request_id"] == response.headers["X-Request-ID"]


def test_server_timing_reports_each_stage_of_a_search(client: TestClient) -> None:
    header = client.post(f"{V1}/search", json=SEARCH).headers["Server-Timing"]

    stages = [part.split(";")[0] for part in header.split(", ")]
    assert stages == ["catalog", "facts", "constraints", "ranking", "total"]
    assert all(re.fullmatch(r"\w+;dur=\d+\.\d", part) for part in header.split(", "))


def test_each_request_writes_one_log_line_with_id_status_and_stages(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.INFO, logger="api.requests"):
        response = client.post(f"{V1}/search", json=SEARCH)

    (line,) = [record.getMessage() for record in caplog.records if record.name == "api.requests"]
    assert f"request_id={response.headers['X-Request-ID']}" in line
    assert "method=POST path=/api/v1/search status=200" in line
    assert re.search(r"total_ms=\d+\.\d stages=catalog=\d", line)


# --- Errors ----------------------------------------------------------------


def test_every_error_has_the_same_shape(client: TestClient) -> None:
    responses = [
        client.get(f"{V1}/areas/999"),
        client.post(f"{V1}/search", json={}),
        client.get(f"{V1}/no-such-endpoint"),
        client.put(f"{V1}/cities"),
    ]

    assert [r.status_code for r in responses] == [404, 422, 404, 405]
    for response in responses:
        error = response.json()["error"]
        assert set(error) == {"code", "message", "request_id", "details"}
        assert set(response.json()) == {"error"}


def test_an_unexpected_failure_is_a_500_that_reveals_nothing() -> None:
    client, _ = make_client(raise_server_exceptions=False)

    def broken() -> None:
        raise RuntimeError("password=hunter2 connection refused")

    client.app.dependency_overrides[get_catalog] = broken  # type: ignore[attr-defined]
    response = client.get(f"{V1}/cities")

    assert response.status_code == 500
    error = response.json()["error"]
    assert error["code"] == "internal_error"
    assert error["message"] == "Something went wrong on the server."
    assert "hunter2" not in response.text
    assert re.fullmatch(r"[0-9a-f]{32}", error["request_id"])


# --- Rate limiting ---------------------------------------------------------


def test_the_limiter_allows_the_limit_and_then_says_how_long_to_wait() -> None:
    now = [100.0]
    limiter = SlidingWindowRateLimiter(limit=3, window_seconds=60, clock=lambda: now[0])

    assert [limiter.check("a") for _ in range(3)] == [0, 0, 0]
    now[0] = 110.0
    assert limiter.check("a") == 50  # the first request leaves the window at 160
    assert limiter.check("b") == 0  # another client is counted separately


def test_the_limiter_window_slides() -> None:
    now = [0.0]
    limiter = SlidingWindowRateLimiter(limit=2, window_seconds=60, clock=lambda: now[0])
    limiter.check("a")
    now[0] = 30.0
    limiter.check("a")

    now[0] = 59.0
    assert limiter.check("a") > 0
    now[0] = 60.0  # the request made at 0 has left the window
    assert limiter.check("a") == 0
    assert limiter.check("a") > 0


def test_too_many_requests_get_a_429_with_retry_after() -> None:
    client, _ = make_client(rate_limit_per_minute=3)

    statuses = [client.get(f"{V1}/cities").status_code for _ in range(4)]
    refused = client.get(f"{V1}/cities")

    assert statuses == [200, 200, 200, 429]
    assert refused.json()["error"]["code"] == "rate_limited"
    assert 1 <= int(refused.headers["Retry-After"]) <= 60
    assert refused.json()["error"]["request_id"] == refused.headers["X-Request-ID"]


def test_clients_are_told_apart_by_the_forwarded_address() -> None:
    client, _ = make_client(rate_limit_per_minute=1)
    alice, bob = {"X-Forwarded-For": "203.0.113.5, 10.0.0.1"}, {"X-Forwarded-For": "203.0.113.9"}

    assert client.get(f"{V1}/cities", headers=alice).status_code == 200
    assert client.get(f"{V1}/cities", headers=alice).status_code == 429
    assert client.get(f"{V1}/cities", headers=bob).status_code == 200


def test_the_health_check_is_never_rate_limited_and_zero_switches_the_limit_off() -> None:
    limited, _ = make_client(rate_limit_per_minute=1)
    limited.get(f"{V1}/cities")
    unlimited, _ = make_client(rate_limit_per_minute=0)

    assert all(limited.get("/health").status_code == 200 for _ in range(5))
    assert all(unlimited.get(f"{V1}/cities").status_code == 200 for _ in range(50))
    assert Settings().rate_limit_per_minute == 120


# --- CORS and compression --------------------------------------------------


def test_the_frontend_origin_may_call_the_api_and_read_the_extra_headers(
    client: TestClient,
) -> None:
    origin = {"Origin": "http://localhost:3000"}

    preflight = client.options(
        f"{V1}/search",
        headers=origin
        | {
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    response = client.get(f"{V1}/cities", headers=origin)

    assert preflight.status_code == 200
    assert preflight.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert "X-Request-ID" in response.headers["access-control-expose-headers"]
    assert "Server-Timing" in response.headers["access-control-expose-headers"]


def test_large_responses_are_compressed(client: TestClient) -> None:
    layer = client.get(
        f"{V1}/cities/testville/layers/cells",
        params={"metric": "job_access"},
        headers={"Accept-Encoding": "gzip"},
    )

    assert layer.headers["content-encoding"] == "gzip"
    assert len(layer.json()["features"]) > 0


# --- OpenAPI documentation -------------------------------------------------

EXPECTED_OPERATIONS = {
    ("get", "/health"),
    ("get", "/health/live"),
    ("get", "/api/v1/cities"),
    ("get", "/api/v1/cities/{city_id}/universities"),
    ("get", "/api/v1/cities/{city_id}/employers"),
    ("get", "/api/v1/cities/{city_id}/sources"),
    ("get", "/api/v1/cities/{city_id}/comparison"),
    ("get", "/api/v1/cities/{city_id}/layers/areas"),
    ("get", "/api/v1/cities/{city_id}/layers/cells"),
    ("get", "/api/v1/cities/{city_id}/layers/transit"),
    ("get", "/api/v1/areas/{area_id}"),
    ("get", "/api/v1/areas/{area_id}/commute"),
    ("post", "/api/v1/search"),
    ("get", "/api/v1/ai/status"),
    ("post", "/api/v1/intent"),
    ("post", "/api/v1/ask"),
    ("get", "/api/v1/areas/{area_id}/briefing"),
}


def test_the_documentation_covers_every_endpoint(client: TestClient) -> None:
    spec = client.get("/openapi.json").json()
    operations = {(method, path) for path, methods in spec["paths"].items() for method in methods}

    assert operations == EXPECTED_OPERATIONS
    assert client.get("/docs").status_code == 200


def test_every_operation_is_described_and_typed(client: TestClient) -> None:
    spec = client.get("/openapi.json").json()

    for path, methods in spec["paths"].items():
        for method, operation in methods.items():
            where = f"{method.upper()} {path}"
            assert operation.get("summary"), where
            assert operation.get("tags"), where
            ok = operation["responses"]["200"]["content"]["application/json"]["schema"]
            assert ok, where
            if path.startswith("/api/v1"):
                assert {"429", "500"} <= set(operation["responses"]), where


def test_the_documentation_states_the_unknown_convention_and_the_error_shape(
    client: TestClient,
) -> None:
    spec = client.get("/openapi.json").json()
    schemas = spec["components"]["schemas"]

    assert '"UNKNOWN"' in spec["info"]["description"]
    commute = schemas["FactsOut"]["properties"]["commute_minutes"]
    assert {"const": "UNKNOWN", "type": "string"} in commute["anyOf"]
    assert set(schemas["ErrorBody"]["properties"]) == {"code", "message", "request_id", "details"}
    search_errors = spec["paths"]["/api/v1/search"]["post"]["responses"]
    assert search_errors["404"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/ErrorResponse"
    }
    assert "examples" in schemas["SearchIn"]

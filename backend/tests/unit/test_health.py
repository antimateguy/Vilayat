"""The health endpoint with fake probes: no database, no network."""

from fastapi.testclient import TestClient

from api.dependencies import get_health_probes
from api.main import create_app
from infrastructure.fakes.health import FakeHealthProbe
from infrastructure.settings import Settings
from ports.health import HealthProbe


def client_with(*probes: HealthProbe, settings: Settings | None = None) -> TestClient:
    app = create_app(settings)
    app.dependency_overrides[get_health_probes] = lambda: list(probes)
    return TestClient(app)


def test_health_is_ok_when_every_probe_passes() -> None:
    client = client_with(FakeHealthProbe("database", ok=True, detail="postgis 3.6"))

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "checks": {"database": {"ok": True, "detail": "postgis 3.6"}},
    }


def test_health_is_503_when_a_probe_fails() -> None:
    client = client_with(
        FakeHealthProbe("database", ok=False, detail="unreachable"),
        FakeHealthProbe("other", ok=True),
    )

    response = client.get("/health")

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "unavailable"
    assert body["checks"]["database"] == {"ok": False, "detail": "unreachable"}
    assert body["checks"]["other"]["ok"] is True


def test_cors_allows_only_configured_origins() -> None:
    settings = Settings(cors_origins="https://app.example")
    client = client_with(FakeHealthProbe(), settings=settings)

    allowed = client.get("/health", headers={"Origin": "https://app.example"})
    other = client.get("/health", headers={"Origin": "https://evil.example"})

    assert allowed.headers["access-control-allow-origin"] == "https://app.example"
    assert "access-control-allow-origin" not in other.headers


def test_the_liveness_check_never_touches_the_database() -> None:
    client = client_with(FakeHealthProbe("database", ok=False, detail="asleep"))

    response = client.get("/health/live")

    assert (response.status_code, response.json()) == (200, {"status": "ok"})

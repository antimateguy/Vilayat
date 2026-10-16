"""Health checks against the real Compose database (docker compose up -d db)."""

import pytest
from fastapi.testclient import TestClient

from api.main import create_app
from infrastructure.db.engine import create_db_engine
from infrastructure.db.health import PostgresHealthProbe
from infrastructure.settings import Settings

pytestmark = pytest.mark.integration


def test_probe_passes_and_reports_extension_versions() -> None:
    probe = PostgresHealthProbe(create_db_engine(Settings().database_url))

    result = probe.check()

    assert result.ok, result.detail
    assert "postgis" in result.detail
    assert "vector" in result.detail


def test_probe_reports_failure_without_leaking_the_connection_string() -> None:
    # Port 1 has nothing listening, so the connection is refused.
    unreachable = "postgresql+psycopg://user:secret-password@127.0.0.1:1/nothing"
    probe = PostgresHealthProbe(create_db_engine(unreachable))

    result = probe.check()

    assert not result.ok
    assert "unreachable" in result.detail
    assert "secret-password" not in result.detail


def test_health_endpoint_with_real_wiring() -> None:
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"

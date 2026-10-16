import pytest

from infrastructure.settings import Settings


def test_cors_origins_are_split_and_trimmed() -> None:
    settings = Settings(cors_origins=" http://localhost:3000 , https://app.example ,")

    assert settings.cors_origin_list == ["http://localhost:3000", "https://app.example"]


def test_environment_variables_override_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@db:5432/x")

    assert Settings().database_url == "postgresql+psycopg://u:p@db:5432/x"


@pytest.mark.parametrize(
    "given",
    [
        "postgresql://user:secret@host.neon.tech/db?sslmode=require",
        "postgres://user:secret@host.neon.tech/db?sslmode=require",
        "postgresql+psycopg://user:secret@host.neon.tech/db?sslmode=require",
    ],
)
def test_a_hosted_database_address_is_given_the_psycopg_driver(given: str) -> None:
    assert Settings(database_url=given).database_url == (
        "postgresql+psycopg://user:secret@host.neon.tech/db?sslmode=require"
    )


def test_cors_origins_are_matched_however_they_were_typed() -> None:
    settings = Settings(cors_origins=' "https://vilayat.pages.dev/" , http://localhost:3000 ,')

    assert settings.cors_origin_list == ["https://vilayat.pages.dev", "http://localhost:3000"]

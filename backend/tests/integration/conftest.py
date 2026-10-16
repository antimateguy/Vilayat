"""Fixtures for tests that need the Compose database (docker compose up -d db).

The tests use their own database, "<name>_test". It is dropped and re-created at
the start of every run and built by running the Alembic migrations, so each run
also proves that the migrations apply to an empty database. The development
database is never touched.
"""

from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, make_url, text
from sqlalchemy.orm import Session

from infrastructure.db.engine import create_db_engine
from infrastructure.settings import Settings

BACKEND = Path(__file__).resolve().parents[2]


def alembic_config(database_url: str) -> Config:
    config = Config(str(BACKEND / "alembic.ini"))
    config.attributes["database_url"] = database_url
    config.attributes["configure_logging"] = False
    return config


@pytest.fixture(scope="session")
def test_database_url() -> str:
    dev_url = make_url(Settings().database_url)
    test_name = f"{dev_url.database}_test"
    # CREATE/DROP DATABASE cannot run inside a transaction, hence AUTOCOMMIT.
    admin = create_engine(dev_url, isolation_level="AUTOCOMMIT")
    with admin.connect() as connection:
        connection.execute(text(f'DROP DATABASE IF EXISTS "{test_name}" WITH (FORCE)'))
        connection.execute(text(f'CREATE DATABASE "{test_name}"'))
    admin.dispose()
    return dev_url.set(database=test_name).render_as_string(hide_password=False)


@pytest.fixture(scope="session")
def engine(test_database_url: str) -> Iterator[Engine]:
    command.upgrade(alembic_config(test_database_url), "head")
    engine = create_db_engine(test_database_url)
    yield engine
    engine.dispose()


@pytest.fixture
def session(engine: Engine) -> Iterator[Session]:
    """A session inside a transaction that is rolled back after the test,
    so tests cannot see each other's rows."""
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    yield session
    session.close()
    transaction.rollback()
    connection.close()

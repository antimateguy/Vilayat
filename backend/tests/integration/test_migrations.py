"""The migrations build the schema the models describe."""

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from geoalchemy2 import alembic_helpers
from sqlalchemy import Engine, inspect, text

from infrastructure.db.models import Base
from tests.integration.conftest import alembic_config

pytestmark = pytest.mark.integration

EXPECTED_TABLES = {
    "cities",
    "universities",
    "campuses",
    "neighbourhoods",
    "cells",
    "destinations",
    "travel_times",
    "area_rents",
    "places",
    "doc_chunks",
    "area_briefings",
    "destination_travel_times",
    "ai_usage",
    "commute_routes",
    "destination_routes",
}

# For each index: the table, the indexed column and the index method.
INDEX_METHODS = """
    SELECT t.relname, a.attname, am.amname
    FROM pg_index i
    JOIN pg_class c ON c.oid = i.indexrelid
    JOIN pg_class t ON t.oid = i.indrelid
    JOIN pg_am am ON am.oid = c.relam
    JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = ANY(i.indkey)
"""


def test_migrations_create_every_table_of_the_models(engine: Engine) -> None:
    assert set(Base.metadata.tables) == EXPECTED_TABLES
    assert set(inspect(engine).get_table_names()) >= EXPECTED_TABLES


def test_models_and_migrated_schema_do_not_differ(engine: Engine) -> None:
    """Fails when a model changes without a migration (or the other way round)."""
    with engine.connect() as connection:
        context = MigrationContext.configure(
            connection, opts={"include_object": alembic_helpers.include_object}
        )
        differences = compare_metadata(context, Base.metadata)

    assert differences == []


def test_every_spatial_column_has_a_gist_index(engine: Engine) -> None:
    with engine.connect() as connection:
        spatial_columns = {
            (table, column)
            for table, column in connection.execute(
                text("SELECT f_table_name, f_geometry_column FROM geometry_columns")
            )
        }
        gist_indexed = {
            (table, column)
            for table, column, method in connection.execute(text(INDEX_METHODS))
            if method == "gist"
        }

    assert spatial_columns == {
        ("neighbourhoods", "geom"),
        ("cells", "centroid"),
        ("destinations", "geom"),
        ("places", "geom"),
    }
    assert spatial_columns <= gist_indexed


def test_embeddings_have_an_hnsw_index(engine: Engine) -> None:
    with engine.connect() as connection:
        indexed = {tuple(row) for row in connection.execute(text(INDEX_METHODS))}

    assert ("doc_chunks", "embedding", "hnsw") in indexed


def test_downgrade_and_upgrade_again(engine: Engine, test_database_url: str) -> None:
    config = alembic_config(test_database_url)

    command.downgrade(config, "base")
    assert not EXPECTED_TABLES & set(inspect(engine).get_table_names())

    command.upgrade(config, "head")
    assert set(inspect(engine).get_table_names()) >= EXPECTED_TABLES

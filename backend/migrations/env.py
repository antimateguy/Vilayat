"""Alembic environment: connects migrations to the models and the database."""

from logging.config import fileConfig
from typing import Any

from alembic import context
from geoalchemy2 import alembic_helpers
from sqlalchemy import create_engine, pool

from infrastructure.db.models import Base
from infrastructure.settings import Settings

config = context.config

# Skipped when a caller (the test suite) sets up logging itself.
if config.config_file_name is not None and config.attributes.get("configure_logging", True):
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def database_url() -> str:
    """Tests pass their own URL through config.attributes; otherwise use the settings."""
    url: str | None = config.attributes.get("database_url")
    return url or Settings().database_url


def configure(**kwargs: Any) -> None:
    context.configure(
        target_metadata=target_metadata,
        # Ignore PostGIS's own spatial_ref_sys table when comparing with the models.
        include_object=alembic_helpers.include_object,
        render_item=alembic_helpers.render_item,
        **kwargs,
    )


def run_migrations_offline() -> None:
    """Print the SQL instead of running it: `alembic upgrade head --sql`."""
    configure(url=database_url(), literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(database_url(), poolclass=pool.NullPool)
    with engine.connect() as connection:
        configure(connection=connection)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

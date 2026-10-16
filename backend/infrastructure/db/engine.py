"""SQLAlchemy engine factory."""

from sqlalchemy import Engine, create_engine

CONNECT_TIMEOUT_SECONDS = 5


def create_db_engine(database_url: str) -> Engine:
    """Create the engine. No connection is opened until the first query.

    pool_pre_ping tests a pooled connection before reuse, so a connection the
    managed database closed while idle is replaced instead of failing a request.
    """
    return create_engine(
        database_url,
        pool_pre_ping=True,
        connect_args={"connect_timeout": CONNECT_TIMEOUT_SECONDS},
    )

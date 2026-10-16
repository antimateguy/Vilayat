"""SQLAlchemy session factory."""

from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Sessions are short-lived: one per request or per job step.

    expire_on_commit=False keeps loaded objects readable after a commit, which
    matters because repositories hand out plain domain objects built from them.
    """
    return sessionmaker(bind=engine, expire_on_commit=False)

"""Health probe for the PostgreSQL database."""

import logging

from sqlalchemy import Engine, text
from sqlalchemy.exc import SQLAlchemyError

from ports.health import HealthProbe, ProbeResult

logger = logging.getLogger(__name__)

REQUIRED_EXTENSIONS = ("postgis", "vector")


class PostgresHealthProbe(HealthProbe):
    """Passes when the database answers and the required extensions are installed."""

    name = "database"

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def check(self) -> ProbeResult:
        try:
            with self._engine.connect() as connection:
                rows = connection.execute(
                    text("SELECT extname, extversion FROM pg_extension")
                ).all()
        except SQLAlchemyError as exc:
            # The full error can contain the connection string, so it goes to the
            # log only; the response carries just the error type.
            logger.warning("Database health check failed: %s", exc)
            return ProbeResult(self.name, ok=False, detail=f"unreachable ({type(exc).__name__})")

        installed = {row.extname: row.extversion for row in rows}
        missing = [ext for ext in REQUIRED_EXTENSIONS if ext not in installed]
        if missing:
            detail = f"missing extensions: {', '.join(missing)}"
            return ProbeResult(self.name, ok=False, detail=detail)
        versions = ", ".join(f"{ext} {installed[ext]}" for ext in REQUIRED_EXTENSIONS)
        return ProbeResult(self.name, ok=True, detail=versions)

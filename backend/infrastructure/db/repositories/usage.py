"""Daily request counts in PostgreSQL."""

from datetime import date

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session, sessionmaker

from infrastructure.db.models import AiUsageRow
from ports.usage import UsageLedger


class PostgresUsageLedger(UsageLedger):
    """Each call runs in its own short transaction, separate from any request's
    session, so a count is kept even when the request that spent it fails."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._sessions = session_factory

    def take(self, model: str, day: date, limit: int, units: int = 1) -> bool:
        if units > limit:
            return False
        # One statement: insert the day's first requests, or add to the count
        # only while it stays within the limit. Row locking makes concurrent
        # requests queue here, so the limit cannot be overshot.
        statement = (
            insert(AiUsageRow)
            .values(day=day, model=model, requests=units)
            .on_conflict_do_update(
                index_elements=["day", "model"],
                set_={"requests": AiUsageRow.requests + units},
                where=AiUsageRow.requests + units <= limit,
            )
            .returning(AiUsageRow.requests)
        )
        with self._sessions.begin() as session:
            return session.execute(statement).first() is not None

    def used(self, model: str, day: date) -> int:
        with self._sessions() as session:
            count = session.scalar(
                select(AiUsageRow.requests).where(AiUsageRow.day == day, AiUsageRow.model == model)
            )
        return count or 0

    def use_up(self, model: str, day: date, limit: int) -> None:
        statement = (
            insert(AiUsageRow)
            .values(day=day, model=model, requests=limit)
            .on_conflict_do_update(
                index_elements=["day", "model"],
                set_={"requests": limit},
                where=AiUsageRow.requests < limit,
            )
        )
        with self._sessions.begin() as session:
            session.execute(statement)

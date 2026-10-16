"""Area briefings in PostgreSQL."""

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from domain.briefing import AreaBriefing
from infrastructure.db.models import AreaBriefingRow
from ports.briefings import BriefingRepository


class PostgresBriefingRepository(BriefingRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, area_id: int) -> AreaBriefing | None:
        row = self._session.scalar(
            select(AreaBriefingRow).where(AreaBriefingRow.neighbourhood_id == area_id)
        )
        if row is None:
            return None
        return AreaBriefing(
            area_id=row.neighbourhood_id,
            content=row.content,
            facts=row.facts,
            model=row.model,
            generated_at=row.generated_at,
        )

    def save(self, briefing: AreaBriefing) -> None:
        values = {
            "content": briefing.content,
            "facts": dict(briefing.facts),
            "model": briefing.model,
            "generated_at": briefing.generated_at,
        }
        statement = insert(AreaBriefingRow).values(neighbourhood_id=briefing.area_id, **values)
        # One briefing per area: writing a new one replaces the old one.
        self._session.execute(
            statement.on_conflict_do_update(index_elements=["neighbourhood_id"], set_=values)
        )

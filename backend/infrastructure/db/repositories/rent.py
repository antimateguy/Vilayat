"""Area rent estimates from PostgreSQL."""

from collections.abc import Mapping

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import distinct_on
from sqlalchemy.orm import Session, aliased

from domain.area import RentEstimate
from domain.unknown import UNKNOWN, Unknown
from infrastructure.db.models import AreaRentRow, NeighbourhoodRow
from ports.rent import RentProvider


class PostgresRentProvider(RentProvider):
    def __init__(self, session: Session) -> None:
        self._session = session

    def rents_by_area(self, city_id: str) -> Mapping[int, RentEstimate | Unknown]:
        # One row per area (DISTINCT ON, a PostgreSQL feature): a real figure
        # beats a sample figure, and among those the most recent wins.
        best = (
            select(AreaRentRow)
            .ext(distinct_on(AreaRentRow.neighbourhood_id))
            .order_by(
                AreaRentRow.neighbourhood_id,
                AreaRentRow.is_sample,
                AreaRentRow.as_of.desc(),
                AreaRentRow.id.desc(),
            )
            .subquery()
        )
        rent = aliased(AreaRentRow, best)
        # Outer join, so an area without any figure still appears, as UNKNOWN.
        statement = (
            select(NeighbourhoodRow.id, rent)
            .outerjoin(rent, rent.neighbourhood_id == NeighbourhoodRow.id)
            .where(NeighbourhoodRow.city_id == city_id)
        )
        return {
            area_id: UNKNOWN if row is None else _to_estimate(row)
            for area_id, row in self._session.execute(statement)
        }


def _to_estimate(row: AreaRentRow) -> RentEstimate:
    return RentEstimate(
        monthly_eur=row.monthly_rent_eur,
        basis=row.basis,
        source=row.source,
        source_url=row.source_url,
        as_of=row.as_of,
        is_sample=row.is_sample,
    )

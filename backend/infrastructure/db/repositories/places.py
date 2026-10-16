"""Place counts and job access from PostgreSQL."""

import math
from collections.abc import Collection, Iterable, Mapping
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from domain.place import JobAccess, PlaceCategory
from domain.unknown import UNKNOWN, Unknown
from infrastructure.db.models import CellRow, NeighbourhoodRow, PlaceRow
from ports.places import PlacesRepository


class PostgresPlacesRepository(PlacesRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def counts_by_area(
        self, city_id: str, categories: Collection[PlaceCategory]
    ) -> Mapping[int, Mapping[PlaceCategory, int]]:
        # A place belongs to an area through the cell it falls in.
        statement = (
            select(CellRow.neighbourhood_id, PlaceRow.category, func.count())
            .join(CellRow, CellRow.h3_index == PlaceRow.cell_id)
            .where(PlaceRow.city_id == city_id, PlaceRow.category.in_(categories))
            .group_by(CellRow.neighbourhood_id, PlaceRow.category)
        )
        return _nest(self._session.execute(statement))

    def counts_by_cell(
        self, city_id: str, categories: Collection[PlaceCategory]
    ) -> Mapping[str, Mapping[PlaceCategory, int]]:
        statement = (
            select(CellRow.h3_index, PlaceRow.category, func.count())
            .join(CellRow, CellRow.h3_index == PlaceRow.cell_id)
            .where(PlaceRow.city_id == city_id, PlaceRow.category.in_(categories))
            .group_by(CellRow.h3_index, PlaceRow.category)
        )
        return _nest(self._session.execute(statement))

    def snapshot_date(self, city_id: str) -> date | Unknown:
        latest = self._session.scalar(
            select(func.max(PlaceRow.as_of)).where(PlaceRow.city_id == city_id)
        )
        return UNKNOWN if latest is None else latest

    def job_access_by_cell(self, city_id: str) -> Mapping[str, JobAccess]:
        statement = select(
            CellRow.h3_index, CellRow.job_places_nearby, CellRow.job_access_score
        ).where(
            CellRow.city_id == city_id,
            CellRow.job_places_nearby.is_not(None),
            CellRow.job_access_score.is_not(None),
        )
        return {
            cell: JobAccess(places_nearby=nearby, score=score)
            for cell, nearby, score in self._session.execute(statement)
            if nearby is not None and score is not None
        }

    def job_access_by_area(self, city_id: str) -> Mapping[int, JobAccess | Unknown]:
        # Medians ignore unscored cells and are NULL when an area has none. The
        # outer join keeps every area of the city in the result.
        statement = (
            select(
                NeighbourhoodRow.id,
                func.percentile_cont(0.5).within_group(CellRow.job_places_nearby),
                func.percentile_cont(0.5).within_group(CellRow.job_access_score),
            )
            .outerjoin(CellRow, CellRow.neighbourhood_id == NeighbourhoodRow.id)
            .where(NeighbourhoodRow.city_id == city_id)
            .group_by(NeighbourhoodRow.id)
        )
        return {
            area_id: (
                UNKNOWN
                if nearby is None or score is None
                else JobAccess(places_nearby=math.floor(nearby + 0.5), score=score)
            )
            for area_id, nearby, score in self._session.execute(statement)
        }


def _nest[K](rows: Iterable[tuple[K, PlaceCategory, int]]) -> dict[K, dict[PlaceCategory, int]]:
    """Turn (key, category, count) rows into {key: {category: count}}."""
    counts: dict[K, dict[PlaceCategory, int]] = {}
    for key, category, count in rows:
        counts.setdefault(key, {})[category] = count
    return counts

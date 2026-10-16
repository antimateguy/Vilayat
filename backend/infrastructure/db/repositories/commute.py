"""Travel times read from the table the offline job fills."""

import math
from collections.abc import Mapping
from datetime import datetime

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from domain.travel import TimeWindow
from domain.unknown import UNKNOWN, Unknown
from infrastructure.db.models import (
    CellRow,
    DestinationRow,
    DestinationTravelTimeRow,
    NeighbourhoodRow,
    TravelTimeRow,
)
from ports.commute import CommuteProvider


class PrecomputedCommuteProvider(CommuteProvider):
    """No routing happens here: a lookup in travel_times, which is why a search
    answers in milliseconds."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def minutes_by_cell(self, destination_id: int, window: TimeWindow) -> Mapping[str, int]:
        statement = select(TravelTimeRow.cell_id, TravelTimeRow.minutes).where(
            TravelTimeRow.destination_id == destination_id,
            TravelTimeRow.time_window == window,
        )
        return dict(self._session.execute(statement).all())

    def minutes_by_area(
        self, destination_id: int, window: TimeWindow
    ) -> Mapping[int, int | Unknown]:
        # The median ignores cells without a route and is NULL when no cell has
        # one. Outer joins keep every area of the destination's city in the result.
        median = func.percentile_cont(0.5).within_group(TravelTimeRow.minutes)
        statement = (
            select(NeighbourhoodRow.id, median)
            .join(DestinationRow, DestinationRow.city_id == NeighbourhoodRow.city_id)
            .outerjoin(CellRow, CellRow.neighbourhood_id == NeighbourhoodRow.id)
            .outerjoin(
                TravelTimeRow,
                and_(
                    TravelTimeRow.cell_id == CellRow.h3_index,
                    TravelTimeRow.destination_id == DestinationRow.id,
                    TravelTimeRow.time_window == window,
                ),
            )
            .where(DestinationRow.id == destination_id)
            .group_by(NeighbourhoodRow.id)
        )
        return {
            area_id: UNKNOWN if minutes is None else _round_half_up(minutes)
            for area_id, minutes in self._session.execute(statement)
        }

    def minutes_between(
        self, from_destination_id: int, to_destination_id: int, window: TimeWindow
    ) -> int | Unknown:
        minutes = self._session.scalar(
            select(DestinationTravelTimeRow.minutes).where(
                DestinationTravelTimeRow.from_destination_id == from_destination_id,
                DestinationTravelTimeRow.to_destination_id == to_destination_id,
                DestinationTravelTimeRow.time_window == window,
            )
        )
        return UNKNOWN if minutes is None else minutes

    def last_computed(self, city_id: str) -> datetime | Unknown:
        latest = self._session.scalar(
            select(func.max(TravelTimeRow.computed_at))
            .join(DestinationRow, DestinationRow.id == TravelTimeRow.destination_id)
            .where(DestinationRow.city_id == city_id)
        )
        return UNKNOWN if latest is None else latest


def _round_half_up(value: float) -> int:
    """15.5 minutes becomes 16: a commute is never understated."""
    return math.floor(value + 0.5)

"""Typical journeys and per-area commute spread, read from PostgreSQL."""

import math
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from domain.geo import Coordinate
from domain.route import CommuteRoute, CommuteSpread, DestinationRoute, LegMode, RouteLeg
from domain.travel import TimeWindow
from infrastructure.db.models import CellRow, CommuteRouteRow, DestinationRouteRow, TravelTimeRow
from ports.routes import CommuteRouteRepository


class PostgresCommuteRouteRepository(CommuteRouteRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def route(self, area_id: int, destination_id: int) -> CommuteRoute | None:
        row = self._session.get(CommuteRouteRow, (area_id, destination_id))
        if row is None:
            return None
        return CommuteRoute(
            area_id=row.neighbourhood_id,
            destination_id=row.destination_id,
            cell_id=row.cell_id,
            departs_at=row.departs_at,
            total_minutes=row.total_minutes,
            legs=tuple(leg_from_json(leg) for leg in row.legs),
            computed_at=row.computed_at,
        )

    def between(self, from_destination_id: int, to_destination_id: int) -> DestinationRoute | None:
        row = self._session.get(DestinationRouteRow, (from_destination_id, to_destination_id))
        if row is None:
            return None
        return DestinationRoute(
            from_destination_id=row.from_destination_id,
            to_destination_id=row.to_destination_id,
            departs_at=row.departs_at,
            total_minutes=row.total_minutes,
            legs=tuple(leg_from_json(leg) for leg in row.legs),
            computed_at=row.computed_at,
        )

    def spread(self, area_id: int, destination_id: int) -> CommuteSpread | None:
        minutes = TravelTimeRow.minutes
        row = self._session.execute(
            select(
                func.count(minutes),
                func.min(minutes),
                func.percentile_cont(0.5).within_group(minutes),
                func.max(minutes),
            )
            .join(CellRow, CellRow.h3_index == TravelTimeRow.cell_id)
            .where(
                CellRow.neighbourhood_id == area_id,
                TravelTimeRow.destination_id == destination_id,
                TravelTimeRow.time_window == TimeWindow.WEEKDAY_MORNING,
            )
        ).one()
        cells, fastest, median, slowest = row
        if not cells:
            return None
        # Rounded the same way as the area's figure in the ranking.
        return CommuteSpread(cells, fastest, math.floor(median + 0.5), slowest)


def leg_to_json(leg: RouteLeg) -> dict[str, Any]:
    return {
        "mode": leg.mode.value,
        "minutes": leg.minutes,
        "wait_minutes": leg.wait_minutes,
        "distance_m": leg.distance_m,
        "line": leg.line,
        "from_stop": leg.from_stop,
        "to_stop": leg.to_stop,
        "line_colour": leg.line_colour,
        "path": [[point.lon, point.lat] for point in leg.path],
    }


def leg_from_json(data: dict[str, Any]) -> RouteLeg:
    return RouteLeg(
        mode=LegMode(data["mode"]),
        minutes=data["minutes"],
        wait_minutes=data["wait_minutes"],
        distance_m=data["distance_m"],
        path=tuple(Coordinate(lat=lat, lon=lon) for lon, lat in data["path"]),
        line=data.get("line"),
        from_stop=data.get("from_stop"),
        to_stop=data.get("to_stop"),
        line_colour=data.get("line_colour"),
    )

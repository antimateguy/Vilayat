"""An area's commute to one campus: how the times spread, and one typical journey."""

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query

from api.dependencies import get_commute_route_service
from api.errors import INVALID, NOT_FOUND
from api.mappers import area_ref, campus_out
from api.schemas.commute import (
    AreaCommuteOut,
    CommuteRouteOut,
    CommuteSpreadOut,
    RouteLegOut,
)
from api.schemas.search import EmployerRef
from domain.route import CommuteRoute, DestinationRoute, RouteLeg
from services.commute_route import CommuteRouteService

router = APIRouter(tags=["areas"])


@router.get(
    "/areas/{area_id}/commute",
    response_model=AreaCommuteOut,
    responses=NOT_FOUND | INVALID,
    summary="Show how the commute from an area to a campus goes",
    description=(
        "The fastest, median and slowest morning time over the area's hexagons, and one "
        "typical journey step by step (walk, line, walk), planned offline from the hexagon "
        "whose time is closest to the median. Nothing is routed during the request."
    ),
)
def area_commute(
    area_id: Annotated[int, Path(ge=1)],
    campus_id: Annotated[int, Query(ge=1)],
    service: Annotated[CommuteRouteService, Depends(get_commute_route_service)],
    employer_id: Annotated[int | None, Query(ge=1)] = None,
) -> AreaCommuteOut:
    commute = service.get(area_id, campus_id, employer_id)
    spread = commute.spread
    return AreaCommuteOut(
        area=area_ref(commute.area),
        campus=campus_out(commute.campus),
        spread=None
        if spread is None
        else CommuteSpreadOut(
            cells=spread.cells,
            fastest_minutes=spread.fastest,
            median_minutes=spread.median,
            slowest_minutes=spread.slowest,
        ),
        route=None if commute.route is None else _route_out(commute.route),
        employer=None
        if commute.employer is None
        else EmployerRef(id=commute.employer.id, name=commute.employer.name),
        to_job=None if commute.to_job is None else _route_out(commute.to_job),
    )


def _route_out(route: CommuteRoute | DestinationRoute) -> CommuteRouteOut:
    first = route.legs[0].path[0] if route.legs and route.legs[0].path else None
    return CommuteRouteOut(
        departs_at=f"{route.departs_at:%H:%M}",
        total_minutes=route.total_minutes,
        start=[first.lon, first.lat] if first else [],
        legs=[_leg_out(leg) for leg in route.legs],
        computed_at=route.computed_at,
    )


def _leg_out(leg: RouteLeg) -> RouteLegOut:
    return RouteLegOut(
        mode=leg.mode.value,
        minutes=leg.minutes,
        wait_minutes=leg.wait_minutes,
        distance_m=leg.distance_m,
        line=leg.line,
        from_stop=leg.from_stop,
        to_stop=leg.to_stop,
        line_colour=leg.line_colour,
        path={
            "type": "LineString",
            "coordinates": [[point.lon, point.lat] for point in leg.path],
        },
    )

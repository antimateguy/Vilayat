"""Search, area detail and comparison: the decision engine over HTTP."""

from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query

from api.dependencies import (
    RegistryDep,
    get_area_detail_service,
    get_comparison_service,
    get_search_service,
)
from api.errors import INVALID, NOT_FOUND
from api.mappers import area_ref, campus_out, comparison_out, facts_out, search_out
from api.routes.catalog import CityId
from api.schemas.common import or_unknown
from api.schemas.search import (
    AreaDetailOut,
    ComparisonOut,
    ListingPortalOut,
    SearchIn,
    SearchOut,
)
from domain.constraints import MAX_COMMUTE_LIMIT_MINUTES, MAX_RENT_LIMIT_EUR, Constraints
from services.area_detail import AreaDetailService
from services.comparison import ComparisonService
from services.search import SearchRequest, SearchService

router = APIRouter()


@router.post(
    "/search",
    response_model=SearchOut,
    responses=NOT_FOUND | INVALID,
    tags=["search"],
    summary="Rank the areas of a city for a campus, a rent ceiling and a commute limit",
    description=(
        "Every area of the campus's city is returned in exactly one of three groups: "
        "`ranked` (within every limit, best first), `excluded` (breaks a limit, with the reason) "
        "and `unchecked` (a figure needed to check a limit is missing). "
        "The ranking is deterministic: no language model takes part in it."
    ),
)
def search(
    body: SearchIn, service: Annotated[SearchService, Depends(get_search_service)]
) -> SearchOut:
    request = SearchRequest(
        constraints=Constraints(
            campus_id=body.campus_id,
            max_commute_minutes=body.max_commute_minutes,
            max_rent_eur=body.max_rent_eur,
            min_job_access=body.min_job_access,
        ),
        weights=body.weights.model_dump(),
        employer_destination_id=body.employer_id,
    )
    return search_out(service.search(request))


@router.get(
    "/areas/{area_id}",
    response_model=AreaDetailOut,
    responses=NOT_FOUND | INVALID,
    tags=["areas"],
    summary="Show one area in detail, with links to rental portals",
    description="With `campus_id`, the commute to that campus and back is included.",
)
def area_detail(
    area_id: Annotated[int, Path(ge=1)],
    service: Annotated[AreaDetailService, Depends(get_area_detail_service)],
    registry: RegistryDep,
    campus_id: Annotated[int | None, Query(ge=1)] = None,
) -> AreaDetailOut:
    detail = service.get(area_id, campus_id)
    area = detail.facts.area
    return AreaDetailOut(
        area=area_ref(area),
        city_id=area.city_id,
        campus=campus_out(detail.campus) if detail.campus else None,
        facts=facts_out(detail.facts),
        return_minutes=or_unknown(detail.return_minutes),
        listing_portals=[
            ListingPortalOut(name=portal.name, offers=portal.offers, url=portal.url)
            for portal in registry.get(area.city_id).listing_portals
        ],
        listing_hint=f"Enter '{area.name}' as the district on the portal.",
    )


@router.get(
    "/cities/{city_id}/comparison",
    response_model=ComparisonOut,
    responses=NOT_FOUND | INVALID,
    tags=["comparison"],
    summary="Count the feasible areas around each university for one budget",
    description="Uses the same rent and commute checks as the search.",
)
def comparison(
    city_id: CityId,
    max_rent_eur: Annotated[Decimal, Query(gt=0, le=MAX_RENT_LIMIT_EUR, examples=[700])],
    max_commute_minutes: Annotated[int, Query(ge=1, le=MAX_COMMUTE_LIMIT_MINUTES, examples=[40])],
    service: Annotated[ComparisonService, Depends(get_comparison_service)],
) -> ComparisonOut:
    result = service.compare(city_id, max_rent_eur, max_commute_minutes)
    return comparison_out(result, float(max_rent_eur), max_commute_minutes)

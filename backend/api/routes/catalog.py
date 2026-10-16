"""Reference data: cities, universities with campuses, employers and data sources."""

from typing import Annotated

from fastapi import APIRouter, Depends, Path

from api.dependencies import CatalogDep, RegistryDep, get_sources_service
from api.errors import NOT_FOUND
from api.mappers import employer_out, source_out, university_out
from api.schemas.catalog import CityOut, DataSourceOut, EmployerOut, UniversityOut
from domain.destination import DestinationKind
from services.lookup import require_city
from services.sources import SourcesService

router = APIRouter(tags=["catalog"])

CityId = Annotated[
    str, Path(pattern=r"^[a-z][a-z-]{0,31}$", description="City key.", examples=["munich"])
]


@router.get("/cities", response_model=list[CityOut], summary="List the cities the app covers")
def list_cities(catalog: CatalogDep) -> list[CityOut]:
    return [CityOut(id=city.id, name=city.name) for city in catalog.list_cities()]


@router.get(
    "/cities/{city_id}/universities",
    response_model=list[UniversityOut],
    responses=NOT_FOUND,
    summary="List a city's universities with their campuses",
    description="A search is made for a campus, not a university: students commute to a campus.",
)
def list_universities(city_id: CityId, catalog: CatalogDep) -> list[UniversityOut]:
    require_city(catalog, city_id)
    return [
        university_out(university, catalog.list_campuses(university.id))
        for university in catalog.list_universities(city_id)
    ]


@router.get(
    "/cities/{city_id}/employers",
    response_model=list[EmployerOut],
    responses=NOT_FOUND,
    summary="List the employer sites a student can pin",
)
def list_employers(city_id: CityId, catalog: CatalogDep) -> list[EmployerOut]:
    require_city(catalog, city_id)
    employers = catalog.list_destinations(city_id, DestinationKind.EMPLOYER)
    return [employer_out(employer) for employer in employers]


@router.get(
    "/cities/{city_id}/sources",
    response_model=list[DataSourceOut],
    responses=NOT_FOUND,
    summary="List where each dataset of a city comes from and how current it is",
    description="Publisher, licence, date and whether the data is a placeholder sample. "
    "Show this wherever the data is shown.",
)
def list_sources(
    city_id: CityId,
    registry: RegistryDep,
    catalog: CatalogDep,
    sources: Annotated[SourcesService, Depends(get_sources_service)],
) -> list[DataSourceOut]:
    require_city(catalog, city_id)
    return [source_out(source) for source in sources.for_city(registry.get(city_id))]

"""Looking up what a request refers to, with one error for "it does not exist"."""

from domain.city import Campus
from ports.catalog import CatalogRepository
from services.errors import NotFoundError


def campus_and_city(catalog: CatalogRepository, campus_id: int) -> tuple[Campus, str]:
    """The campus and the id of the city it is in."""
    campus = catalog.get_campus(campus_id)
    if campus is None:
        raise NotFoundError(f"no campus with id {campus_id}")
    destination = catalog.get_destination(campus.destination_id)
    if destination is None:
        raise NotFoundError(f"campus {campus_id} has no location")
    return campus, destination.city_id


def require_city(catalog: CatalogRepository, city_id: str) -> None:
    if city_id not in {city.id for city in catalog.list_cities()}:
        raise NotFoundError(f"no city with id {city_id}")

"""How a commute from an area goes: the spread of times and one typical journey."""

from dataclasses import dataclass

from domain.area import Area
from domain.city import Campus
from domain.destination import Destination, DestinationKind
from domain.route import CommuteRoute, CommuteSpread, DestinationRoute
from ports.areas import AreaRepository
from ports.catalog import CatalogRepository
from ports.routes import CommuteRouteRepository
from services.errors import InvalidRequestError, NotFoundError
from services.lookup import campus_and_city


@dataclass(frozen=True)
class AreaCommute:
    area: Area
    campus: Campus
    spread: CommuteSpread | None
    """None when no hexagon of the area has a journey to the campus."""
    route: CommuteRoute | None
    """None until the offline job has planned it."""
    employer: Destination | None = None
    to_job: DestinationRoute | None = None
    """Campus to the pinned employer in the afternoon, when one is pinned and planned."""


class CommuteRouteService:
    """Reads what the offline jobs stored; no routing happens here."""

    def __init__(
        self, catalog: CatalogRepository, areas: AreaRepository, routes: CommuteRouteRepository
    ) -> None:
        self._catalog = catalog
        self._areas = areas
        self._routes = routes

    def get(self, area_id: int, campus_id: int, employer_id: int | None = None) -> AreaCommute:
        area = self._areas.get(area_id)
        if area is None:
            raise NotFoundError(f"no area with id {area_id}")
        campus, campus_city = campus_and_city(self._catalog, campus_id)
        if campus_city != area.city_id:
            raise InvalidRequestError(
                f"{area.name} is in {area.city_id}, the campus is in {campus_city}"
            )
        employer = None
        to_job = None
        if employer_id is not None:
            employer = self._catalog.get_destination(employer_id)
            if employer is None or employer.kind is not DestinationKind.EMPLOYER:
                raise NotFoundError(f"no employer with id {employer_id}")
            if employer.city_id != area.city_id:
                raise InvalidRequestError(
                    f"{employer.name} is in {employer.city_id}, {area.name} in {area.city_id}"
                )
            to_job = self._routes.between(campus.destination_id, employer.id)
        return AreaCommute(
            area=area,
            campus=campus,
            spread=self._routes.spread(area_id, campus.destination_id),
            route=self._routes.route(area_id, campus.destination_id),
            employer=employer,
            to_job=to_job,
        )

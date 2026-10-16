"""Area detail: everything known about one area, optionally seen from a campus."""

from domain.search import AreaDetail
from domain.travel import TimeWindow
from domain.unknown import UNKNOWN, Unknown
from ports.areas import AreaRepository
from ports.catalog import CatalogRepository
from ports.commute import CommuteProvider
from services.errors import InvalidRequestError, NotFoundError
from services.facts import AreaFactsCollector
from services.lookup import campus_and_city
from services.timing import stage


class AreaDetailService:
    def __init__(
        self,
        catalog: CatalogRepository,
        areas: AreaRepository,
        facts: AreaFactsCollector,
        commute: CommuteProvider,
    ) -> None:
        self._catalog = catalog
        self._areas = areas
        self._facts = facts
        self._commute = commute

    def get(self, area_id: int, campus_id: int | None = None) -> AreaDetail:
        area = self._areas.get(area_id)
        if area is None:
            raise NotFoundError(f"no area with id {area_id}")

        campus = None
        return_minutes: int | Unknown = UNKNOWN
        if campus_id is not None:
            campus, campus_city = campus_and_city(self._catalog, campus_id)
            if campus_city != area.city_id:
                raise InvalidRequestError(
                    f"{area.name} is in {area.city_id}, the campus is in {campus_city}"
                )
            with stage("commute"):
                return_minutes = self._commute.minutes_by_area(
                    campus.destination_id, TimeWindow.WEEKDAY_EVENING
                ).get(area_id, UNKNOWN)

        with stage("facts"):
            all_facts = self._facts.collect(area.city_id, campus.destination_id if campus else None)
        facts = next(item for item in all_facts if item.area.id == area_id)
        return AreaDetail(facts=facts, campus=campus, return_minutes=return_minutes)

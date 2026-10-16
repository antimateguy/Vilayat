"""Gathering what is known about every area of a city."""

from collections.abc import Mapping, Sequence

from domain.area import AreaFacts
from domain.place import AMENITY_CATEGORIES
from domain.travel import TimeWindow
from domain.unknown import UNKNOWN, Unknown
from ports.areas import AreaRepository
from ports.commute import CommuteProvider
from ports.places import PlacesRepository
from ports.rent import RentProvider


class AreaFactsCollector:
    """Turns the separate data sources into one AreaFacts per area.

    Everything downstream (constraints, scorers, comparison) reads AreaFacts and
    never touches a repository, so it can be tested with plain objects.
    """

    def __init__(
        self,
        areas: AreaRepository,
        rents: RentProvider,
        commute: CommuteProvider,
        places: PlacesRepository,
    ) -> None:
        self._areas = areas
        self._rents = rents
        self._commute = commute
        self._places = places

    def collect(self, city_id: str, campus_destination_id: int | None) -> list[AreaFacts]:
        """The facts of every area. Without a campus the commute is UNKNOWN."""
        return self.collect_for(city_id, [campus_destination_id])[campus_destination_id]

    def collect_for(
        self, city_id: str, campus_destination_ids: Sequence[int | None]
    ) -> dict[int | None, list[AreaFacts]]:
        """The facts of every area for each of several campuses.

        Rent, amenities and job access do not depend on the campus, so they are
        read once; only the commute is read per campus.
        """
        areas = self._areas.list_by_city(city_id)
        cells = self._areas.cells_by_area(city_id)
        rents = self._rents.rents_by_area(city_id)
        job_access = self._places.job_access_by_area(city_id)
        # Without a places snapshot "no cafes" would be a guess, so it is UNKNOWN.
        # With one, an area missing from the counts really has none.
        has_places = self._places.snapshot_date(city_id) is not UNKNOWN
        amenities = self._places.counts_by_area(city_id, AMENITY_CATEGORIES) if has_places else {}

        result: dict[int | None, list[AreaFacts]] = {}
        for destination_id in campus_destination_ids:
            commute: Mapping[int, int | Unknown] = (
                {}
                if destination_id is None
                else self._commute.minutes_by_area(destination_id, TimeWindow.WEEKDAY_MORNING)
            )
            result[destination_id] = [
                AreaFacts(
                    area=area,
                    cell_count=len(cells.get(area.id, ())),
                    rent=rents.get(area.id, UNKNOWN),
                    commute_minutes=commute.get(area.id, UNKNOWN),
                    amenity_counts=amenities.get(area.id, {}) if has_places else UNKNOWN,
                    job_access=job_access.get(area.id, UNKNOWN),
                )
                for area in areas
            ]
        return result

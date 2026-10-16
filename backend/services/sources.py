"""Data sources: where each dataset of a city comes from and how current it is."""

from cities.base import CityConfig
from domain.destination import DestinationKind
from domain.source import DataSource
from domain.unknown import UNKNOWN
from ports.catalog import CatalogRepository
from ports.commute import CommuteProvider
from ports.places import PlacesRepository
from ports.rent import RentProvider

OSM_PUBLISHER = "OpenStreetMap contributors"
OSM_LICENCE = "ODbL"
OSM_URL = "https://www.openstreetmap.org/copyright"


class SourcesService:
    """Combines the city's configuration (publishers, licences) with what is
    actually loaded (dates, sample flags), so the list never claims data that
    is not there."""

    def __init__(
        self,
        catalog: CatalogRepository,
        rents: RentProvider,
        places: PlacesRepository,
        commute: CommuteProvider,
    ) -> None:
        self._catalog = catalog
        self._rents = rents
        self._places = places
        self._commute = commute

    def for_city(self, city: CityConfig) -> list[DataSource]:
        boundaries = city.boundaries
        sources = [
            DataSource(
                used_for="Area boundaries",
                name=boundaries.dataset,
                publisher=boundaries.publisher,
                licence=boundaries.licence,
                as_of=boundaries.retrieved_on,
                url=boundaries.url,
            ),
            DataSource(
                used_for="Campus locations",
                name=city.campus_source,
                publisher=OSM_PUBLISHER,
                licence=OSM_LICENCE,
                as_of=city.campus_as_of,
                url=city.campus_source_url,
            ),
            DataSource(
                used_for="Amenities, job access and job hotspots",
                name="OpenStreetMap places",
                publisher=OSM_PUBLISHER,
                licence=OSM_LICENCE,
                as_of=self._places.snapshot_date(city.id),
                url=OSM_URL,
            ),
        ]

        computed = self._commute.last_computed(city.id)
        computed_on = UNKNOWN if computed is UNKNOWN else computed.date()
        for feed in (*city.feeds.gtfs, city.feeds.streets):
            sources.append(
                DataSource(
                    used_for="Travel times",
                    name=feed.file,
                    publisher=feed.publisher,
                    licence=feed.licence,
                    as_of=computed_on,
                    url=feed.url,
                )
            )

        rents = {
            (rent.source, rent.as_of, rent.is_sample, rent.source_url)
            for rent in self._rents.rents_by_area(city.id).values()
            if rent is not UNKNOWN
        }
        for name, as_of, is_sample, url in sorted(rents, key=lambda item: (item[2], item[0])):
            sources.append(
                DataSource(
                    used_for="Rent estimates",
                    name=name,
                    publisher=name,
                    licence="not stated",
                    as_of=as_of,
                    is_sample=is_sample,
                    url=url,
                )
            )

        employers = {
            (employer.source or "not stated", employer.as_of, employer.is_sample)
            for employer in self._catalog.list_destinations(city.id, DestinationKind.EMPLOYER)
        }
        for name, employer_as_of, is_sample in sorted(employers, key=lambda item: item[0]):
            sources.append(
                DataSource(
                    used_for="Employer sites",
                    name=name,
                    publisher=name,
                    licence="not stated",
                    as_of=UNKNOWN if employer_as_of is None else employer_as_of,
                    is_sample=is_sample,
                )
            )
        return sources

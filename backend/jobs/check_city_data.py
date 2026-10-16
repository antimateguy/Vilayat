"""Report what is loaded for each city: every area with its cells, rent, amenities
and job access, each either a figure or UNKNOWN.

Run for every city:  uv run python -m jobs.check_city_data
Run for one city:    uv run python -m jobs.check_city_data --city berlin --list
"""

import argparse
from collections.abc import Mapping
from dataclasses import dataclass

from cities.registry import discover_cities
from domain.area import Area, RentEstimate
from domain.destination import DestinationKind
from domain.place import AMENITY_CATEGORIES, JobAccess, PlaceCategory
from domain.unknown import UNKNOWN, Unknown
from infrastructure.db.repositories.areas import PostgresAreaRepository
from infrastructure.db.repositories.catalog import PostgresCatalogRepository
from infrastructure.db.repositories.places import PostgresPlacesRepository
from infrastructure.db.repositories.rent import PostgresRentProvider
from jobs.runtime import configure_logging, job_session
from ports.areas import AreaRepository
from ports.places import PlacesRepository
from ports.rent import RentProvider


@dataclass(frozen=True)
class AreaSummary:
    area: Area
    cell_count: int
    rent: RentEstimate | Unknown
    amenity_counts: Mapping[PlaceCategory, int] | Unknown
    job_access: JobAccess | Unknown


def summarise_city(
    areas: AreaRepository, rents: RentProvider, places: PlacesRepository, city_id: str
) -> list[AreaSummary]:
    """Depends only on the ports, so it runs against fakes as well as PostgreSQL."""
    cells = areas.cells_by_area(city_id)
    rent_by_area = rents.rents_by_area(city_id)
    job_access = places.job_access_by_area(city_id)
    # Without a places snapshot, "no cafes" would be a guess, so it is UNKNOWN.
    # With one, an area missing from the counts really has none.
    counts = (
        UNKNOWN
        if places.snapshot_date(city_id) is UNKNOWN
        else places.counts_by_area(city_id, AMENITY_CATEGORIES)
    )
    return [
        AreaSummary(
            area=area,
            cell_count=len(cells.get(area.id, ())),
            rent=rent_by_area.get(area.id, UNKNOWN),
            amenity_counts=UNKNOWN if counts is UNKNOWN else counts.get(area.id, {}),
            job_access=job_access.get(area.id, UNKNOWN),
        )
        for area in areas.list_by_city(city_id)
    ]


def format_rent(rent: RentEstimate | Unknown) -> str:
    if rent is UNKNOWN:
        return "UNKNOWN"
    label = "sample" if rent.is_sample else rent.source
    return f"{rent.monthly_eur:.0f} EUR ({label}, {rent.as_of})"


def format_amenities(counts: Mapping[PlaceCategory, int] | Unknown) -> str:
    if counts is UNKNOWN:
        return "UNKNOWN"
    return ", ".join(
        f"{counts.get(category, 0)} {category.value}" for category in sorted(AMENITY_CATEGORIES)
    )


def format_job_access(access: JobAccess | Unknown) -> str:
    if access is UNKNOWN:
        return "UNKNOWN"
    return f"{access.score:.2f} ({access.places_nearby} nearby)"


def main() -> None:
    registry = discover_cities()
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--city", choices=[city.id for city in registry.all()])
    parser.add_argument("--list", action="store_true", help="print one line per area")
    arguments = parser.parse_args()
    cities = [registry.get(arguments.city)] if arguments.city else list(registry.all())

    configure_logging()
    with job_session() as session:
        areas, rents = PostgresAreaRepository(session), PostgresRentProvider(session)
        places, catalog = PostgresPlacesRepository(session), PostgresCatalogRepository(session)
        for city in cities:
            summaries = summarise_city(areas, rents, places, city.id)
            known = [s for s in summaries if s.rent is not UNKNOWN]
            sample = [s for s in known if s.rent is not UNKNOWN and s.rent.is_sample]
            with_amenities = [s for s in summaries if s.amenity_counts is not UNKNOWN]
            with_jobs = [s for s in summaries if s.job_access is not UNKNOWN]
            hotspots = catalog.list_destinations(city.id, DestinationKind.JOB_HOTSPOT)
            employers = catalog.list_destinations(city.id, DestinationKind.EMPLOYER)
            print(
                f"{city.name}: {len(summaries)} areas, "
                f"{sum(s.cell_count for s in summaries)} cells, "
                f"{sum(s.cell_count == 0 for s in summaries)} areas without cells\n"
                f"  rent: known for {len(known)} ({len(sample)} sample), "
                f"UNKNOWN for {len(summaries) - len(known)}\n"
                f"  places: snapshot of {places.snapshot_date(city.id)}, "
                f"amenity counts for {len(with_amenities)} areas, "
                f"job access for {len(with_jobs)} areas\n"
                f"  destinations: {len(hotspots)} job hotspots, {len(employers)} employers"
            )
            if arguments.list:
                for summary in summaries:
                    print(
                        f"  {summary.area.name:<32} {summary.cell_count:>3} cells | "
                        f"{format_rent(summary.rent)} | "
                        f"{format_amenities(summary.amenity_counts)} | "
                        f"jobs {format_job_access(summary.job_access)}"
                    )
                for hotspot in hotspots:
                    print(f"  {hotspot.name}")


if __name__ == "__main__":
    main()

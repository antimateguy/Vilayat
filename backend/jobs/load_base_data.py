"""Load the base data of one or all cities, in dependency order.

Steps per city: city, universities and campuses; neighbourhood boundaries; H3
cells; OpenStreetMap places; job access per cell; job hotspots. Then the rent
file and the employer file. Every step can be run again without creating
duplicates, and the whole run is one transaction.

Run for every city:  uv run python -m jobs.load_base_data
Run for one city:    uv run python -m jobs.load_base_data --city berlin
"""

import argparse
import logging
from pathlib import Path

from sqlalchemy.orm import Session

from cities.base import CityConfig
from cities.registry import discover_cities
from jobs.build_cells import build_cells
from jobs.build_hotspots import build_hotspots
from jobs.compute_job_access import compute_job_access
from jobs.fetch_osm_places import OSM_DIR
from jobs.ingest_places import ingest_places, read_snapshot, snapshot_exists
from jobs.load_boundaries import load_boundaries, read_boundaries
from jobs.load_employers import EMPLOYER_FILE, load_employers, read_employers
from jobs.load_rents import load_rents, read_rents
from jobs.make_sample_rents import SAMPLE_FILE
from jobs.runtime import configure_logging, job_session
from jobs.seed_catalog import seed_catalog

logger = logging.getLogger(__name__)


def load_city(session: Session, city: CityConfig, osm_directory: Path = OSM_DIR) -> None:
    seed_catalog(session, city)
    load_boundaries(session, city, read_boundaries(city))
    build_cells(session, city.id)
    if snapshot_exists(city.id, osm_directory):
        ingest_places(session, city.id, read_snapshot(city.id, osm_directory))
    else:
        logger.warning(
            "%s: no OpenStreetMap snapshot found; run jobs.fetch_osm_places first", city.id
        )
    compute_job_access(session, city.id)
    build_hotspots(session, city.id)


def main() -> None:
    registry = discover_cities()
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--city",
        action="append",
        choices=[city.id for city in registry.all()],
        help="city to load; repeat for several (default: all)",
    )
    parser.add_argument(
        "--rents",
        type=Path,
        default=SAMPLE_FILE,
        help="rent CSV to load (default: the labelled sample file)",
    )
    parser.add_argument(
        "--employers",
        type=Path,
        default=EMPLOYER_FILE,
        help="employer CSV to load (default: the labelled sample file)",
    )
    arguments = parser.parse_args()

    configure_logging()
    cities = [registry.get(city_id) for city_id in arguments.city] if arguments.city else None
    selected = cities or list(registry.all())
    selected_ids = {city.id for city in selected}
    rents = [record for record in read_rents(arguments.rents) if record.city_id in selected_ids]
    employers = [
        record for record in read_employers(arguments.employers) if record.city_id in selected_ids
    ]

    with job_session() as session:
        for city in selected:
            load_city(session, city)
        load_rents(session, rents)
        load_employers(session, employers)


if __name__ == "__main__":
    main()

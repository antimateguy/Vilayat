"""Write a city, its universities and their campuses from the city configuration.

Run for one city:  uv run python -m jobs.load_base_data --city berlin
"""

import logging

from geoalchemy2.shape import from_shape
from shapely.geometry import Point
from sqlalchemy import select
from sqlalchemy.orm import Session

from cities.base import CampusConfig, CityConfig, UniversityConfig
from domain.destination import DestinationKind
from infrastructure.db.models import (
    SRID_WGS84,
    CampusRow,
    CityRow,
    DestinationRow,
    UniversityRow,
)

logger = logging.getLogger(__name__)


def seed_catalog(session: Session, city: CityConfig) -> None:
    """Insert or update by natural key (names), so the job is safe to run again."""
    city_row = session.get(CityRow, city.id)
    if city_row is None:
        session.add(CityRow(id=city.id, name=city.name))
    else:
        city_row.name = city.name
    session.flush()

    campuses = 0
    for university in city.universities:
        university_row = _upsert_university(session, city, university)
        for campus in university.campuses:
            _upsert_campus(session, city, university, university_row, campus)
            campuses += 1
    session.flush()
    logger.info(
        "%s: seeded %d universities, %d campuses", city.id, len(city.universities), campuses
    )


def _upsert_university(
    session: Session, city: CityConfig, university: UniversityConfig
) -> UniversityRow:
    row = session.scalar(
        select(UniversityRow).where(
            UniversityRow.city_id == city.id, UniversityRow.name == university.name
        )
    )
    if row is None:
        row = UniversityRow(city_id=city.id, name=university.name)
        session.add(row)
    row.short_name = university.short_name
    session.flush()
    return row


def _upsert_campus(
    session: Session,
    city: CityConfig,
    university: UniversityConfig,
    university_row: UniversityRow,
    campus: CampusConfig,
) -> None:
    """A campus is also a travel destination, so it gets a destination row that
    holds its location."""
    campus_row = session.scalar(
        select(CampusRow).where(
            CampusRow.university_id == university_row.id, CampusRow.name == campus.name
        )
    )
    destination = (
        DestinationRow(city_id=city.id, kind=DestinationKind.CAMPUS)
        if campus_row is None
        else session.get_one(DestinationRow, campus_row.destination_id)
    )
    destination.name = f"{university.short_name}, {campus.name}"
    destination.geom = from_shape(Point(campus.location.lon, campus.location.lat), srid=SRID_WGS84)
    destination.source = city.campus_source
    destination.source_url = city.campus_source_url
    destination.as_of = city.campus_as_of
    destination.is_sample = False
    session.add(destination)
    session.flush()

    if campus_row is None:
        session.add(
            CampusRow(
                university_id=university_row.id,
                name=campus.name,
                destination_id=destination.id,
            )
        )

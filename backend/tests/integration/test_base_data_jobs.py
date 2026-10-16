"""The base-data jobs against the real database, using the real data files.

Loading both cities takes a few seconds, so it is done once for the module, in a
transaction that is rolled back at the end.
"""

from collections.abc import Iterator

import pytest
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from cities.registry import discover_cities
from domain.destination import DestinationKind
from domain.place import AMENITY_CATEGORIES
from domain.unknown import UNKNOWN
from infrastructure.db.models import (
    AreaRentRow,
    CampusRow,
    CellRow,
    DestinationRow,
    NeighbourhoodRow,
    PlaceRow,
    UniversityRow,
)
from infrastructure.db.repositories.areas import PostgresAreaRepository
from infrastructure.db.repositories.catalog import PostgresCatalogRepository
from infrastructure.db.repositories.places import PostgresPlacesRepository
from infrastructure.db.repositories.rent import PostgresRentProvider
from jobs.check_city_data import summarise_city
from jobs.load_base_data import load_city
from jobs.load_employers import EMPLOYER_FILE, load_employers, read_employers
from jobs.load_rents import RentRecord, load_rents, read_rents
from jobs.make_sample_rents import SAMPLE_FILE

pytestmark = pytest.mark.integration

REGISTRY = discover_cities()
TABLES = (
    NeighbourhoodRow,
    CellRow,
    UniversityRow,
    CampusRow,
    DestinationRow,
    AreaRentRow,
    PlaceRow,
)


def load_everything(session: Session) -> None:
    for city in REGISTRY.all():
        load_city(session, city)
    load_rents(session, read_rents(SAMPLE_FILE))
    load_employers(session, read_employers(EMPLOYER_FILE))
    session.flush()


def row_counts(session: Session) -> list[int | None]:
    return [session.scalar(select(func.count()).select_from(table)) for table in TABLES]


@pytest.fixture(scope="module")
def loaded(engine: Engine) -> Iterator[Session]:
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    load_everything(session)
    yield session
    session.close()
    transaction.rollback()
    connection.close()


@pytest.mark.parametrize(
    ("city_id", "areas", "min_cells", "max_cells"),
    # Berlin is about 891 km2 and Munich 311 km2; a cell is about 0.65 to 0.75 km2 here.
    [("berlin", 97, 1150, 1400), ("munich", 25, 400, 500)],
)
def test_every_area_has_cells_rent_amenities_and_job_access(
    loaded: Session, city_id: str, areas: int, min_cells: int, max_cells: int
) -> None:
    """The "done when" of Modules 2 and 3 for the real cities."""
    summaries = summarise_city(
        PostgresAreaRepository(loaded),
        PostgresRentProvider(loaded),
        PostgresPlacesRepository(loaded),
        city_id,
    )

    assert len(summaries) == areas
    assert all(summary.cell_count >= 1 for summary in summaries)
    assert min_cells <= sum(summary.cell_count for summary in summaries) <= max_cells
    # The sample file covers every area, and every figure is labelled as a sample.
    assert all(s.rent is not UNKNOWN and s.rent.is_sample for s in summaries)
    assert all(s.amenity_counts is not UNKNOWN for s in summaries)
    assert all(s.job_access is not UNKNOWN for s in summaries)


@pytest.mark.parametrize(("city_id", "min_places"), [("berlin", 15000), ("munich", 6000)])
def test_places_are_loaded_with_their_snapshot_date(
    loaded: Session, city_id: str, min_places: int
) -> None:
    places = PostgresPlacesRepository(loaded)

    counts = places.counts_by_area(city_id, AMENITY_CATEGORIES)
    total = loaded.scalar(
        select(func.count()).select_from(PlaceRow).where(PlaceRow.city_id == city_id)
    )

    assert places.snapshot_date(city_id) is not UNKNOWN
    assert total is not None and total >= min_places
    # Every amenity category occurs somewhere in the city.
    assert {category for area in counts.values() for category in area} == AMENITY_CATEGORIES


@pytest.mark.parametrize("city_id", ["berlin", "munich"])
def test_job_access_ranks_the_centre_above_the_edge(loaded: Session, city_id: str) -> None:
    by_cell = PostgresPlacesRepository(loaded).job_access_by_cell(city_id)
    scores = sorted(access.score for access in by_cell.values())

    assert len(by_cell) == loaded.scalar(
        select(func.count()).select_from(CellRow).where(CellRow.city_id == city_id)
    )
    assert scores[0] == 0
    assert scores[-1] == 1
    busiest = max(by_cell.values(), key=lambda access: access.places_nearby)
    assert busiest.places_nearby > 1000


@pytest.mark.parametrize(("city_id", "min_hotspots"), [("berlin", 6), ("munich", 4)])
def test_hotspots_and_employers_exist_as_destinations(
    loaded: Session, city_id: str, min_hotspots: int
) -> None:
    catalog = PostgresCatalogRepository(loaded)
    city = REGISTRY.get(city_id)

    hotspots = catalog.list_destinations(city_id, DestinationKind.JOB_HOTSPOT)
    employers = catalog.list_destinations(city_id, DestinationKind.EMPLOYER)

    assert min_hotspots <= len(hotspots) <= 10
    assert all(hotspot.name.startswith("Job hotspot: ") for hotspot in hotspots)
    assert all(city.bounds.contains(hotspot.location) for hotspot in hotspots)
    assert len(employers) == 10


def test_an_area_missing_from_the_rent_file_is_unknown(loaded: Session) -> None:
    removed = loaded.scalar(
        select(AreaRentRow.neighbourhood_id)
        .join(NeighbourhoodRow, NeighbourhoodRow.id == AreaRentRow.neighbourhood_id)
        .where(NeighbourhoodRow.city_id == "munich")
        .limit(1)
    )
    with loaded.begin_nested() as savepoint:
        loaded.query(AreaRentRow).filter(AreaRentRow.neighbourhood_id == removed).delete()

        rents = PostgresRentProvider(loaded).rents_by_area("munich")

        assert removed is not None and rents[removed] is UNKNOWN
        assert list(rents.values()).count(UNKNOWN) == 1
        assert len(rents) == 25
        savepoint.rollback()


def test_campuses_are_seeded_as_destinations(loaded: Session) -> None:
    catalog = PostgresCatalogRepository(loaded)

    assert [city.id for city in catalog.list_cities()] == ["berlin", "munich"]
    assert [u.short_name for u in catalog.list_universities("munich")] == ["HM", "LMU", "TUM"]
    assert len(catalog.list_universities("berlin")) == 4
    assert len(catalog.list_destinations("berlin", DestinationKind.CAMPUS)) == 7
    munich_campuses = catalog.list_destinations("munich", DestinationKind.CAMPUS)
    assert len(munich_campuses) == 6
    garching = next(d for d in munich_campuses if d.name == "TUM, Campus Garching")
    assert garching.location.lat == pytest.approx(48.26585)
    assert garching.location.lon == pytest.approx(11.67061)


def test_each_cell_centre_lies_inside_its_own_area_or_was_given_to_a_tiny_one(
    loaded: Session,
) -> None:
    outside = loaded.scalar(
        select(func.count())
        .select_from(CellRow)
        .join(NeighbourhoodRow, NeighbourhoodRow.id == CellRow.neighbourhood_id)
        .where(~func.ST_Contains(NeighbourhoodRow.geom, CellRow.centroid))
    )

    # Only an area too small to contain a cell centre takes a cell it does not contain.
    assert outside is not None and outside <= 2


def test_running_the_jobs_twice_keeps_every_row_and_destination_id(loaded: Session) -> None:
    """Travel times are stored against destination ids, so a reload must not change them."""
    counts_before = row_counts(loaded)
    ids_before = set(loaded.scalars(select(DestinationRow.id)))

    load_everything(loaded)

    assert row_counts(loaded) == counts_before
    assert set(loaded.scalars(select(DestinationRow.id))) == ids_before


def test_rents_for_an_area_that_does_not_exist_are_rejected(loaded: Session) -> None:
    template = read_rents(SAMPLE_FILE)[0]
    bad = RentRecord(
        city_id="berlin",
        area_external_id="no-such-area",
        monthly_rent_eur=template.monthly_rent_eur,
        basis=template.basis,
        source=template.source,
        source_url=None,
        as_of=template.as_of,
        is_sample=True,
    )

    with pytest.raises(ValueError, match="berlin/no-such-area"):
        load_rents(loaded, [bad])

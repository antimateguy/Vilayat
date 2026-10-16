"""The PostgreSQL repositories against the real database, on the Testville fixture."""

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from domain.area import RentEstimate
from domain.destination import DestinationKind
from domain.document import EMBEDDING_DIMENSIONS, DocChunk, EmbeddedChunk
from domain.place import JobAccess, PlaceCategory
from domain.travel import TimeWindow
from domain.unknown import UNKNOWN
from infrastructure.db.models import DocChunkRow
from infrastructure.db.repositories.areas import PostgresAreaRepository
from infrastructure.db.repositories.catalog import PostgresCatalogRepository
from infrastructure.db.repositories.commute import PrecomputedCommuteProvider
from infrastructure.db.repositories.places import PostgresPlacesRepository
from infrastructure.db.repositories.rent import PostgresRentProvider
from infrastructure.db.repositories.vector_store import PgVectorStore
from tests.integration.world import (
    A1,
    A2,
    A3,
    B1,
    B2,
    CAMPUS_LAT,
    CAMPUS_LON,
    World,
    build_world,
)

pytestmark = pytest.mark.integration


@pytest.fixture
def world(session: Session) -> World:
    return build_world(session)


# --- Catalog ---------------------------------------------------------------


def test_catalog_lists_cities_and_universities(session: Session, world: World) -> None:
    catalog = PostgresCatalogRepository(session)

    assert [city.id for city in catalog.list_cities()] == ["elsewhere", "testville"]
    (university,) = catalog.list_universities(world.city_id)
    assert (university.id, university.short_name) == (world.university_id, "TU")
    assert catalog.list_universities("elsewhere") == []


def test_campus_takes_its_location_from_its_destination(session: Session, world: World) -> None:
    catalog = PostgresCatalogRepository(session)

    campus = catalog.get_campus(world.campus_id)

    assert campus is not None
    assert campus.destination_id == world.campus_destination_id
    assert campus.location.lat == pytest.approx(CAMPUS_LAT)
    assert campus.location.lon == pytest.approx(CAMPUS_LON)
    assert catalog.list_campuses(world.university_id) == [campus]


def test_destinations_are_listed_by_kind(session: Session, world: World) -> None:
    catalog = PostgresCatalogRepository(session)

    employers = catalog.list_destinations(world.city_id, DestinationKind.EMPLOYER)

    assert [(d.id, d.name, d.kind) for d in employers] == [
        (world.employer_destination_id, "Example Works", DestinationKind.EMPLOYER)
    ]
    assert catalog.list_destinations(world.city_id, DestinationKind.JOB_HOTSPOT) == []
    assert catalog.get_destination(world.employer_destination_id) == employers[0]


def test_catalog_returns_none_for_ids_that_do_not_exist(session: Session, world: World) -> None:
    catalog = PostgresCatalogRepository(session)

    assert catalog.get_campus(-1) is None
    assert catalog.get_destination(-1) is None


# --- Areas -----------------------------------------------------------------


def test_areas_of_one_city_in_name_order(session: Session, world: World) -> None:
    areas = PostgresAreaRepository(session)

    assert [area.name for area in areas.list_by_city(world.city_id)] == [
        "Altstadt",
        "Nordend",
        "Ostpark",
    ]
    assert areas.get(world.nordend) == areas.list_by_city(world.city_id)[1]
    assert areas.get(-1) is None


def test_cells_by_area_keeps_an_area_that_has_no_cells(session: Session, world: World) -> None:
    cells = PostgresAreaRepository(session).cells_by_area(world.city_id)

    assert cells == {world.altstadt: [A1, A2, A3], world.nordend: [B1, B2], world.ostpark: []}


# --- Rent ------------------------------------------------------------------


def test_latest_real_rent_wins_over_older_and_sample_figures(
    session: Session, world: World
) -> None:
    rents = PostgresRentProvider(session).rents_by_area(world.city_id)

    assert rents[world.altstadt] == RentEstimate(
        monthly_eur=Decimal("720.00"),
        basis="median asking rent, 1-room flat",
        source="official report",
        source_url=None,
        as_of=date(2025, 6, 1),
        is_sample=False,
    )


def test_sample_rent_is_used_and_labelled_when_it_is_all_there_is(
    session: Session, world: World
) -> None:
    rent = PostgresRentProvider(session).rents_by_area(world.city_id)[world.nordend]

    assert rent is not UNKNOWN
    assert (rent.monthly_eur, rent.is_sample) == (Decimal("500.00"), True)


def test_area_without_a_rent_figure_is_unknown(session: Session, world: World) -> None:
    rents = PostgresRentProvider(session).rents_by_area(world.city_id)

    assert rents[world.ostpark] is UNKNOWN
    assert set(rents) == {world.altstadt, world.nordend, world.ostpark}


# --- Commute ---------------------------------------------------------------


def test_minutes_by_cell_omits_cells_without_a_route(session: Session, world: World) -> None:
    commute = PrecomputedCommuteProvider(session)

    morning = commute.minutes_by_cell(world.campus_destination_id, TimeWindow.WEEKDAY_MORNING)

    assert morning == {A1: 10, A2: 20, A3: 40, B1: 30}
    assert B2 not in morning


def test_minutes_by_area_is_the_median_of_routed_cells(session: Session, world: World) -> None:
    commute = PrecomputedCommuteProvider(session)

    morning = commute.minutes_by_area(world.campus_destination_id, TimeWindow.WEEKDAY_MORNING)

    assert morning == {world.altstadt: 20, world.nordend: 30, world.ostpark: UNKNOWN}


def test_minutes_by_area_rounds_half_up_and_reports_unknown(session: Session, world: World) -> None:
    commute = PrecomputedCommuteProvider(session)

    evening = commute.minutes_by_area(world.campus_destination_id, TimeWindow.WEEKDAY_EVENING)

    # Altstadt: median of 10 and 21 is 15.5. Nordend has no evening times at all.
    assert evening == {world.altstadt: 16, world.nordend: UNKNOWN, world.ostpark: UNKNOWN}


def test_destination_without_travel_times_gives_unknown_everywhere(
    session: Session, world: World
) -> None:
    commute = PrecomputedCommuteProvider(session)

    by_area = commute.minutes_by_area(world.employer_destination_id, TimeWindow.WEEKDAY_MORNING)

    assert set(by_area.values()) == {UNKNOWN}
    assert commute.minutes_by_cell(world.employer_destination_id, TimeWindow.WEEKDAY_MORNING) == {}


def test_minutes_between_two_destinations(session: Session, world: World) -> None:
    commute = PrecomputedCommuteProvider(session)
    campus, employer = world.campus_destination_id, world.employer_destination_id

    assert commute.minutes_between(campus, employer, TimeWindow.WEEKDAY_EVENING) == 15
    # Nothing is stored for the morning or for the way back, and nothing is assumed.
    assert commute.minutes_between(campus, employer, TimeWindow.WEEKDAY_MORNING) is UNKNOWN
    assert commute.minutes_between(employer, campus, TimeWindow.WEEKDAY_EVENING) is UNKNOWN


# --- Places ----------------------------------------------------------------


def test_place_counts_by_area(session: Session, world: World) -> None:
    places = PostgresPlacesRepository(session)

    counts = places.counts_by_area(
        world.city_id, {PlaceCategory.CAFE, PlaceCategory.SUPERMARKET, PlaceCategory.LIBRARY}
    )

    # The bar is not asked for; the library lies outside every area; Ostpark has no places.
    assert counts == {
        world.altstadt: {PlaceCategory.CAFE: 2, PlaceCategory.SUPERMARKET: 1},
        world.nordend: {PlaceCategory.CAFE: 1},
    }


def test_place_counts_by_cell(session: Session, world: World) -> None:
    places = PostgresPlacesRepository(session)

    counts = places.counts_by_cell(world.city_id, {PlaceCategory.CAFE, PlaceCategory.BAR})

    assert counts == {
        A1: {PlaceCategory.CAFE: 2},
        B1: {PlaceCategory.CAFE: 1, PlaceCategory.BAR: 1},
    }
    assert places.counts_by_cell(world.city_id, set()) == {}


def test_snapshot_date_tells_no_data_apart_from_no_places(session: Session, world: World) -> None:
    places = PostgresPlacesRepository(session)

    assert places.snapshot_date(world.city_id) == date(2026, 1, 1)
    assert places.snapshot_date("city-without-places") is UNKNOWN


def test_job_access_by_cell_omits_cells_that_are_not_scored(session: Session, world: World) -> None:
    access = PostgresPlacesRepository(session).job_access_by_cell(world.city_id)

    assert access == {
        A1: JobAccess(places_nearby=10, score=0.2),
        A2: JobAccess(places_nearby=20, score=0.4),
        A3: JobAccess(places_nearby=60, score=1.0),
        B1: JobAccess(places_nearby=5, score=0.1),
    }


def test_job_access_by_area_is_the_median_of_scored_cells(session: Session, world: World) -> None:
    access = PostgresPlacesRepository(session).job_access_by_area(world.city_id)

    assert access == {
        world.altstadt: JobAccess(places_nearby=20, score=0.4),
        world.nordend: JobAccess(places_nearby=5, score=0.1),
        world.ostpark: UNKNOWN,
    }


# --- Vector store ----------------------------------------------------------


def axis(index: int, also: int | None = None) -> tuple[float, ...]:
    """A vector pointing along one axis, or halfway between two."""
    vector = [0.0] * EMBEDDING_DIMENSIONS
    vector[index] = 1.0
    if also is not None:
        vector[also] = 1.0
    return tuple(vector)


MODEL = "test-model"


def embedded(
    key: str,
    vector: tuple[float, ...],
    city_id: str | None = None,
    *,
    index: int = 0,
    model: str = MODEL,
) -> EmbeddedChunk:
    chunk = DocChunk(
        document_key=key,
        chunk_index=index,
        title=f"Title of {key}",
        source_url=f"https://example.org/{key}",
        content=f"Content of {key}",
        retrieved_on=date(2026, 1, 1),
        city_id=city_id,
        is_sample=True,
    )
    return EmbeddedChunk(chunk=chunk, embedding=vector, model=model)


def test_search_returns_the_most_similar_chunks_first(session: Session, world: World) -> None:
    store = PgVectorStore(session)
    store.add([embedded("visa", axis(0)), embedded("both", axis(0, 1)), embedded("rent", axis(1))])

    results = store.search(axis(0), limit=3, model=MODEL)

    assert [result.chunk.document_key for result in results] == ["visa", "both", "rent"]
    assert [result.similarity for result in results] == pytest.approx([1.0, 0.7071, 0.0], abs=1e-3)
    assert results[0].chunk == embedded("visa", axis(0)).chunk
    assert len(store.search(axis(0), limit=1, model=MODEL)) == 1


def test_search_for_a_city_skips_chunks_about_other_cities(session: Session, world: World) -> None:
    store = PgVectorStore(session)
    store.add(
        [
            embedded("general", axis(0)),
            embedded("local", axis(0), city_id=world.city_id),
            embedded("foreign", axis(0), city_id="elsewhere"),
        ]
    )

    results = store.search(axis(0), limit=10, model=MODEL, city_id=world.city_id)

    assert {result.chunk.document_key for result in results} == {"general", "local"}


def test_adding_a_chunk_again_replaces_it(session: Session, world: World) -> None:
    store = PgVectorStore(session)
    store.add([embedded("visa", axis(0))])
    store.add([embedded("visa", axis(1))])
    store.add([])

    assert session.scalar(select(func.count()).select_from(DocChunkRow)) == 1
    (result,) = store.search(axis(1), limit=5, model=MODEL)
    assert result.similarity == pytest.approx(1.0)


def test_search_ignores_chunks_embedded_with_another_model(session: Session, world: World) -> None:
    store = PgVectorStore(session)
    store.add([embedded("old", axis(0), model="older-model"), embedded("new", axis(1))])

    results = store.search(axis(0), limit=5, model=MODEL)

    assert [result.chunk.document_key for result in results] == ["new"]


def test_deleting_a_document_removes_all_its_chunks(session: Session, world: World) -> None:
    store = PgVectorStore(session)
    store.add(
        [
            embedded("visa", axis(0)),
            embedded("visa", axis(1), index=1),
            embedded("rent", axis(2)),
        ]
    )

    store.delete_document("visa")
    store.delete_document("never stored")

    assert store.document_keys() == {"rent"}

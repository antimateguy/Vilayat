"""The decision engine wired to the PostgreSQL repositories.

The unit tests run the same services on in-memory repositories. Getting the same
kind of answer here shows the two sets of implementations are interchangeable
behind the ports.
"""

from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from domain.constraints import Constraints
from domain.unknown import UNKNOWN
from infrastructure.db.repositories.areas import PostgresAreaRepository
from infrastructure.db.repositories.catalog import PostgresCatalogRepository
from infrastructure.db.repositories.commute import PrecomputedCommuteProvider
from infrastructure.db.repositories.places import PostgresPlacesRepository
from infrastructure.db.repositories.rent import PostgresRentProvider
from services.comparison import ComparisonService
from services.facts import AreaFactsCollector
from services.ranking import RankingService
from services.search import SearchRequest, SearchService
from tests.integration.world import World, build_world

pytestmark = pytest.mark.integration


@pytest.fixture
def world(session: Session) -> World:
    return build_world(session)


def wire(session: Session) -> tuple[SearchService, ComparisonService]:
    catalog = PostgresCatalogRepository(session)
    areas = PostgresAreaRepository(session)
    commute = PrecomputedCommuteProvider(session)
    collector = AreaFactsCollector(
        areas, PostgresRentProvider(session), commute, PostgresPlacesRepository(session)
    )
    return (
        SearchService(catalog, collector, commute, RankingService()),
        ComparisonService(catalog, areas, collector),
    )


def test_search_ranks_matches_and_sets_aside_what_cannot_be_checked(
    session: Session, world: World
) -> None:
    search, _ = wire(session)
    constraints = Constraints(world.campus_id, max_commute_minutes=40, max_rent_eur=Decimal("800"))

    result = search.search(SearchRequest(constraints))

    # Altstadt: 720 EUR, 20 min. Nordend: 500 EUR (sample), 30 min. The cheaper
    # rent outweighs the longer commute at the default weights.
    assert [item.facts.area.name for item in result.ranked] == ["Nordend", "Altstadt"]
    assert result.excluded == ()
    (ostpark,) = result.unchecked
    assert ostpark.facts.area.id == world.ostpark
    assert set(ostpark.missing) == {
        "No travel time to the campus is stored for this area.",
        "No rent figure is known for this area.",
    }
    assert "placeholder figure" in " ".join(result.ranked[0].reasons)


def test_a_lower_rent_ceiling_excludes_the_dearer_area(session: Session, world: World) -> None:
    search, _ = wire(session)
    constraints = Constraints(world.campus_id, max_commute_minutes=40, max_rent_eur=Decimal("600"))

    result = search.search(SearchRequest(constraints))

    assert [item.facts.area.name for item in result.ranked] == ["Nordend"]
    assert [item.violations for item in result.excluded] == [
        ("Rent of 720 EUR is over your 600 EUR ceiling.",)
    ]


def test_a_pinned_employer_uses_the_stored_campus_to_job_time(
    session: Session, world: World
) -> None:
    search, _ = wire(session)
    constraints = Constraints(world.campus_id, max_commute_minutes=40, max_rent_eur=Decimal("800"))

    result = search.search(
        SearchRequest(constraints, employer_destination_id=world.employer_destination_id)
    )

    full_day = result.ranked[0].full_day
    assert full_day is not None
    assert full_day.campus_to_job == 15
    # No travel times are stored from the employer to the cells in this fixture.
    assert full_day.job_to_home is UNKNOWN
    assert full_day.total_minutes is UNKNOWN


def test_comparison_counts_the_same_areas_as_the_search(session: Session, world: World) -> None:
    _, comparison = wire(session)

    result = comparison.compare(world.city_id, Decimal("800"), 40)

    assert result.total_areas == 3
    (university,) = result.universities
    (campus,) = university.campuses
    assert campus.feasible_area_ids == {world.altstadt, world.nordend}
    assert (campus.excluded, campus.unchecked) == (0, 1)

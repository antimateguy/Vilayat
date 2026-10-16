"""A small made-up city for the decision-engine tests, held entirely in memory.

Testville, searched from campus 1 with a 700 EUR ceiling and a 40 minute limit:

| Area         | Rent        | Commute | Outcome                              |
| ------------ | ----------- | ------- | ------------------------------------ |
| Altstadt     | 680         | 10      | match: close, lively, expensive      |
| Nordend      | 600 sample  | 25      | match: in between                    |
| Ostpark      | 450         | 38      | match: cheap, far, quiet             |
| Fernweh      | 400         | 70      | excluded: commute over the limit     |
| Teuerberg    | 900         | unknown | excluded: rent over the ceiling      |
| Westend      | unknown     | 20      | cannot be checked: no rent figure    |
| Niemandsland | 500         | unknown | cannot be checked: no travel time    |
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

import h3

from domain.area import Area, RentEstimate
from domain.city import Campus, City, University
from domain.destination import Destination, DestinationKind
from domain.geo import Coordinate
from domain.place import JobAccess, PlaceCategory
from domain.travel import TimeWindow
from infrastructure.fakes.repositories import (
    InMemoryAreas,
    InMemoryCatalog,
    InMemoryCommute,
    InMemoryPlaces,
    InMemoryRents,
)
from services.comparison import ComparisonService
from services.facts import AreaFactsCollector
from services.ranking import RankingService
from services.search import SearchService

CITY = "testville"
ALTSTADT, NORDEND, OSTPARK, FERNWEH, TEUERBERG, WESTEND, NIEMANDSLAND = range(1, 8)
NAMES = {
    ALTSTADT: "Altstadt",
    NORDEND: "Nordend",
    OSTPARK: "Ostpark",
    FERNWEH: "Fernweh",
    TEUERBERG: "Teuerberg",
    WESTEND: "Westend",
    NIEMANDSLAND: "Niemandsland",
}

MAIN_CAMPUS, NORTH_CAMPUS, EAST_CAMPUS = 1, 2, 3
MAIN_CAMPUS_DESTINATION, NORTH_CAMPUS_DESTINATION, EAST_CAMPUS_DESTINATION = 10, 11, 12
EMPLOYER, EMPLOYER_ELSEWHERE, HOTSPOT = 20, 21, 30

MORNING, EVENING = TimeWindow.WEEKDAY_MORNING, TimeWindow.WEEKDAY_EVENING
HERE = Coordinate(48.1, 11.5)

# Real hexagon cells around central Munich, dealt out to the areas.
_CELLS = sorted(h3.grid_disk(h3.latlng_to_cell(48.137, 11.575, 8), 4))
CELLS = {
    ALTSTADT: _CELLS[0:4],
    NORDEND: _CELLS[4:12],
    OSTPARK: _CELLS[12:22],
    FERNWEH: _CELLS[22:27],
    TEUERBERG: _CELLS[27:32],
    WESTEND: _CELLS[32:37],
    NIEMANDSLAND: _CELLS[37:42],
}
CELL_COUNT = 42


def rent(eur: str, *, is_sample: bool = False) -> RentEstimate:
    return RentEstimate(
        monthly_eur=Decimal(eur),
        basis="median asking rent, 1-room flat",
        source="sample fixture" if is_sample else "Housing report",
        source_url=None,
        as_of=date(2026, 1, 1),
        is_sample=is_sample,
    )


@dataclass(frozen=True)
class Engine:
    search: SearchService
    comparison: ComparisonService
    collector: AreaFactsCollector
    catalog: InMemoryCatalog
    areas: InMemoryAreas
    rents: InMemoryRents
    commute: InMemoryCommute
    places: InMemoryPlaces


def build_engine(*, with_places: bool = True) -> Engine:
    """Wire the real services to in-memory repositories: the same wiring as in
    production, with every data source replaced."""
    areas = InMemoryAreas(
        [Area(id=area_id, city_id=CITY, name=name) for area_id, name in NAMES.items()]
        + [Area(id=99, city_id="elsewhere", name="Faraway")],
        cells=CELLS,
    )
    rents = InMemoryRents(
        areas,
        {
            ALTSTADT: rent("680"),
            NORDEND: rent("600", is_sample=True),
            OSTPARK: rent("450"),
            FERNWEH: rent("400"),
            TEUERBERG: rent("900"),
            NIEMANDSLAND: rent("500"),
        },
    )
    commute = InMemoryCommute(
        area_ids=list(NAMES),
        by_area={
            (MAIN_CAMPUS_DESTINATION, MORNING): {
                ALTSTADT: 10,
                NORDEND: 25,
                OSTPARK: 38,
                FERNWEH: 70,
                WESTEND: 20,
            },
            (MAIN_CAMPUS_DESTINATION, EVENING): {ALTSTADT: 12, NORDEND: 27, OSTPARK: 40},
            (NORTH_CAMPUS_DESTINATION, MORNING): {ALTSTADT: 30, NORDEND: 15, OSTPARK: 60},
            (EAST_CAMPUS_DESTINATION, MORNING): {OSTPARK: 20},
            # Nobody has routed the employer to Ostpark, so that leg is unknown.
            (EMPLOYER, EVENING): {ALTSTADT: 18, NORDEND: 30},
        },
        between={(MAIN_CAMPUS_DESTINATION, EMPLOYER, EVENING): 15},
        by_cell={
            (MAIN_CAMPUS_DESTINATION, MORNING): {CELLS[ALTSTADT][0]: 8, CELLS[ALTSTADT][1]: 12}
        },
    )
    places = InMemoryPlaces(
        snapshot=date(2026, 10, 5) if with_places else None,
        area_ids=list(NAMES),
        counts={
            ALTSTADT: {
                PlaceCategory.CAFE: 20,
                PlaceCategory.SUPERMARKET: 6,
                PlaceCategory.LIBRARY: 1,
                PlaceCategory.GYM: 3,
            },
            NORDEND: {PlaceCategory.CAFE: 4, PlaceCategory.SUPERMARKET: 4},
            OSTPARK: {PlaceCategory.SUPERMARKET: 1},
        }
        if with_places
        else {},
        job_access={
            ALTSTADT: JobAccess(places_nearby=500, score=0.95),
            NORDEND: JobAccess(places_nearby=120, score=0.6),
            OSTPARK: JobAccess(places_nearby=20, score=0.2),
        }
        if with_places
        else {},
        cell_counts={
            CELLS[ALTSTADT][0]: {
                PlaceCategory.CAFE: 5,
                PlaceCategory.SUPERMARKET: 1,
                PlaceCategory.BAR: 9,
            }
        }
        if with_places
        else {},
        cell_job_access={
            CELLS[ALTSTADT][0]: JobAccess(places_nearby=500, score=0.95),
            CELLS[NORDEND][0]: JobAccess(places_nearby=120, score=0.6),
        }
        if with_places
        else {},
    )
    catalog = InMemoryCatalog(
        cities=[City(CITY, "Testville"), City("elsewhere", "Elsewhere")],
        universities=[
            University(id=1, city_id=CITY, name="First University", short_name="FU"),
            University(id=2, city_id=CITY, name="Second University", short_name="SU"),
        ],
        campuses=[
            Campus(MAIN_CAMPUS, 1, "Main Campus", HERE, MAIN_CAMPUS_DESTINATION),
            Campus(NORTH_CAMPUS, 2, "North Campus", HERE, NORTH_CAMPUS_DESTINATION),
            Campus(EAST_CAMPUS, 2, "East Campus", HERE, EAST_CAMPUS_DESTINATION),
        ],
        destinations=[
            Destination(MAIN_CAMPUS_DESTINATION, CITY, DestinationKind.CAMPUS, "Main Campus", HERE),
            Destination(NORTH_CAMPUS_DESTINATION, CITY, DestinationKind.CAMPUS, "North", HERE),
            Destination(EAST_CAMPUS_DESTINATION, CITY, DestinationKind.CAMPUS, "East", HERE),
            Destination(
                EMPLOYER,
                CITY,
                DestinationKind.EMPLOYER,
                "Example Works",
                HERE,
                source="sample list",
                as_of=date(2026, 10, 5),
                is_sample=True,
            ),
            Destination(
                EMPLOYER_ELSEWHERE, "elsewhere", DestinationKind.EMPLOYER, "Far Works", HERE
            ),
            Destination(HOTSPOT, CITY, DestinationKind.JOB_HOTSPOT, "Job hotspot: Altstadt", HERE),
        ],
    )
    collector = AreaFactsCollector(areas, rents, commute, places)
    return Engine(
        search=SearchService(catalog, collector, commute, RankingService()),
        comparison=ComparisonService(catalog, areas, collector),
        collector=collector,
        catalog=catalog,
        areas=areas,
        rents=rents,
        commute=commute,
        places=places,
    )

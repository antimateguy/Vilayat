"""A tiny, fully known city for the repository tests.

Testville has three areas:
- Altstadt: cells A1, A2, A3; a real and a sample rent figure.
- Nordend:  cells B1, B2 (B2 has no route to the campus and no job score); a
  sample rent only.
- Ostpark:  no cells, no rent, so every figure about it is UNKNOWN.
"""

from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal

from geoalchemy2 import WKTElement
from sqlalchemy.orm import Session

from domain.destination import DestinationKind
from domain.place import PlaceCategory
from domain.travel import TimeWindow
from infrastructure.db.models import (
    SRID_WGS84,
    AreaRentRow,
    CampusRow,
    CellRow,
    CityRow,
    DestinationRow,
    DestinationTravelTimeRow,
    NeighbourhoodRow,
    PlaceRow,
    TravelTimeRow,
    UniversityRow,
)

# Real H3 cells (resolution 8) in central Munich, in ascending id order, so the
# map endpoints can draw them.
A1, A2, A3 = "881f8d44a3fffff", "881f8d44a7fffff", "881f8d44b5fffff"
B1, B2 = "881f8d7a41fffff", "881f8d7a49fffff"
ELSEWHERE_CELL = "881fae36a1fffff"

CAMPUS_LAT, CAMPUS_LON = 48.15, 11.58


@dataclass(frozen=True)
class World:
    city_id: str
    altstadt: int
    nordend: int
    ostpark: int
    university_id: int
    campus_id: int
    campus_destination_id: int
    employer_destination_id: int


def point(lon: float, lat: float) -> WKTElement:
    return WKTElement(f"POINT({lon} {lat})", srid=SRID_WGS84)


def square(lon: float, lat: float, size: float = 0.01) -> WKTElement:
    east, north = lon + size, lat + size
    ring = f"{lon} {lat}, {east} {lat}, {east} {north}, {lon} {north}, {lon} {lat}"
    return WKTElement(f"MULTIPOLYGON((({ring})))", srid=SRID_WGS84)


def provenance(as_of: date = date(2026, 1, 1), *, is_sample: bool = False) -> dict[str, object]:
    return {"source": "test fixture", "source_url": None, "as_of": as_of, "is_sample": is_sample}


def build_world(session: Session) -> World:
    city, other_city = "testville", "elsewhere"
    session.add_all([CityRow(id=city, name="Testville"), CityRow(id=other_city, name="Elsewhere")])

    altstadt = NeighbourhoodRow(
        city_id=city, external_id="01", name="Altstadt", geom=square(11.57, 48.13), **provenance()
    )
    nordend = NeighbourhoodRow(
        city_id=city, external_id="02", name="Nordend", geom=square(11.58, 48.16), **provenance()
    )
    ostpark = NeighbourhoodRow(
        city_id=city, external_id="03", name="Ostpark", geom=square(11.62, 48.13), **provenance()
    )
    faraway = NeighbourhoodRow(
        city_id=other_city, external_id="01", name="Faraway", geom=square(9.0, 50.0), **provenance()
    )
    session.add_all([altstadt, nordend, ostpark, faraway])
    session.flush()

    def cell(
        h3_index: str, area: NeighbourhoodRow, job_access: tuple[int, float] | None = None
    ) -> CellRow:
        nearby, score = job_access or (None, None)
        return CellRow(
            h3_index=h3_index,
            city_id=area.city_id,
            neighbourhood_id=area.id,
            centroid=point(11.575, 48.135),
            job_places_nearby=nearby,
            job_access_score=score,
        )

    session.add_all(
        [
            # Altstadt medians: 20 places nearby, score 0.4.
            cell(A1, altstadt, (10, 0.2)),
            cell(A2, altstadt, (20, 0.4)),
            cell(A3, altstadt, (60, 1.0)),
            cell(B1, nordend, (5, 0.1)),
            cell(B2, nordend),
            cell(ELSEWHERE_CELL, faraway),
        ]
    )

    university = UniversityRow(city_id=city, name="Test University", short_name="TU")
    campus_destination = DestinationRow(
        city_id=city,
        kind=DestinationKind.CAMPUS,
        name="Main Campus",
        geom=point(CAMPUS_LON, CAMPUS_LAT),
        **provenance(),
    )
    employer = DestinationRow(
        city_id=city,
        kind=DestinationKind.EMPLOYER,
        name="Example Works",
        geom=point(11.60, 48.17),
        **provenance(is_sample=True),
    )
    session.add_all([university, campus_destination, employer])
    session.flush()
    campus = CampusRow(
        university_id=university.id, name="Main Campus", destination_id=campus_destination.id
    )
    session.add(campus)

    computed_at = datetime(2026, 1, 2, tzinfo=UTC)

    def travel(cell_id: str, window: TimeWindow, minutes: int) -> TravelTimeRow:
        return TravelTimeRow(
            destination_id=campus_destination.id,
            time_window=window,
            cell_id=cell_id,
            minutes=minutes,
            computed_at=computed_at,
        )

    morning, evening = TimeWindow.WEEKDAY_MORNING, TimeWindow.WEEKDAY_EVENING
    session.add_all(
        [
            # Morning: Altstadt median of 10, 20, 40 is 20; Nordend has one routed cell.
            travel(A1, morning, 10),
            travel(A2, morning, 20),
            travel(A3, morning, 40),
            travel(B1, morning, 30),
            # Evening: Altstadt median of 10 and 21 is 15.5.
            travel(A1, evening, 10),
            travel(A2, evening, 21),
        ]
    )

    # The middle leg of a day with a job: campus to employer, in the evening window only.
    session.add(
        DestinationTravelTimeRow(
            from_destination_id=campus_destination.id,
            to_destination_id=employer.id,
            time_window=evening,
            minutes=15,
            computed_at=computed_at,
        )
    )

    def rent(area: NeighbourhoodRow, eur: str, as_of: date, *, is_sample: bool) -> AreaRentRow:
        fields = provenance(as_of, is_sample=is_sample) | {
            "source": "sample fixture" if is_sample else "official report"
        }
        return AreaRentRow(
            neighbourhood_id=area.id,
            monthly_rent_eur=Decimal(eur),
            basis="median asking rent, 1-room flat",
            **fields,
        )

    session.add_all(
        [
            rent(altstadt, "700.00", date(2024, 6, 1), is_sample=False),
            rent(altstadt, "720.00", date(2025, 6, 1), is_sample=False),
            rent(altstadt, "600.00", date(2026, 1, 1), is_sample=True),
            rent(nordend, "500.00", date(2026, 1, 1), is_sample=True),
        ]
    )

    def place(
        osm_id: int, category: PlaceCategory, cell_id: str | None, place_city: str = city
    ) -> PlaceRow:
        return PlaceRow(
            city_id=place_city,
            osm_type="node",
            osm_id=osm_id,
            category=category,
            name=None,
            geom=point(11.575, 48.135),
            cell_id=cell_id,
            **provenance(),
        )

    session.add_all(
        [
            place(1, PlaceCategory.CAFE, A1),
            place(2, PlaceCategory.CAFE, A1),
            place(3, PlaceCategory.SUPERMARKET, A2),
            place(4, PlaceCategory.CAFE, B1),
            place(5, PlaceCategory.BAR, B1),
            place(6, PlaceCategory.LIBRARY, None),  # outside every neighbourhood
            place(7, PlaceCategory.CAFE, ELSEWHERE_CELL, other_city),
        ]
    )
    session.flush()

    return World(
        city_id=city,
        altstadt=altstadt.id,
        nordend=nordend.id,
        ostpark=ostpark.id,
        university_id=university.id,
        campus_id=campus.id,
        campus_destination_id=campus_destination.id,
        employer_destination_id=employer.id,
    )

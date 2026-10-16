"""The pure parts of the offline jobs: no database, no network."""

import json
from collections.abc import Sequence
from datetime import date
from decimal import Decimal
from pathlib import Path

import h3
import pytest
from shapely.geometry import box

from cities.registry import discover_cities
from domain.area import Area, RentEstimate
from domain.place import JobAccess, PlaceCategory
from domain.unknown import UNKNOWN
from infrastructure.fakes.repositories import InMemoryAreas, InMemoryPlaces, InMemoryRents
from jobs.build_cells import H3_RESOLUTION, assign_cells
from jobs.check_city_data import format_amenities, format_job_access, format_rent, summarise_city
from jobs.load_boundaries import read_boundaries
from jobs.load_rents import COLUMNS, read_rents
from jobs.make_sample_rents import (
    PARAMETERS,
    SAMPLE_FILE,
    sample_rent_eur,
    sample_rows,
)
from tests.unit.test_cities import minimal_city

REGISTRY = discover_cities()

# --- Cells -----------------------------------------------------------------

# About 3.4 km x 2.2 km near Munich: room for several resolution-8 cells.
LARGE = box(11.50, 48.10, 11.545, 48.12)
# About 150 m x 110 m: smaller than one cell.
TINY = box(11.560, 48.110, 11.562, 48.111)


def test_cells_are_resolution_8_and_cover_the_area() -> None:
    assignment = assign_cells({1: LARGE})

    assert len(assignment) >= 5
    assert set(assignment.values()) == {1}
    assert all(h3.get_resolution(cell) == H3_RESOLUTION for cell in assignment)
    assert all(len(cell) == 15 for cell in assignment)


def test_each_cell_belongs_to_exactly_one_of_two_adjacent_areas() -> None:
    west, east = box(11.50, 48.10, 11.52, 48.12), box(11.52, 48.10, 11.54, 48.12)

    assignment = assign_cells({1: west, 2: east})

    assert set(assignment.values()) == {1, 2}
    assert len(assignment) == len(assign_cells({1: west})) + len(assign_cells({2: east}))


def test_an_area_smaller_than_a_cell_still_gets_one() -> None:
    assert assign_cells({7: TINY}) != {}
    assert list(assign_cells({7: TINY}).values()) == [7]


def test_a_tiny_area_takes_a_cell_from_the_large_area_around_it() -> None:
    surrounding = box(11.52, 48.09, 11.60, 48.13)
    alone = assign_cells({1: surrounding})

    assignment = assign_cells({1: surrounding, 2: TINY})

    assert list(assignment.values()).count(2) == 1
    assert list(assignment.values()).count(1) == len(alone) - 1


# --- Boundaries ------------------------------------------------------------


def write_geojson(directory: Path, features: list[dict[str, object]]) -> None:
    collection = {"type": "FeatureCollection", "features": features}
    (directory / "none.geojson").write_text(json.dumps(collection), encoding="utf-8")


def square_feature(area_id: str, name: str, west: float, south: float) -> dict[str, object]:
    east, north = west + 0.1, south + 0.1
    ring = [[west, south], [east, south], [east, north], [west, north], [west, south]]
    return {
        "type": "Feature",
        "properties": {"id": area_id, "name": name},
        "geometry": {"type": "Polygon", "coordinates": [ring]},
    }


def test_features_with_the_same_id_are_merged_into_one_area(tmp_path: Path) -> None:
    write_geojson(
        tmp_path,
        [
            square_feature("2", "Split", 0.5, 0.5),
            square_feature("1", "Whole", 0.0, 0.0),
            square_feature("2", "Split", -0.5, -0.5),
        ],
    )

    boundaries = read_boundaries(minimal_city("x"), tmp_path)

    assert [(b.external_id, b.name, len(b.geometry.geoms)) for b in boundaries] == [
        ("1", "Whole", 1),
        ("2", "Split", 2),
    ]


def test_a_boundary_outside_the_city_bounds_is_rejected(tmp_path: Path) -> None:
    # Bounds of the test city are -1..1; this square sits at longitude 48, as if
    # latitude and longitude had been swapped.
    write_geojson(tmp_path, [square_feature("1", "Swapped", 48.0, 0.0)])

    with pytest.raises(ValueError, match="outside the bounds"):
        read_boundaries(minimal_city("x"), tmp_path)


def test_munich_districts_with_detached_parts_are_merged() -> None:
    boundaries = read_boundaries(REGISTRY.get("munich"))

    assert len(boundaries) == 25
    assert sum(len(boundary.geometry.geoms) for boundary in boundaries) == 27


# --- Rent files ------------------------------------------------------------

VALID_ROW = {
    "city_id": "munich",
    "area_external_id": "03",
    "area_name": "Maxvorstadt",
    "monthly_rent_eur": "890.00",
    "basis": "median asking rent",
    "source": "Report",
    "source_url": "",
    "as_of": "2025-06-30",
    "is_sample": "false",
}


def write_rents(path: Path, *rows: dict[str, str], columns: Sequence[str] = COLUMNS) -> Path:
    lines = [",".join(columns)] + [",".join(row[column] for column in columns) for row in rows]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def test_a_valid_rent_row_is_parsed(tmp_path: Path) -> None:
    (record,) = read_rents(write_rents(tmp_path / "rents.csv", VALID_ROW))

    assert record.monthly_rent_eur == Decimal("890.00")
    assert record.as_of == date(2025, 6, 30)
    assert record.source_url is None
    assert record.is_sample is False


@pytest.mark.parametrize(
    ("column", "value", "message"),
    [
        ("monthly_rent_eur", "cheap", "not a number"),
        ("monthly_rent_eur", "0", "must be positive"),
        ("source", " ", "source is empty"),
        ("as_of", "30.06.2025", "Invalid isoformat"),
        ("is_sample", "no", "true or false"),
    ],
)
def test_a_bad_rent_row_is_rejected_with_its_line_number(
    tmp_path: Path, column: str, value: str, message: str
) -> None:
    bad_row = VALID_ROW | {column: value}

    with pytest.raises(ValueError, match=f"line 3: .*{message}"):
        read_rents(write_rents(tmp_path / "rents.csv", VALID_ROW, bad_row))


def test_a_rent_file_without_a_required_column_is_rejected(tmp_path: Path) -> None:
    columns = [column for column in COLUMNS if column != "as_of"]

    with pytest.raises(ValueError, match=r"missing columns .*as_of"):
        read_rents(write_rents(tmp_path / "rents.csv", VALID_ROW, columns=columns))


def test_sample_rent_falls_with_distance_and_stops_at_the_floor() -> None:
    munich = PARAMETERS["munich"]

    assert sample_rent_eur(munich, 0) == 900
    assert sample_rent_eur(munich, 5) == 765
    assert sample_rent_eur(munich, 50) == sample_rent_eur(munich, 500) == 600


def test_the_committed_sample_file_is_labelled_and_matches_its_generator() -> None:
    records = read_rents(SAMPLE_FILE)
    generated = [row for city in REGISTRY.all() for row in sample_rows(city)]

    assert all(record.is_sample and "SAMPLE" in record.source for record in records)
    assert [(r.city_id, r.area_external_id, str(r.monthly_rent_eur)) for r in records] == [
        (row["city_id"], row["area_external_id"], row["monthly_rent_eur"]) for row in generated
    ]


# --- City report -----------------------------------------------------------


def areas_with_cells(cells: dict[int, list[str]]) -> InMemoryAreas:
    return InMemoryAreas(
        [Area(id=area_id, city_id="x", name=f"Area {area_id}") for area_id in cells], cells
    )


def test_amenities_are_unknown_without_a_places_snapshot_and_zero_with_one() -> None:
    areas = areas_with_cells({1: ["a"], 2: ["b"]})
    rents = InMemoryRents(areas, {})
    loaded = InMemoryPlaces(
        snapshot=date(2026, 10, 5),
        area_ids=[1, 2],
        counts={1: {PlaceCategory.CAFE: 3}},
        job_access={1: JobAccess(places_nearby=120, score=0.75)},
    )

    without_data = summarise_city(areas, rents, InMemoryPlaces(area_ids=[1, 2]), "x")
    with_data = summarise_city(areas, rents, loaded, "x")

    assert [s.amenity_counts for s in without_data] == [UNKNOWN, UNKNOWN]
    assert [s.amenity_counts for s in with_data] == [{PlaceCategory.CAFE: 3}, {}]
    assert [s.job_access for s in with_data] == [JobAccess(places_nearby=120, score=0.75), UNKNOWN]
    assert format_amenities(UNKNOWN) == "UNKNOWN"
    assert format_amenities({}) == "0 cafe, 0 gym, 0 library, 0 supermarket"
    assert format_job_access(JobAccess(places_nearby=120, score=0.75)) == "0.75 (120 nearby)"
    assert format_job_access(UNKNOWN) == "UNKNOWN"


def test_city_report_lists_every_area_with_cells_and_rent_or_unknown() -> None:
    rent = RentEstimate(Decimal("700"), "basis", "Report", None, date(2025, 6, 30), False)
    areas = areas_with_cells({1: ["a", "b"], 2: [], 3: ["c"]})
    rents = InMemoryRents(areas, {1: rent})

    summaries = summarise_city(areas, rents, InMemoryPlaces(), "x")

    assert [(s.area.id, s.cell_count, s.rent) for s in summaries] == [
        (1, 2, rent),
        (2, 0, UNKNOWN),
        (3, 1, UNKNOWN),
    ]
    assert format_rent(rent) == "700 EUR (Report, 2025-06-30)"
    assert format_rent(UNKNOWN) == "UNKNOWN"

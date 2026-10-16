"""The pure parts of the places jobs: tag mapping, snapshot parsing, job access, hotspots."""

import json
from datetime import date
from pathlib import Path

import h3
import pytest

from cities.registry import discover_cities
from domain.geo import Coordinate
from domain.place import PlaceCategory
from jobs.build_cells import H3_RESOLUTION
from jobs.build_hotspots import find_hotspots, hotspot_names
from jobs.compute_job_access import job_access
from jobs.fetch_osm_places import COLUMNS, build_query, metadata_file, places_file
from jobs.ingest_places import read_snapshot, snapshot_exists
from jobs.load_employers import COLUMNS as EMPLOYER_COLUMNS
from jobs.load_employers import EMPLOYER_FILE, read_employers
from jobs.osm_tags import TAG_CATEGORIES, classify

# --- Tags ------------------------------------------------------------------


@pytest.mark.parametrize(
    ("tags", "category"),
    [
        ({"shop": "supermarket"}, PlaceCategory.SUPERMARKET),
        ({"amenity": "cafe"}, PlaceCategory.CAFE),
        ({"amenity": "fast_food"}, PlaceCategory.RESTAURANT),
        ({"amenity": "pub"}, PlaceCategory.BAR),
        ({"leisure": "fitness_centre"}, PlaceCategory.GYM),
        ({"shop": "bakery"}, PlaceCategory.RETAIL),
        ({"shop": "bakery", "amenity": "cafe"}, PlaceCategory.RETAIL),
        ({"amenity": "bank"}, None),
        ({"shop": ""}, None),
        ({}, None),
    ],
)
def test_classify_maps_tags_to_a_category(
    tags: dict[str, str], category: PlaceCategory | None
) -> None:
    assert classify(tags) == category


def test_every_category_can_be_reached_from_some_tag() -> None:
    assert set(TAG_CATEGORIES.values()) == set(PlaceCategory)


def test_the_download_query_asks_for_exactly_the_mapped_tags() -> None:
    query = build_query(discover_cities().get("munich").bounds)

    assert all(value in query for _, value in TAG_CATEGORIES)
    # Bounds 48.06..48.25 / 11.36..11.73, widened by the 0.03 degree margin.
    assert "(48.03,11.33,48.28,11.76)" in query
    assert "out center;" in query


# --- Snapshot --------------------------------------------------------------


def write_snapshot(directory: Path, rows: list[list[str]]) -> None:
    lines = ["\t".join(COLUMNS)] + ["\t".join(row) for row in rows]
    places_file("x", directory).write_text("\n".join(lines) + "\n", encoding="utf-8")
    metadata = {"source": "OpenStreetMap", "source_url": "https://o", "retrieved_on": "2026-10-05"}
    metadata_file("x", directory).write_text(json.dumps(metadata), encoding="utf-8")


def test_snapshot_keeps_classified_places_that_have_a_coordinate(tmp_path: Path) -> None:
    write_snapshot(
        tmp_path,
        [
            ["node", "1", "48.1", "11.5", 'Café "Zur Post"', "", "cafe", ""],
            ["way", "2", "48.2", "11.6", "", "supermarket", "", ""],
            ["node", "3", "48.3", "11.7", "Bank", "", "bank", ""],
            ["relation", "4", "", "", "No coordinate", "", "cafe", ""],
            ["node", "1", "48.1", "11.5", "Duplicate of the first", "", "cafe", ""],
        ],
    )

    snapshot = read_snapshot("x", tmp_path)

    assert snapshot_exists("x", tmp_path)
    assert not snapshot_exists("y", tmp_path)
    assert snapshot.retrieved_on == date(2026, 10, 5)
    assert [(p.osm_type, p.osm_id, p.category) for p in snapshot.places] == [
        ("node", 1, PlaceCategory.CAFE),
        ("way", 2, PlaceCategory.SUPERMARKET),
    ]
    assert snapshot.places[1].name is None
    assert snapshot.places[1].location == Coordinate(lat=48.2, lon=11.6)


# --- Job access ------------------------------------------------------------

CENTRE = h3.latlng_to_cell(48.137, 11.575, H3_RESOLUTION)


def test_job_access_counts_businesses_within_two_rings() -> None:
    cells = sorted(h3.grid_disk(CENTRE, 4))
    ring_2 = next(iter(h3.grid_ring(CENTRE, 2)))
    ring_4 = next(c for c in h3.grid_ring(CENTRE, 4) if h3.grid_distance(c, ring_2) > 2)
    job_places = [CENTRE] * 5 + [ring_2] * 3

    access = job_access(cells, job_places)

    assert access[CENTRE].places_nearby == 8
    assert access[ring_2].places_nearby == 8
    assert access[ring_4].places_nearby == 0
    assert access[ring_4].score == 0
    assert 0 < access[next(iter(h3.grid_ring(CENTRE, 3)))].score <= 1


def test_job_access_score_is_the_share_of_other_cells_with_fewer_businesses() -> None:
    # Three cells so far apart that each only sees its own businesses.
    far_apart = [h3.latlng_to_cell(lat, 11.5, H3_RESOLUTION) for lat in (48.0, 48.2, 48.4)]
    job_places = [far_apart[1]] * 2 + [far_apart[2]] * 9

    access = job_access(far_apart, job_places)

    assert [access[cell].places_nearby for cell in far_apart] == [0, 2, 9]
    assert [access[cell].score for cell in far_apart] == [0.0, 0.5, 1.0]


def test_job_access_of_a_single_cell_is_zero_not_an_error() -> None:
    assert job_access([CENTRE], [CENTRE])[CENTRE].score == 0


# --- Hotspots --------------------------------------------------------------


def places_in(cell: str, count: int) -> list[Coordinate]:
    lat, lon = h3.cell_to_latlng(cell)
    return [Coordinate(lat=lat, lon=lon)] * count


FAR = h3.latlng_to_cell(48.20, 11.70, H3_RESOLUTION)
CITY_CELLS = set(h3.grid_disk(CENTRE, 3)) | set(h3.grid_disk(FAR, 3))


def test_two_separate_clusters_give_two_hotspots_strongest_first() -> None:
    neighbour = next(iter(h3.grid_ring(CENTRE, 1)))
    places = places_in(CENTRE, 30) + places_in(neighbour, 20) + places_in(FAR, 45)

    hotspots = find_hotspots(places, CITY_CELLS, min_places=40)

    assert [(h.cell, h.places) for h in hotspots] == [(CENTRE, 50), (FAR, 45)]
    far_lat, far_lon = h3.cell_to_latlng(FAR)
    assert hotspots[1].location.lat == pytest.approx(far_lat)
    assert hotspots[1].location.lon == pytest.approx(far_lon)


def test_a_hotspot_sits_at_a_real_business_not_at_the_average_position() -> None:
    """Businesses on two river banks average out to a point in the water."""
    west_bank, east_bank = Coordinate(48.1370, 11.5700), Coordinate(48.1370, 11.5800)
    places = [west_bank] * 30 + [east_bank] * 20

    (hotspot,) = find_hotspots(places, CITY_CELLS, min_places=40)

    # The average lies at longitude 11.574, nearer the west bank.
    assert hotspot.location == west_bank
    assert hotspot.places == 50


def test_one_busy_district_gives_one_hotspot() -> None:
    places = [p for cell in h3.grid_disk(CENTRE, 2) for p in places_in(cell, 10)]

    hotspots = find_hotspots(places, CITY_CELLS, min_places=40)

    assert len(hotspots) == 1


def test_a_cluster_below_the_minimum_or_outside_the_city_is_not_a_hotspot() -> None:
    outside = h3.latlng_to_cell(48.50, 11.00, H3_RESOLUTION)
    places = places_in(CENTRE, 39) + places_in(outside, 500)

    assert find_hotspots(places, CITY_CELLS, min_places=40) == []
    assert len(find_hotspots(places, CITY_CELLS, min_places=39)) == 1


def test_only_the_strongest_hotspots_are_kept() -> None:
    places = places_in(CENTRE, 50) + places_in(FAR, 45)

    hotspots = find_hotspots(places, CITY_CELLS, max_hotspots=1, min_places=40)

    assert [h.cell for h in hotspots] == [CENTRE]


def test_hotspots_are_named_after_their_area_and_numbered_when_it_repeats() -> None:
    assert hotspot_names(["Mitte", "Spandau", "Mitte"]) == [
        "Job hotspot: Mitte",
        "Job hotspot: Spandau",
        "Job hotspot: Mitte 2",
    ]


# --- Employers -------------------------------------------------------------


def test_the_sample_employer_file_has_ten_labelled_sites_per_city() -> None:
    records = read_employers(EMPLOYER_FILE)

    assert [sum(r.city_id == city for r in records) for city in ("berlin", "munich")] == [10, 10]
    assert all(record.is_sample and "SAMPLE" in record.source for record in records)
    assert len({(record.city_id, record.name) for record in records}) == 20


@pytest.mark.parametrize(
    ("column", "value", "message"),
    [
        ("name", " ", "name is empty"),
        ("lat", "north", "bad coordinate"),
        ("lat", "95", "bad coordinate: latitude out of range"),
        ("is_sample", "maybe", "is_sample must be true or false"),
    ],
)
def test_a_bad_employer_row_is_rejected_with_its_line_number(
    tmp_path: Path, column: str, value: str, message: str
) -> None:
    row = {
        "city_id": "munich",
        "name": "Example Works",
        "address": "Somewhere 1",
        "lat": "48.1",
        "lon": "11.5",
        "source": "checked by hand",
        "source_url": "",
        "as_of": "2026-10-05",
        "is_sample": "false",
    } | {column: value}
    path = tmp_path / "employers.csv"
    path.write_text(
        ",".join(EMPLOYER_COLUMNS) + "\n" + ",".join(row[c] for c in EMPLOYER_COLUMNS) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match=f"line 2: {message}"):
        read_employers(path)

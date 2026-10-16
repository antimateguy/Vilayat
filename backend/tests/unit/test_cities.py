"""City configurations and the registry. Reads the boundary files; needs no database."""

from datetime import date

import pytest
from shapely.geometry import Point

from cities.base import BoundarySource, BoundingBox, CityConfig, FeedSource, TransitFeeds
from cities.registry import CityRegistry, UnknownCityError, discover_cities
from domain.geo import Coordinate
from jobs.load_boundaries import BOUNDARY_DIR, read_boundaries

REGISTRY = discover_cities()
CITIES = REGISTRY.all()

# Campuses that are known to lie outside their city's boundary.
OUTSIDE_THE_CITY = {("munich", "Campus Garching")}


def minimal_city(city_id: str) -> CityConfig:
    return CityConfig(
        id=city_id,
        name=city_id.title(),
        centre=Coordinate(0, 0),
        bounds=BoundingBox(south=-1, west=-1, north=1, east=1),
        boundaries=BoundarySource(
            file="none.geojson",
            dataset="d",
            publisher="p",
            url="https://example.org",
            licence="l",
            retrieved_on=date(2026, 1, 1),
            id_property="id",
            name_property="name",
        ),
        universities=(),
        feeds=TransitFeeds(
            gtfs=(), streets=FeedSource("none.osm.pbf", "https://example.org", "p", "l")
        ),
        campus_source="s",
        campus_source_url="https://example.org",
        campus_as_of=date(2026, 1, 1),
    )


def test_discovery_finds_every_city_module() -> None:
    assert [city.id for city in CITIES] == ["berlin", "munich"]
    assert REGISTRY.get("munich").name == "Munich"


def test_unknown_city_is_reported_with_the_known_ones() -> None:
    with pytest.raises(UnknownCityError, match="known: berlin, munich"):
        REGISTRY.get("hamburg")


def test_registry_rejects_two_cities_with_the_same_id() -> None:
    with pytest.raises(ValueError, match="defined twice"):
        CityRegistry([minimal_city("x"), minimal_city("x")])


def test_a_new_city_needs_no_change_to_the_registry_class() -> None:
    registry = CityRegistry([*CITIES, minimal_city("hamburg")])

    assert [city.id for city in registry.all()] == ["berlin", "hamburg", "munich"]


@pytest.mark.parametrize("city", CITIES, ids=lambda city: city.id)
def test_city_has_three_to_five_universities_each_with_a_campus(city: CityConfig) -> None:
    assert 3 <= len(city.universities) <= 5
    assert all(university.campuses for university in city.universities)
    assert city.bounds.contains(city.centre)


@pytest.mark.parametrize(("city_id", "areas"), [("berlin", 97), ("munich", 25)])
def test_boundary_file_has_the_expected_number_of_areas(city_id: str, areas: int) -> None:
    city = REGISTRY.get(city_id)

    boundaries = read_boundaries(city)

    assert (BOUNDARY_DIR / city.boundaries.file).is_file()
    assert len(boundaries) == areas
    assert len({boundary.external_id for boundary in boundaries}) == areas
    assert all(boundary.geometry.is_valid for boundary in boundaries)


@pytest.mark.parametrize("city", CITIES, ids=lambda city: city.id)
def test_every_campus_lies_in_an_area_of_its_city(city: CityConfig) -> None:
    """Guards against a mistyped coordinate."""
    boundaries = read_boundaries(city)
    for university in city.universities:
        for campus in university.campuses:
            point = Point(campus.location.lon, campus.location.lat)
            inside = any(boundary.geometry.contains(point) for boundary in boundaries)
            expected = (city.id, campus.name) not in OUTSIDE_THE_CITY
            assert inside == expected, f"{university.short_name} {campus.name}"


@pytest.mark.parametrize(
    ("city_id", "campus", "area"),
    [
        ("berlin", "Campus Charlottenburg", "Charlottenburg"),
        ("berlin", "Campus Adlershof", "Adlershof"),
        ("berlin", "Campus Dahlem", "Dahlem"),
        ("munich", "City Campus", "Maxvorstadt"),
        ("munich", "Campus Pasing", "Pasing-Obermenzing"),
    ],
)
def test_campus_falls_in_the_expected_area(city_id: str, campus: str, area: str) -> None:
    city = REGISTRY.get(city_id)
    location = next(
        c.location
        for university in city.universities
        for c in university.campuses
        if c.name == campus
    )
    point = Point(location.lon, location.lat)

    containing = [b.name for b in read_boundaries(city) if b.geometry.contains(point)]

    assert containing == [area]

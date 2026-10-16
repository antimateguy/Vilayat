"""Berlin: areas are the 97 Ortsteile (localities)."""

from datetime import date

from cities.base import (
    BoundarySource,
    BoundingBox,
    CampusConfig,
    CityConfig,
    FeedSource,
    ListingPortal,
    TransitFeeds,
    UniversityConfig,
)
from domain.geo import Coordinate

CITY = CityConfig(
    id="berlin",
    name="Berlin",
    centre=Coordinate(lat=52.5200, lon=13.4050),
    bounds=BoundingBox(south=52.33, west=13.08, north=52.68, east=13.77),
    boundaries=BoundarySource(
        file="berlin_ortsteile.geojson",
        dataset="ALKIS Berlin Ortsteile",
        publisher="Geoportal Berlin",
        url=(
            "https://gdi.berlin.de/services/wfs/alkis_ortsteile?service=WFS&version=2.0.0"
            "&request=GetFeature&typeNames=alkis_ortsteile:ortsteile"
            "&outputFormat=application/json&srsName=EPSG:4326"
        ),
        licence="Datenlizenz Deutschland - Zero - Version 2.0",
        retrieved_on=date(2026, 10, 5),
        id_property="sch",
        name_property="nam",
    ),
    universities=(
        UniversityConfig(
            name="Technische Universität Berlin",
            short_name="TU Berlin",
            campuses=(
                CampusConfig(
                    name="Campus Charlottenburg",
                    address="Straße des 17. Juni 135, 10623 Berlin",
                    location=Coordinate(lat=52.51212, lon=13.32700),
                ),
            ),
        ),
        UniversityConfig(
            name="Humboldt-Universität zu Berlin",
            short_name="HU Berlin",
            campuses=(
                CampusConfig(
                    name="Campus Mitte",
                    address="Unter den Linden 6, 10117 Berlin",
                    location=Coordinate(lat=52.51834, lon=13.39292),
                ),
                CampusConfig(
                    name="Campus Adlershof",
                    address="Rudower Chaussee 26, 12489 Berlin",
                    location=Coordinate(lat=52.43114, lon=13.53115),
                ),
            ),
        ),
        UniversityConfig(
            name="Freie Universität Berlin",
            short_name="FU Berlin",
            campuses=(
                CampusConfig(
                    name="Campus Dahlem",
                    address="Habelschwerdter Allee 45, 14195 Berlin",
                    location=Coordinate(lat=52.45191, lon=13.28825),
                ),
                CampusConfig(
                    name="Campus Lankwitz",
                    address="Malteserstraße 74, 12249 Berlin",
                    location=Coordinate(lat=52.42550, lon=13.35734),
                ),
            ),
        ),
        UniversityConfig(
            name="Hochschule für Technik und Wirtschaft Berlin",
            short_name="HTW Berlin",
            campuses=(
                CampusConfig(
                    name="Campus Treskowallee",
                    address="Treskowallee 8, 10318 Berlin",
                    location=Coordinate(lat=52.49320, lon=13.52462),
                ),
                CampusConfig(
                    name="Campus Wilhelminenhof",
                    address="Wilhelminenhofstraße 75A, 12459 Berlin",
                    location=Coordinate(lat=52.45504, lon=13.52533),
                ),
            ),
        ),
    ),
    feeds=TransitFeeds(
        gtfs=(
            FeedSource(
                file="vbb_gtfs.zip",
                url="https://www.vbb.de/vbbgtfs",
                publisher="VBB Verkehrsverbund Berlin-Brandenburg GmbH",
                licence="CC BY 4.0",
            ),
        ),
        streets=FeedSource(
            file="berlin.osm.pbf",
            url="https://download.geofabrik.de/europe/germany/berlin-latest.osm.pbf",
            publisher="OpenStreetMap contributors, extract by Geofabrik",
            licence="ODbL",
        ),
    ),
    campus_source="OpenStreetMap (Nominatim geocoding of the campus address)",
    campus_source_url="https://nominatim.openstreetmap.org/",
    campus_as_of=date(2026, 10, 5),
    # City-level search pages, opened 2026-10-05. The portals have no stable link
    # for one of our areas, so the student types the area name there. The
    # Kleinanzeigen link could not be opened for checking (the site was
    # blocking this network at the time).
    listing_portals=(
        ListingPortal(
            "WG-Gesucht",
            "Rooms in shared flats",
            "https://www.wg-gesucht.de/wg-zimmer-in-Berlin.8.0.1.0.html",
        ),
        ListingPortal(
            "ImmoScout24",
            "Flats to rent",
            "https://www.immobilienscout24.de/Suche/de/berlin/berlin/wohnung-mieten",
        ),
        ListingPortal(
            "Immowelt", "Flats to rent", "https://www.immowelt.de/suche/berlin/wohnungen/mieten"
        ),
        ListingPortal(
            "Kleinanzeigen",
            "Flats to rent, private offers",
            "https://www.kleinanzeigen.de/s-wohnung-mieten/berlin/c203l3331",
        ),
    ),
)

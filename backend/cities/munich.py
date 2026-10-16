"""Munich: areas are the 25 Stadtbezirke (city districts)."""

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
    id="munich",
    name="Munich",
    centre=Coordinate(lat=48.1372, lon=11.5756),
    bounds=BoundingBox(south=48.06, west=11.36, north=48.25, east=11.73),
    boundaries=BoundarySource(
        file="munich_stadtbezirke.geojson",
        dataset="Stadtbezirke München",
        publisher="Landeshauptstadt München, GeodatenService",
        url=(
            "https://geoportal.muenchen.de/geoserver/gsm_wfs/ows?service=WFS&version=2.0.0"
            "&request=GetFeature&typeNames=gsm_wfs:vablock_stadtbezirk"
            "&outputFormat=application/json&srsName=EPSG:4326"
        ),
        licence="Datenlizenz Deutschland - Namensnennung - Version 2.0",
        retrieved_on=date(2026, 10, 5),
        id_property="sb_nummer",
        name_property="sb_name",
    ),
    universities=(
        UniversityConfig(
            name="Technische Universität München",
            short_name="TUM",
            campuses=(
                CampusConfig(
                    name="City Campus",
                    address="Arcisstraße 21, 80333 München",
                    location=Coordinate(lat=48.14888, lon=11.56777),
                ),
                CampusConfig(
                    # North of the city boundary, so it lies in no Munich area.
                    name="Campus Garching",
                    address="Boltzmannstraße 15, 85748 Garching bei München",
                    location=Coordinate(lat=48.26585, lon=11.67061),
                ),
            ),
        ),
        UniversityConfig(
            name="Ludwig-Maximilians-Universität München",
            short_name="LMU",
            campuses=(
                CampusConfig(
                    name="Main Campus",
                    address="Geschwister-Scholl-Platz 1, 80539 München",
                    location=Coordinate(lat=48.15048, lon=11.57984),
                ),
                CampusConfig(
                    name="Campus Großhadern",
                    address="Butenandtstraße 5, 81377 München",
                    location=Coordinate(lat=48.11381, lon=11.46540),
                ),
            ),
        ),
        UniversityConfig(
            name="Hochschule München",
            short_name="HM",
            campuses=(
                CampusConfig(
                    name="Campus Lothstraße",
                    address="Lothstraße 34, 80335 München",
                    location=Coordinate(lat=48.15469, lon=11.55398),
                ),
                CampusConfig(
                    name="Campus Pasing",
                    address="Am Stadtpark 20, 81243 München",
                    location=Coordinate(lat=48.14147, lon=11.45096),
                ),
            ),
        ),
    ),
    feeds=TransitFeeds(
        gtfs=(
            FeedSource(
                file="mvv_gtfs.zip",
                url="https://www.mvv-muenchen.de/fileadmin/mediapool/developer/opendata/gesamt_gtfs.zip",
                publisher="Münchner Verkehrs- und Tarifverbund GmbH (MVV)",
                licence="CC BY",
            ),
        ),
        # The BBBike extract reaches beyond the city, so it covers Garching and Neubiberg.
        streets=FeedSource(
            file="munich.osm.pbf",
            url="https://download.bbbike.org/osm/bbbike/Muenchen/Muenchen.osm.pbf",
            publisher="OpenStreetMap contributors, extract by BBBike",
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
            "https://www.wg-gesucht.de/wg-zimmer-in-Muenchen.90.0.1.0.html",
        ),
        ListingPortal(
            "ImmoScout24",
            "Flats to rent",
            "https://www.immobilienscout24.de/Suche/de/bayern/muenchen/wohnung-mieten",
        ),
        ListingPortal(
            "Immowelt", "Flats to rent", "https://www.immowelt.de/suche/muenchen/wohnungen/mieten"
        ),
        ListingPortal(
            "Kleinanzeigen",
            "Flats to rent, private offers",
            "https://www.kleinanzeigen.de/s-wohnung-mieten/muenchen/c203l6411",
        ),
    ),
)

"""Download a snapshot of OpenStreetMap places for a city from the Overpass API.

This is the only place job that needs the network. It writes two files to
backend/data/osm/: the places as tab-separated text and a small metadata file
with the retrieval date. `jobs.ingest_places` then loads them offline.

OpenStreetMap data is (c) OpenStreetMap contributors, licensed under the ODbL.

Run:  uv run python -m jobs.fetch_osm_places --city berlin
"""

import argparse
import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

from cities.base import BoundingBox, CityConfig
from cities.registry import discover_cities
from jobs.osm_tags import TAG_KEYS, values_for
from jobs.runtime import configure_logging, https_context

logger = logging.getLogger(__name__)

OSM_DIR = Path(__file__).resolve().parents[1] / "data" / "osm"
# Public Overpass instances, tried in order. A request that fails (server busy or
# network error) moves on to the next one.
OVERPASS_URLS = (
    "https://overpass-api.de/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
)
USER_AGENT = "EduCommuteMatrix/0.1 (student project; places snapshot)"
TIMEOUT_SECONDS = 300

# The query box reaches past the city so that places just across the boundary
# still count for the cells at the edge. About 3 km.
MARGIN_DEGREES = 0.03

COLUMNS = ("type", "id", "lat", "lon", "name", *TAG_KEYS)


def places_file(city_id: str, directory: Path = OSM_DIR) -> Path:
    return directory / f"{city_id}_places.tsv"


def metadata_file(city_id: str, directory: Path = OSM_DIR) -> Path:
    return directory / f"{city_id}_places.meta.json"


def build_query(bounds: BoundingBox) -> str:
    """Overpass QL: every node, way and relation with one of our tags in the box.

    `out center` gives ways and relations (a shop drawn as a building outline)
    one coordinate, so every element becomes a point.
    """
    box = (
        f"{bounds.south - MARGIN_DEGREES},{bounds.west - MARGIN_DEGREES},"
        f"{bounds.north + MARGIN_DEGREES},{bounds.east + MARGIN_DEGREES}"
    )
    fields = ",".join(["::type", "::id", "::lat", "::lon", "name", *TAG_KEYS])
    filters = "\n".join(
        f'  nwr["{key}"~"^({"|".join(values_for(key))})$"]({box});' for key in TAG_KEYS
    )
    return (
        f'[out:csv({fields};true;"\\t")][timeout:{TIMEOUT_SECONDS}];\n'
        f"(\n{filters}\n);\nout center;\n"
    )


def fetch(city: CityConfig, directory: Path = OSM_DIR) -> int:
    query = build_query(city.bounds)
    endpoint, body = _run_query(query)

    lines = body.splitlines()
    if not lines or not lines[0].startswith("@type"):
        raise RuntimeError(f"unexpected Overpass response: {body[:200]!r}")
    lines[0] = "\t".join(COLUMNS)

    directory.mkdir(parents=True, exist_ok=True)
    # newline="\n" keeps the files byte-identical on every operating system.
    places_file(city.id, directory).write_text(
        "\n".join(lines) + "\n", encoding="utf-8", newline="\n"
    )
    metadata = {
        "city_id": city.id,
        "source": "OpenStreetMap via the Overpass API (ODbL, (c) OpenStreetMap contributors)",
        "source_url": endpoint,
        "retrieved_on": date.today().isoformat(),
        "elements": len(lines) - 1,
        "query": query,
    }
    metadata_file(city.id, directory).write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n"
    )
    logger.info("%s: saved %d OpenStreetMap elements", city.id, len(lines) - 1)
    return len(lines) - 1


def _run_query(query: str) -> tuple[str, str]:
    """Returns the endpoint that answered and its response."""
    failures = []
    for endpoint in OVERPASS_URLS:
        request = urllib.request.Request(
            endpoint,
            data=urllib.parse.urlencode({"data": query}).encode(),
            headers={"User-Agent": USER_AGENT},
        )
        try:
            with urllib.request.urlopen(
                request, timeout=TIMEOUT_SECONDS + 30, context=https_context()
            ) as response:
                return endpoint, response.read().decode("utf-8")
        except (urllib.error.URLError, TimeoutError) as error:
            logger.warning("%s failed: %s", endpoint, error)
            failures.append(f"{endpoint}: {error}")
    raise RuntimeError("no Overpass instance answered: " + "; ".join(failures))


def main() -> None:
    registry = discover_cities()
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--city", required=True, choices=[city.id for city in registry.all()])
    arguments = parser.parse_args()

    configure_logging()
    fetch(registry.get(arguments.city))


if __name__ == "__main__":
    main()

"""Download the timetable (GTFS) and street (OpenStreetMap) files of a city.

The files are large, change often and can be fetched again at any time, so they
go to backend/data/raw/<city>/, which is not committed. Next to each file a
small .meta.json records where it came from and when.

Run:  uv run python -m jobs.fetch_feeds --city munich
"""

import argparse
import json
import logging
import shutil
import urllib.request
from datetime import date
from pathlib import Path

from cities.base import CityConfig, FeedSource
from cities.registry import discover_cities
from jobs.runtime import configure_logging, https_context

logger = logging.getLogger(__name__)

RAW_DIR = Path(__file__).resolve().parents[1] / "data" / "raw"
USER_AGENT = "EduCommuteMatrix/0.1 (student project; feed download)"
TIMEOUT_SECONDS = 120


def feed_path(city_id: str, feed: FeedSource, directory: Path = RAW_DIR) -> Path:
    return directory / city_id / feed.file


def metadata_path(city_id: str, feed: FeedSource, directory: Path = RAW_DIR) -> Path:
    return directory / city_id / f"{feed.file}.meta.json"


def all_feeds(city: CityConfig) -> list[FeedSource]:
    return [*city.feeds.gtfs, city.feeds.streets]


def missing_feeds(city: CityConfig, directory: Path = RAW_DIR) -> list[str]:
    return [
        feed.file for feed in all_feeds(city) if not feed_path(city.id, feed, directory).is_file()
    ]


def retrieved_on(city_id: str, feed: FeedSource, directory: Path = RAW_DIR) -> date | None:
    path = metadata_path(city_id, feed, directory)
    if not path.is_file():
        return None
    return date.fromisoformat(json.loads(path.read_text(encoding="utf-8"))["retrieved_on"])


def fetch(city: CityConfig, directory: Path = RAW_DIR, *, force: bool = False) -> None:
    for feed in all_feeds(city):
        target = feed_path(city.id, feed, directory)
        if target.is_file() and not force:
            logger.info("%s: %s is already there, skipping", city.id, feed.file)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        # Download to a .part file first, so an interrupted download is never
        # mistaken for a complete one.
        partial = target.with_name(target.name + ".part")
        request = urllib.request.Request(feed.url, headers={"User-Agent": USER_AGENT})
        logger.info("%s: downloading %s from %s", city.id, feed.file, feed.url)
        with (
            urllib.request.urlopen(
                request, timeout=TIMEOUT_SECONDS, context=https_context()
            ) as response,
            partial.open("wb") as file,
        ):
            shutil.copyfileobj(response, file, length=1024 * 1024)
        partial.replace(target)
        size = target.stat().st_size
        metadata = {
            "file": feed.file,
            "url": feed.url,
            "publisher": feed.publisher,
            "licence": feed.licence,
            "retrieved_on": date.today().isoformat(),
            "bytes": size,
        }
        metadata_path(city.id, feed, directory).write_text(
            json.dumps(metadata, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        logger.info("%s: saved %s (%.1f MB)", city.id, feed.file, size / 1e6)


def main() -> None:
    registry = discover_cities()
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--city", required=True, choices=[city.id for city in registry.all()])
    parser.add_argument("--force", action="store_true", help="download even if the file exists")
    arguments = parser.parse_args()

    configure_logging()
    fetch(registry.get(arguments.city), force=arguments.force)


if __name__ == "__main__":
    main()

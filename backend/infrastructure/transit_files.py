"""Rail and tram lines read from the files jobs.build_transit_lines writes."""

import json
from collections.abc import Sequence
from functools import cache
from pathlib import Path

from domain.geo import Coordinate
from domain.route import LegMode
from domain.transit import TransitLine
from ports.transit import TransitNetworkSource

TRANSIT_DIR = Path(__file__).resolve().parents[1] / "data" / "transit"


class FileTransitNetwork(TransitNetworkSource):
    """The files are small and change only with a new timetable, so each is
    read once per process."""

    def __init__(self, directory: Path = TRANSIT_DIR) -> None:
        self._directory = directory

    def lines(self, city_id: str) -> Sequence[TransitLine]:
        return _read(self._directory / f"{city_id}.geojson")


@cache
def _read(path: Path) -> tuple[TransitLine, ...]:
    if not path.exists():
        return ()
    data = json.loads(path.read_text(encoding="utf-8"))
    return tuple(
        TransitLine(
            label=feature["properties"]["label"],
            mode=LegMode(feature["properties"]["mode"]),
            colour=feature["properties"].get("colour"),
            stops=tuple(
                Coordinate(lat=lat, lon=lon) for lon, lat in feature["geometry"]["coordinates"]
            ),
        )
        for feature in data["features"]
    )

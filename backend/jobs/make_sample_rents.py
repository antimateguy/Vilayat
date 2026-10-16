"""Generate the SAMPLE rent file. These are not real rents.

Real area rents have not been supplied yet, so this writes a clearly labelled
stand-in: a synthetic figure per area that falls with distance from the city
centre. Every row is marked is_sample=true and says so in its source and basis.
Delete this script and the sample file once real data is loaded.

Run:  uv run python -m jobs.make_sample_rents
"""

import csv
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from cities.base import CityConfig
from cities.registry import discover_cities
from domain.geo import Coordinate
from jobs.load_boundaries import read_boundaries
from jobs.load_rents import COLUMNS

SAMPLE_FILE = Path(__file__).resolve().parents[1] / "data" / "rents" / "sample_rents.csv"
SAMPLE_SOURCE = "SAMPLE DATA (synthetic, not a real rent)"
SAMPLE_AS_OF = date(2026, 10, 5)
FLAT_SIZE_SQM = 30


@dataclass(frozen=True)
class SampleParameters:
    centre_eur_per_sqm: float
    drop_per_km: float
    floor_eur_per_sqm: float


# Invented round numbers that only make the two cities look different.
PARAMETERS = {
    "berlin": SampleParameters(centre_eur_per_sqm=22, drop_per_km=0.6, floor_eur_per_sqm=12),
    "munich": SampleParameters(centre_eur_per_sqm=30, drop_per_km=0.9, floor_eur_per_sqm=20),
}


def sample_rent_eur(parameters: SampleParameters, distance_km: float) -> int:
    """Monthly rent of a 30 m2 flat, rounded to 5 EUR."""
    eur_per_sqm = max(
        parameters.floor_eur_per_sqm,
        parameters.centre_eur_per_sqm - parameters.drop_per_km * distance_km,
    )
    return round(eur_per_sqm * FLAT_SIZE_SQM / 5) * 5


def sample_rows(city: CityConfig) -> list[dict[str, str]]:
    parameters = PARAMETERS[city.id]
    rows = []
    for boundary in read_boundaries(city):
        point = boundary.geometry.representative_point()
        distance_km = city.centre.distance_km(Coordinate(lat=point.y, lon=point.x))
        rows.append(
            {
                "city_id": city.id,
                "area_external_id": boundary.external_id,
                "area_name": boundary.name,
                "monthly_rent_eur": str(sample_rent_eur(parameters, distance_km)),
                "basis": (
                    f"SAMPLE: synthetic figure for a {FLAT_SIZE_SQM} m2 flat, "
                    "derived only from distance to the city centre"
                ),
                "source": SAMPLE_SOURCE,
                "source_url": "",
                "as_of": SAMPLE_AS_OF.isoformat(),
                "is_sample": "true",
            }
        )
    return rows


def main() -> None:
    rows = [row for city in discover_cities().all() for row in sample_rows(city)]
    SAMPLE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with SAMPLE_FILE.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {len(rows)} sample rows to {SAMPLE_FILE}")


if __name__ == "__main__":
    main()

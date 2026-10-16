"""Load curated employer sites from a CSV file as destinations a student can pin.

The file format is described in backend/data/employers/README.md.

Run:  uv run python -m jobs.load_employers data/employers/sample_employers.csv
"""

import argparse
import csv
import logging
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from geoalchemy2.shape import from_shape
from shapely.geometry import Point
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from domain.destination import DestinationKind
from domain.geo import Coordinate
from infrastructure.db.models import SRID_WGS84, DestinationRow
from jobs.runtime import configure_logging, job_session

logger = logging.getLogger(__name__)

EMPLOYER_FILE = Path(__file__).resolve().parents[1] / "data" / "employers" / "sample_employers.csv"
COLUMNS = (
    "city_id",
    "name",
    "address",
    "lat",
    "lon",
    "source",
    "source_url",
    "as_of",
    "is_sample",
)


@dataclass(frozen=True)
class EmployerRecord:
    city_id: str
    name: str
    location: Coordinate
    source: str
    source_url: str | None
    as_of: date
    is_sample: bool


def read_employers(path: Path) -> list[EmployerRecord]:
    """Parse the CSV. A file with any bad row is rejected as a whole."""
    with path.open(encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        missing = set(COLUMNS) - set(reader.fieldnames or ())
        if missing:
            raise ValueError(f"{path.name}: missing columns {sorted(missing)}")

        records: list[EmployerRecord] = []
        errors: list[str] = []
        for line, row in enumerate(reader, start=2):
            try:
                records.append(_to_record(row))
            except ValueError as error:
                errors.append(f"line {line}: {error}")
    if errors:
        raise ValueError(f"{path.name}: " + "; ".join(errors))
    return records


def load_employers(session: Session, records: Sequence[EmployerRecord]) -> int:
    """Make each city's employer destinations match the file.

    An employer that keeps its name keeps its row and id, so travel times
    already computed for it stay valid. Employers no longer listed are removed.
    """
    for city_id in sorted({record.city_id for record in records}):
        city_records = [record for record in records if record.city_id == city_id]
        is_employer = (
            DestinationRow.city_id == city_id,
            DestinationRow.kind == DestinationKind.EMPLOYER,
        )
        names = [record.name for record in city_records]
        session.execute(
            delete(DestinationRow).where(*is_employer, DestinationRow.name.not_in(names))
        )
        existing = {
            row.name: row for row in session.scalars(select(DestinationRow).where(*is_employer))
        }
        for record in city_records:
            row = existing.get(record.name) or DestinationRow(
                city_id=city_id, kind=DestinationKind.EMPLOYER, name=record.name
            )
            row.geom = from_shape(Point(record.location.lon, record.location.lat), srid=SRID_WGS84)
            row.source = record.source
            row.source_url = record.source_url
            row.as_of = record.as_of
            row.is_sample = record.is_sample
            session.add(row)
    session.flush()
    logger.info("loaded %d employer sites", len(records))
    return len(records)


def _to_record(row: dict[str, str]) -> EmployerRecord:
    for column in ("city_id", "name", "source"):
        if not row[column].strip():
            raise ValueError(f"{column} is empty")
    if row["is_sample"] not in ("true", "false"):
        raise ValueError(f"is_sample must be true or false: {row['is_sample']!r}")
    try:
        location = Coordinate(lat=float(row["lat"]), lon=float(row["lon"]))
    except ValueError as error:
        raise ValueError(f"bad coordinate: {error}") from None
    return EmployerRecord(
        city_id=row["city_id"].strip(),
        name=row["name"].strip(),
        location=location,
        source=row["source"].strip(),
        source_url=row["source_url"].strip() or None,
        as_of=date.fromisoformat(row["as_of"]),
        is_sample=row["is_sample"] == "true",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("csv_file", type=Path)
    arguments = parser.parse_args()

    configure_logging()
    records = read_employers(arguments.csv_file)
    with job_session() as session:
        load_employers(session, records)


if __name__ == "__main__":
    main()

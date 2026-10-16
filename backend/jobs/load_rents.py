"""Load area-level rent estimates from a CSV file.

The file format is described in backend/data/rents/README.md.

Run:  uv run python -m jobs.load_rents data/rents/sample_rents.csv
"""

import argparse
import csv
import logging
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from infrastructure.db.models import AreaRentRow, NeighbourhoodRow
from jobs.runtime import configure_logging, job_session

logger = logging.getLogger(__name__)

COLUMNS = (
    "city_id",
    "area_external_id",
    "area_name",
    "monthly_rent_eur",
    "basis",
    "source",
    "source_url",
    "as_of",
    "is_sample",
)


@dataclass(frozen=True)
class RentRecord:
    city_id: str
    area_external_id: str
    monthly_rent_eur: Decimal
    basis: str
    source: str
    source_url: str | None
    as_of: date
    is_sample: bool


def read_rents(path: Path) -> list[RentRecord]:
    """Parse the CSV. Every problem is reported with its line number; a file with
    any bad row is rejected as a whole rather than loaded in part."""
    with path.open(encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        missing = set(COLUMNS) - set(reader.fieldnames or ())
        if missing:
            raise ValueError(f"{path.name}: missing columns {sorted(missing)}")

        records: list[RentRecord] = []
        errors: list[str] = []
        for line, row in enumerate(reader, start=2):
            try:
                records.append(_to_record(row))
            except ValueError as error:
                errors.append(f"line {line}: {error}")
    if errors:
        raise ValueError(f"{path.name}: " + "; ".join(errors))
    return records


def load_rents(session: Session, records: Sequence[RentRecord]) -> int:
    """Insert or update rent rows. Safe to run again with the same file."""
    if not records:
        return 0
    area_ids = {
        (city_id, external_id): area_id
        for area_id, city_id, external_id in session.execute(
            select(NeighbourhoodRow.id, NeighbourhoodRow.city_id, NeighbourhoodRow.external_id)
        )
    }
    unknown = sorted(
        {
            f"{record.city_id}/{record.area_external_id}"
            for record in records
            if (record.city_id, record.area_external_id) not in area_ids
        }
    )
    if unknown:
        raise ValueError(f"rents refer to areas that do not exist: {', '.join(unknown)}")

    statement = insert(AreaRentRow).values(
        [
            {
                "neighbourhood_id": area_ids[record.city_id, record.area_external_id],
                "monthly_rent_eur": record.monthly_rent_eur,
                "basis": record.basis,
                "source": record.source,
                "source_url": record.source_url,
                "as_of": record.as_of,
                "is_sample": record.is_sample,
            }
            for record in records
        ]
    )
    updated = ("monthly_rent_eur", "basis", "source_url", "is_sample")
    session.execute(
        statement.on_conflict_do_update(
            constraint="uq_area_rents_neighbourhood_id_source_as_of",
            set_={column: statement.excluded[column] for column in updated},
        )
    )
    logger.info("loaded %d rent figures", len(records))
    return len(records)


def _to_record(row: dict[str, str]) -> RentRecord:
    try:
        rent = Decimal(row["monthly_rent_eur"])
    except InvalidOperation:
        raise ValueError(f"monthly_rent_eur is not a number: {row['monthly_rent_eur']!r}") from None
    if rent <= 0:
        raise ValueError(f"monthly_rent_eur must be positive: {rent}")
    for column in ("city_id", "area_external_id", "basis", "source"):
        if not row[column].strip():
            raise ValueError(f"{column} is empty")
    if row["is_sample"] not in ("true", "false"):
        raise ValueError(f"is_sample must be true or false: {row['is_sample']!r}")
    return RentRecord(
        city_id=row["city_id"].strip(),
        area_external_id=row["area_external_id"].strip(),
        monthly_rent_eur=rent,
        basis=row["basis"].strip(),
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
    records = read_rents(arguments.csv_file)
    with job_session() as session:
        load_rents(session, records)


if __name__ == "__main__":
    main()

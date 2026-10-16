"""Where a dataset comes from and how current it is."""

from dataclasses import dataclass
from datetime import date

from domain.unknown import Unknown


@dataclass(frozen=True, slots=True)
class DataSource:
    """Shown wherever the data appears: no figure without its source and date."""

    used_for: str
    """What the app uses it for, for example "Area boundaries"."""
    name: str
    publisher: str
    licence: str
    as_of: date | Unknown
    is_sample: bool = False
    """True for placeholder data that real data must replace."""
    url: str | None = None

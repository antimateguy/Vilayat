"""Hard constraints of a search."""

from dataclasses import dataclass
from decimal import Decimal

from domain.specification import MaxCommute, MaxRent, MinJobAccess, Specification

MAX_COMMUTE_LIMIT_MINUTES = 180
MAX_RENT_LIMIT_EUR = 20000
"""The highest rent ceiling a search accepts; far above any student budget."""


@dataclass(frozen=True, slots=True)
class Constraints:
    """The limits a student sets.

    An area that breaks one is excluded, however well it scores on everything else.
    """

    campus_id: int
    max_commute_minutes: int
    max_rent_eur: Decimal
    min_job_access: float | None = None
    """Optional floor on the service-job access score (0 to 1)."""

    def __post_init__(self) -> None:
        if not 1 <= self.max_commute_minutes <= MAX_COMMUTE_LIMIT_MINUTES:
            raise ValueError(
                f"max commute must be 1 to {MAX_COMMUTE_LIMIT_MINUTES} minutes: "
                f"{self.max_commute_minutes}"
            )
        if self.max_rent_eur <= 0:
            raise ValueError(f"max rent must be positive: {self.max_rent_eur}")
        if self.min_job_access is not None and not 0 <= self.min_job_access <= 1:
            raise ValueError(f"min job access must be 0 to 1: {self.min_job_access}")

    def to_specification(self) -> Specification:
        """The limits as one composed specification an area either meets or not."""
        specification = MaxCommute(self.max_commute_minutes) & MaxRent(self.max_rent_eur)
        if self.min_job_access is not None:
            specification = specification & MinJobAccess(self.min_job_access)
        return specification

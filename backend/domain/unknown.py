"""The explicit "we do not have this figure" value."""

from enum import Enum
from typing import Final


class Unknown(Enum):
    """Type of the single UNKNOWN value.

    Missing data is never replaced by a guess or a zero. A figure the system does
    not have is UNKNOWN, and because `Decimal | Unknown` is a different type from
    `Decimal`, the type checker makes every caller handle that case.

    None is not used for this: None also means "not provided" or "not applicable",
    while UNKNOWN always means "this figure exists in the world but we lack it".
    """

    UNKNOWN = "UNKNOWN"

    def __repr__(self) -> str:
        return "UNKNOWN"


UNKNOWN: Final = Unknown.UNKNOWN

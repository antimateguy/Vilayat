"""A short written summary of an area, stored with the figures it was written from."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Final

BriefingFacts = Mapping[str, str | int | bool]
"""The figures a briefing is written from. Only plain values, so that the
stored copy can be compared with freshly computed figures exactly."""

NOT_KNOWN: Final = "unknown"
"""How a missing figure is written in BriefingFacts."""


@dataclass(frozen=True, slots=True)
class AreaBriefing:
    area_id: int
    content: str
    facts: BriefingFacts
    """Exactly what the model was given. A briefing is shown only while these
    are still the area's current figures."""
    model: str
    generated_at: datetime

"""Travel-time concepts."""

from enum import StrEnum


class TimeWindow(StrEnum):
    """Departure windows the offline job computes public-transport times for."""

    WEEKDAY_MORNING = "weekday_morning"
    WEEKDAY_EVENING = "weekday_evening"

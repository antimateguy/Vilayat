"""The model provider's daily allowance: which day a request counts against.

Google's free tier counts requests per day and starts each day at midnight
Pacific time (US and Canada west coast). The rule for daylight saving time is
written out here, so no time-zone database is needed: Pacific time is UTC-8,
and UTC-7 from 02:00 on the second Sunday of March until 02:00 on the first
Sunday of November.
"""

from datetime import UTC, date, datetime, time, timedelta

_STANDARD = timedelta(hours=-8)
_DAYLIGHT = timedelta(hours=-7)
_SUNDAY = 6


def _nth_sunday(year: int, month: int, n: int) -> date:
    first = date(year, month, 1)
    first_sunday = first + timedelta(days=(_SUNDAY - first.weekday()) % 7)
    return first_sunday + timedelta(weeks=n - 1)


def pacific_offset(moment: datetime) -> timedelta:
    """Pacific time minus UTC at the given moment (which must carry a time zone)."""
    utc = moment.astimezone(UTC)
    year = utc.year
    # 02:00 local standard time is 10:00 UTC; 02:00 local daylight time is 09:00 UTC.
    daylight_starts = datetime.combine(_nth_sunday(year, 3, 2), time(10), UTC)
    daylight_ends = datetime.combine(_nth_sunday(year, 11, 1), time(9), UTC)
    return _DAYLIGHT if daylight_starts <= utc < daylight_ends else _STANDARD


def quota_day(moment: datetime) -> date:
    """The provider's day a request made at this moment is counted on."""
    return (moment.astimezone(UTC) + pacific_offset(moment)).date()


def next_reset(moment: datetime) -> datetime:
    """When the next day's allowance starts, in UTC."""
    # The next local midnight, written as if it were UTC, then shifted by
    # whichever offset is actually in force at that instant.
    local_midnight = datetime.combine(quota_day(moment) + timedelta(days=1), time(0), UTC)
    for offset in (_STANDARD, _DAYLIGHT):
        instant = local_midnight - offset
        if pacific_offset(instant) == offset:
            return instant
    raise AssertionError("unreachable: one of the two offsets always applies")

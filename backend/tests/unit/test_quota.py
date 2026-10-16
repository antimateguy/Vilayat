"""Which provider day a request counts against, and when the next one starts."""

from datetime import UTC, date, datetime

import pytest

from domain.quota import next_reset, quota_day
from infrastructure.budget import DailyBudget
from infrastructure.fakes.ai import InMemoryUsageLedger
from ports.usage import DailyLimitReachedError


def utc(year: int, month: int, day: int, hour: int = 0, minute: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=UTC)


@pytest.mark.parametrize(
    ("moment", "day", "reset"),
    [
        # Summer time (UTC-7): the day starts at 07:00 UTC.
        (utc(2026, 10, 16, 12, 0), date(2026, 10, 16), utc(2026, 10, 17, 7)),
        (utc(2026, 10, 16, 6, 30), date(2026, 10, 15), utc(2026, 10, 16, 7)),
        # Winter time (UTC-8): the day starts at 08:00 UTC.
        (utc(2026, 12, 1, 7, 30), date(2026, 11, 30), utc(2026, 12, 1, 8)),
        (utc(2026, 12, 1, 8, 0), date(2026, 12, 1), utc(2026, 12, 2, 8)),
        # Summer time ends on Sunday 1 November 2026; that midnight is still summer time.
        (utc(2026, 10, 31, 20, 0), date(2026, 10, 31), utc(2026, 11, 1, 7)),
        (utc(2026, 11, 1, 12, 0), date(2026, 11, 1), utc(2026, 11, 2, 8)),
        # Summer time starts on Sunday 8 March 2026; that midnight is still winter time.
        (utc(2026, 3, 7, 20, 0), date(2026, 3, 7), utc(2026, 3, 8, 8)),
        (utc(2026, 3, 8, 12, 0), date(2026, 3, 8), utc(2026, 3, 9, 7)),
    ],
)
def test_the_day_follows_pacific_time(moment: datetime, day: date, reset: datetime) -> None:
    assert quota_day(moment) == day
    assert next_reset(moment) == reset


def test_the_allowance_starts_again_on_the_next_provider_day() -> None:
    now = utc(2026, 10, 16, 12)
    budget = DailyBudget(InMemoryUsageLedger(), "flash-test", 1, clock=lambda: now)

    budget.spend()
    with pytest.raises(DailyLimitReachedError):
        budget.spend()
    now = utc(2026, 10, 17, 7)  # midnight in California
    budget.spend()

    assert budget.status().used == 1


def test_reading_the_status_spends_nothing() -> None:
    budget = DailyBudget(InMemoryUsageLedger(), "flash-test", 3)

    for _ in range(3):
        status = budget.status()

    assert (status.used, status.limit, status.reached) == (0, 3, False)

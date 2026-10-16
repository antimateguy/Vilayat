"""The daily allowance of one model, counted in the shared ledger."""

from collections.abc import Callable
from datetime import UTC, datetime

from domain.quota import next_reset, quota_day
from ports.usage import BudgetStatus, DailyLimitReachedError, RequestBudget, UsageLedger


def _now() -> datetime:
    return datetime.now(UTC)


class DailyBudget(RequestBudget):
    def __init__(
        self,
        ledger: UsageLedger,
        model: str,
        limit: int,
        clock: Callable[[], datetime] = _now,
    ) -> None:
        self._ledger = ledger
        self._model = model
        self._limit = limit
        self._clock = clock

    def spend(self, units: int = 1) -> None:
        now = self._clock()
        if not self._ledger.take(self._model, quota_day(now), self._limit, units):
            raise DailyLimitReachedError(self._model, next_reset(now))

    def use_up(self) -> None:
        self._ledger.use_up(self._model, quota_day(self._clock()), self._limit)

    def status(self) -> BudgetStatus:
        now = self._clock()
        used = self._ledger.used(self._model, quota_day(now))
        return BudgetStatus(self._model, min(used, self._limit), self._limit, next_reset(now))


class UnlimitedBudget(RequestBudget):
    """For tests and tools that talk to the model outside the app's allowance."""

    def __init__(self, model: str = "unlimited") -> None:
        self._model = model

    def spend(self, units: int = 1) -> None:
        return None

    def use_up(self) -> None:
        return None

    def status(self) -> BudgetStatus:
        return BudgetStatus(self._model, 0, 1, next_reset(_now()))

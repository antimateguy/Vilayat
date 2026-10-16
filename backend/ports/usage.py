"""Port for the daily allowance of model requests.

The free tier of the model provider allows a fixed number of requests per day.
That allowance is a hard limit for this project: once it is used up, the
features that need the model stay off until the provider's next day starts,
instead of sending requests that would fail or cost money.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, datetime

from ports.embedder import EmbedderUnavailableError
from ports.llm import LLMUnavailableError


class DailyLimitReachedError(LLMUnavailableError, EmbedderUnavailableError):
    """The day's allowance for a model is used up.

    A kind of "model unavailable", so every service that already falls back
    without the model does so here too, whichever model it was.
    """

    def __init__(self, model: str, resets_at: datetime) -> None:
        super().__init__(f"{model}: the daily request allowance is used up until {resets_at}")
        self.model = model
        self.resets_at = resets_at


@dataclass(frozen=True)
class BudgetStatus:
    model: str
    used: int
    limit: int
    resets_at: datetime

    @property
    def reached(self) -> bool:
        return self.used >= self.limit


class RequestBudget(ABC):
    """Counts the requests to one model against its daily allowance.

    The model adapters ask before every request they send, retries included.
    """

    @abstractmethod
    def spend(self, units: int = 1) -> None:
        """Count requests before sending them; raises DailyLimitReachedError when
        fewer than `units` are left. The free tier counts every text in an
        embedding call as one request, so a call of 16 texts spends 16."""

    @abstractmethod
    def use_up(self) -> None:
        """Record that the provider itself said the day's allowance is gone,
        so no further request is sent today even if the count is lower."""

    @abstractmethod
    def status(self) -> BudgetStatus:
        """Today's count, without spending anything."""


class UsageLedger(ABC):
    """Where the daily counts are kept. Shared by the API and the offline jobs,
    so both draw on the same allowance."""

    @abstractmethod
    def take(self, model: str, day: date, limit: int, units: int = 1) -> bool:
        """Count `units` requests if the day's count stays within the limit;
        False, counting nothing, if it would not. Must be atomic: two requests at
        once never both get the last one."""

    @abstractmethod
    def used(self, model: str, day: date) -> int: ...

    @abstractmethod
    def use_up(self, model: str, day: date, limit: int) -> None:
        """Raise the day's count to the limit."""

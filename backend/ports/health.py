"""Port for checking that something the app depends on is reachable."""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class ProbeResult:
    """Outcome of one dependency check."""

    name: str
    ok: bool
    detail: str


class HealthProbe(ABC):
    """Checks one dependency. Implementations must report failure, not raise."""

    @abstractmethod
    def check(self) -> ProbeResult: ...

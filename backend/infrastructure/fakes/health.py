"""Fake health probe for tests."""

from ports.health import HealthProbe, ProbeResult


class FakeHealthProbe(HealthProbe):
    """Returns a fixed result without touching any real dependency."""

    def __init__(self, name: str = "database", ok: bool = True, detail: str = "fake") -> None:
        self._result = ProbeResult(name, ok=ok, detail=detail)

    def check(self) -> ProbeResult:
        return self._result

"""Port for stored area briefings."""

from abc import ABC, abstractmethod

from domain.briefing import AreaBriefing


class BriefingRepository(ABC):
    @abstractmethod
    def get(self, area_id: int) -> AreaBriefing | None:
        """The stored briefing of an area, if one was ever written."""

    @abstractmethod
    def save(self, briefing: AreaBriefing) -> None:
        """Store a briefing in place of the area's previous one."""

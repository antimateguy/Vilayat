"""Port for a city's rail and tram lines."""

from abc import ABC, abstractmethod
from collections.abc import Sequence

from domain.transit import TransitLine


class TransitNetworkSource(ABC):
    @abstractmethod
    def lines(self, city_id: str) -> Sequence[TransitLine]:
        """The city's U-Bahn, S-Bahn and tram lines; empty when none are prepared."""

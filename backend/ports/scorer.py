"""Port for one soft preference of the ranking (Strategy pattern)."""

from abc import ABC, abstractmethod

from domain.area import AreaFacts
from domain.score import ScoreComponent


class Scorer(ABC):
    """Rates an area on one preference, such as rent or amenities.

    The ranking service holds a list of scorers and combines their results with
    user-set weights. Adding a preference means adding a Scorer class; the
    ranking service does not change.
    """

    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def score(self, facts: AreaFacts) -> ScoreComponent: ...

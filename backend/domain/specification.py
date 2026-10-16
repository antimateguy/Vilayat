"""Hard constraints as small composable objects (Specification pattern).

Each specification answers one question about an area, such as "is the commute
within the limit?". The answer has three possible values, because the figure it
needs may be missing: an area with an UNKNOWN rent neither passes nor fails a
rent ceiling. Specifications combine with `&` and `|`.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from domain.area import AreaFacts
from domain.unknown import UNKNOWN


class Verdict(StrEnum):
    SATISFIED = "satisfied"
    VIOLATED = "violated"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class Evaluation:
    """A verdict with the sentences that explain it.

    `violations` say which limits the area breaks; `missing` say which figures
    could not be checked. Both are worded for the person searching.
    """

    verdict: Verdict
    violations: tuple[str, ...] = ()
    missing: tuple[str, ...] = ()


SATISFIED = Evaluation(Verdict.SATISFIED)


class Specification(ABC):
    @abstractmethod
    def evaluate(self, facts: AreaFacts) -> Evaluation: ...

    def __and__(self, other: "Specification") -> "Specification":
        return AllOf((self, other))

    def __or__(self, other: "Specification") -> "Specification":
        return AnyOf((self, other))


@dataclass(frozen=True)
class AllOf(Specification):
    """Every part must hold. One violated part is enough to violate the whole;
    otherwise one unknown part makes the whole unknown."""

    parts: tuple[Specification, ...]

    def evaluate(self, facts: AreaFacts) -> Evaluation:
        evaluations = [part.evaluate(facts) for part in self.parts]
        violations = tuple(text for e in evaluations for text in e.violations)
        missing = tuple(text for e in evaluations for text in e.missing)
        if any(e.verdict is Verdict.VIOLATED for e in evaluations):
            verdict = Verdict.VIOLATED
        elif any(e.verdict is Verdict.UNKNOWN for e in evaluations):
            verdict = Verdict.UNKNOWN
        else:
            verdict = Verdict.SATISFIED
        return Evaluation(verdict, violations, missing)


@dataclass(frozen=True)
class AnyOf(Specification):
    """One part holding is enough. If none holds but one is unknown, the whole is unknown."""

    parts: tuple[Specification, ...]

    def evaluate(self, facts: AreaFacts) -> Evaluation:
        evaluations = [part.evaluate(facts) for part in self.parts]
        if any(e.verdict is Verdict.SATISFIED for e in evaluations):
            return SATISFIED
        violations = tuple(text for e in evaluations for text in e.violations)
        missing = tuple(text for e in evaluations for text in e.missing)
        if any(e.verdict is Verdict.UNKNOWN for e in evaluations):
            return Evaluation(Verdict.UNKNOWN, violations, missing)
        return Evaluation(Verdict.VIOLATED, violations, missing)


@dataclass(frozen=True)
class Anything(Specification):
    """Holds for every area. The neutral element when there is nothing to check."""

    def evaluate(self, facts: AreaFacts) -> Evaluation:
        return SATISFIED


@dataclass(frozen=True)
class MaxCommute(Specification):
    minutes: int

    def evaluate(self, facts: AreaFacts) -> Evaluation:
        if facts.commute_minutes is UNKNOWN:
            return Evaluation(
                Verdict.UNKNOWN, missing=("No travel time to the campus is stored for this area.",)
            )
        if facts.commute_minutes > self.minutes:
            text = f"Commute of {facts.commute_minutes} min is over your {self.minutes} min limit."
            return Evaluation(Verdict.VIOLATED, violations=(text,))
        return SATISFIED


@dataclass(frozen=True)
class MaxRent(Specification):
    eur: Decimal

    def evaluate(self, facts: AreaFacts) -> Evaluation:
        if facts.rent is UNKNOWN:
            return Evaluation(Verdict.UNKNOWN, missing=("No rent figure is known for this area.",))
        if facts.rent.monthly_eur > self.eur:
            rent = f"{facts.rent.monthly_eur:.0f} EUR"
            text = f"Rent of {rent} is over your {self.eur:.0f} EUR ceiling."
            return Evaluation(Verdict.VIOLATED, violations=(text,))
        return SATISFIED


@dataclass(frozen=True)
class MinJobAccess(Specification):
    score: float

    def evaluate(self, facts: AreaFacts) -> Evaluation:
        if facts.job_access is UNKNOWN:
            return Evaluation(
                Verdict.UNKNOWN, missing=("Job access has not been computed for this area.",)
            )
        if facts.job_access.score < self.score:
            return Evaluation(
                Verdict.VIOLATED,
                violations=(
                    f"Job access of {facts.job_access.score:.2f} is below "
                    f"your minimum of {self.score:.2f}.",
                ),
            )
        return SATISFIED

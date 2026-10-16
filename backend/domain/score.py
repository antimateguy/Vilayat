"""Scores: how well an area fits the student's soft preferences."""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Final

from domain.unknown import Unknown

DEFAULT_WEIGHTS: Final[Mapping[str, float]] = MappingProxyType(
    {"commute": 0.35, "rent": 0.35, "amenities": 0.15, "job_access": 0.15}
)
"""How much each preference counts unless the student moves the sliders.
Keyed by scorer name."""

EMPHASISED_WEIGHT: Final = 0.5
"""The weight of a preference the student calls important: above every default."""


def adjusted_weights(important: Iterable[str], unimportant: Iterable[str]) -> dict[str, float]:
    """The default weights, changed for what a student stresses or dismisses.

    An important preference is raised to EMPHASISED_WEIGHT and an unimportant
    one is switched off. A preference named as both counts as important.
    """
    weights = dict(DEFAULT_WEIGHTS)
    for name in unimportant:
        weights[_known(name)] = 0.0
    for name in important:
        weights[_known(name)] = EMPHASISED_WEIGHT
    return weights


def _known(preference: str) -> str:
    if preference not in DEFAULT_WEIGHTS:
        raise ValueError(f"unknown preference: {preference}")
    return preference


@dataclass(frozen=True, slots=True)
class ScoreComponent:
    """One scorer's verdict on one area, with the reason shown to the user."""

    scorer: str
    value: float | Unknown
    """0 (worst) to 1 (best); UNKNOWN when the data the scorer needs is missing."""
    reason: str

    def __post_init__(self) -> None:
        if not isinstance(self.value, Unknown) and not 0 <= self.value <= 1:
            raise ValueError(f"score must be 0 to 1: {self.value}")


@dataclass(frozen=True, slots=True)
class Score:
    """The weighted total and what it was built from."""

    total: float
    """0 to 1."""
    components: tuple[ScoreComponent, ...]
    shares: Mapping[str, float]
    """The share of the total each component carried, by scorer name. A component
    with an UNKNOWN value carries nothing, and the others are scaled up so the
    shares still add up to 1."""

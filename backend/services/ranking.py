"""Ranking: combine the scorers' verdicts with the student's weights and explain the result."""

from collections.abc import Mapping, Sequence

from domain.area import AreaFacts
from domain.score import Score, ScoreComponent
from domain.search import RankedArea
from domain.unknown import UNKNOWN
from ports.scorer import Scorer
from services.errors import InvalidRequestError


class RankingService:
    """Knows nothing about rent or commute: it only combines whatever scorers it is given."""

    def rank(
        self,
        candidates: Sequence[AreaFacts],
        scorers: Sequence[Scorer],
        weights: Mapping[str, float],
    ) -> list[RankedArea]:
        """Best area first. Ties go to the shorter commute, then to the name."""
        self._check_weights(weights, scorers)
        scored = [(facts, self._score(facts, scorers, weights)) for facts in candidates]
        scored.sort(
            key=lambda pair: (-pair[1].total, self._commute_key(pair[0]), pair[0].area.name)
        )
        return [
            RankedArea(
                rank=position,
                facts=facts,
                score=score,
                reasons=self._reasons(score),
                trade_off=self._trade_off(score),
            )
            for position, (facts, score) in enumerate(scored, start=1)
        ]

    @staticmethod
    def _commute_key(facts: AreaFacts) -> tuple[bool, int]:
        """An unknown commute sorts after every known one."""
        minutes = facts.commute_minutes
        return (True, 0) if minutes is UNKNOWN else (False, minutes)

    @staticmethod
    def _check_weights(weights: Mapping[str, float], scorers: Sequence[Scorer]) -> None:
        names = {scorer.name for scorer in scorers}
        unknown = sorted(set(weights) - names)
        if unknown:
            raise InvalidRequestError(
                f"no such preference: {', '.join(unknown)} (known: {', '.join(sorted(names))})"
            )
        if any(weight < 0 for weight in weights.values()):
            raise InvalidRequestError("weights cannot be negative")
        if not any(weights.get(name, 0) > 0 for name in names):
            raise InvalidRequestError("at least one weight must be above zero")

    @staticmethod
    def _score(facts: AreaFacts, scorers: Sequence[Scorer], weights: Mapping[str, float]) -> Score:
        components = tuple(scorer.score(facts) for scorer in scorers)
        # A preference whose figure is missing cannot count. The remaining
        # weights are scaled up so they still add up to 1, instead of treating
        # the missing figure as a zero.
        counted = {
            component.scorer: weights.get(component.scorer, 0.0)
            for component in components
            if component.value is not UNKNOWN and weights.get(component.scorer, 0.0) > 0
        }
        weight_sum = sum(counted.values())
        shares = {name: weight / weight_sum for name, weight in counted.items()}
        total = sum(
            shares[component.scorer] * component.value
            for component in components
            if component.value is not UNKNOWN and component.scorer in shares
        )
        return Score(total=total, components=components, shares=shares)

    @staticmethod
    def _contribution(score: Score, component: ScoreComponent) -> float:
        if component.value is UNKNOWN:
            return -1.0
        return score.shares.get(component.scorer, 0.0) * component.value

    def _reasons(self, score: Score) -> tuple[str, ...]:
        """The preference that added most to the score comes first; unknown ones last."""
        ordered = sorted(
            score.components, key=lambda component: -self._contribution(score, component)
        )
        return tuple(component.reason for component in ordered)

    @staticmethod
    def _trade_off(score: Score) -> str:
        """The lowest-scoring preference among those that counted."""
        counted = [
            component
            for component in score.components
            if component.value is not UNKNOWN and component.scorer in score.shares
        ]
        if not counted:
            return "No trade-off can be named: the figures it would rest on are unknown."
        weakest = min(counted, key=lambda component: (component.value, component.scorer))
        label = weakest.scorer.replace("_", " ")
        return f"Weakest point is {label}: {weakest.reason}"

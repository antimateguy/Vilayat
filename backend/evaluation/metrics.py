"""The measures used in the evaluation. Plain functions over plain values."""

from collections.abc import Collection, Hashable, Sequence
from dataclasses import dataclass


def reciprocal_rank(ranked: Sequence[Hashable], relevant: Collection[Hashable]) -> float:
    """1 / position of the first relevant item (1 if it is first, 0.5 if second,
    ...), or 0 if none of the ranked items is relevant."""
    for position, item in enumerate(ranked, start=1):
        if item in relevant:
            return 1 / position
    return 0.0


def hit(ranked: Sequence[Hashable], relevant: Collection[Hashable], k: int) -> bool:
    """True if a relevant item is among the first k."""
    return any(item in relevant for item in ranked[:k])


@dataclass(frozen=True, slots=True)
class RetrievalScores:
    questions: int
    hit_at_1: float
    """Share of questions whose best match is a section that answers them."""
    hit_at_3: float
    mrr: float
    """Mean reciprocal rank: how high the first right section is, on average."""


def retrieval_scores(
    results: Sequence[tuple[Sequence[Hashable], Collection[Hashable]]],
) -> RetrievalScores:
    """Summarise (ranking, relevant items) pairs, one per question."""
    if not results:
        raise ValueError("no results to summarise")
    count = len(results)
    return RetrievalScores(
        questions=count,
        hit_at_1=sum(hit(ranked, relevant, 1) for ranked, relevant in results) / count,
        hit_at_3=sum(hit(ranked, relevant, 3) for ranked, relevant in results) / count,
        mrr=sum(reciprocal_rank(ranked, relevant) for ranked, relevant in results) / count,
    )


@dataclass(frozen=True, slots=True)
class GateScores:
    """How well a similarity threshold separates questions the documents cover
    from questions they do not."""

    threshold: float
    answerable_kept: float
    """Share of answerable questions that pass the threshold (should be high)."""
    unanswerable_stopped: float
    """Share of unanswerable questions stopped before any model call."""
    accuracy: float
    """Share of all questions the threshold decides correctly."""


def gate_scores(
    answerable: Sequence[float], unanswerable: Sequence[float], threshold: float
) -> GateScores:
    """Score a threshold given each question's best similarity."""
    if not answerable or not unanswerable:
        raise ValueError("both groups of questions are needed")
    kept = sum(score >= threshold for score in answerable)
    stopped = sum(score < threshold for score in unanswerable)
    return GateScores(
        threshold=threshold,
        answerable_kept=kept / len(answerable),
        unanswerable_stopped=stopped / len(unanswerable),
        accuracy=(kept + stopped) / (len(answerable) + len(unanswerable)),
    )


def share(flags: Sequence[bool]) -> float:
    """The share of true values; the accuracy of a list of right/wrong marks."""
    if not flags:
        raise ValueError("nothing to take a share of")
    return sum(flags) / len(flags)

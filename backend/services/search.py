"""Search: which areas work for this campus, rent and commute, and in what order."""

import dataclasses
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field

from domain.area import AreaFacts
from domain.city import Campus
from domain.constraints import Constraints
from domain.destination import Destination, DestinationKind
from domain.score import DEFAULT_WEIGHTS
from domain.search import (
    ExcludedArea,
    FullDayTravel,
    RankedArea,
    SearchResult,
    UncheckedArea,
)
from domain.specification import Verdict
from domain.travel import TimeWindow
from domain.unknown import UNKNOWN
from ports.catalog import CatalogRepository
from ports.commute import CommuteProvider
from ports.scorer import Scorer
from services.errors import InvalidRequestError, NotFoundError
from services.facts import AreaFactsCollector
from services.lookup import campus_and_city
from services.ranking import RankingService
from services.scorers import default_scorers
from services.timing import stage

ScorerFactory = Callable[[Constraints], Sequence[Scorer]]


@dataclass(frozen=True)
class SearchRequest:
    constraints: Constraints
    weights: Mapping[str, float] = field(default_factory=lambda: DEFAULT_WEIGHTS)
    employer_destination_id: int | None = None
    """An employer the student has pinned. It adds full-day travel to each result."""


class SearchService:
    """Orchestrates one search. Every decision in it is deterministic code: the
    constraints decide who is in, the scorers and weights decide the order."""

    def __init__(
        self,
        catalog: CatalogRepository,
        facts: AreaFactsCollector,
        commute: CommuteProvider,
        ranking: RankingService,
        scorers: ScorerFactory = default_scorers,
    ) -> None:
        self._catalog = catalog
        self._facts = facts
        self._commute = commute
        self._ranking = ranking
        self._scorers = scorers

    def search(self, request: SearchRequest) -> SearchResult:
        constraints = request.constraints
        with stage("catalog"):
            campus, city_id = campus_and_city(self._catalog, constraints.campus_id)
            employer = self._employer(request.employer_destination_id, city_id)

        specification = constraints.to_specification()
        matches: list[AreaFacts] = []
        excluded: list[ExcludedArea] = []
        unchecked: list[UncheckedArea] = []
        with stage("facts"):
            all_facts = self._facts.collect(city_id, campus.destination_id)
        with stage("constraints"):
            for facts in all_facts:
                evaluation = specification.evaluate(facts)
                if evaluation.verdict is Verdict.SATISFIED:
                    matches.append(facts)
                elif evaluation.verdict is Verdict.VIOLATED:
                    excluded.append(ExcludedArea(facts, evaluation.violations))
                else:
                    unchecked.append(UncheckedArea(facts, evaluation.missing))

        with stage("ranking"):
            ranked = self._ranking.rank(matches, self._scorers(constraints), request.weights)
        if employer is not None:
            with stage("full_day"):
                ranked = self._with_full_day(ranked, campus, employer)

        return SearchResult(
            city_id=city_id,
            campus=campus,
            ranked=tuple(ranked),
            excluded=tuple(sorted(excluded, key=lambda item: item.facts.area.name)),
            unchecked=tuple(sorted(unchecked, key=lambda item: item.facts.area.name)),
        )

    def _employer(self, destination_id: int | None, city_id: str) -> Destination | None:
        if destination_id is None:
            return None
        employer = self._catalog.get_destination(destination_id)
        if employer is None or employer.kind is not DestinationKind.EMPLOYER:
            raise NotFoundError(f"no employer with id {destination_id}")
        if employer.city_id != city_id:
            raise InvalidRequestError(
                f"{employer.name} is in {employer.city_id}, the campus is in {city_id}"
            )
        return employer

    def _with_full_day(
        self, ranked: Sequence[RankedArea], campus: Campus, employer: Destination
    ) -> list[RankedArea]:
        """Attach home, campus, job, home to every result. The order does not change."""
        evening = TimeWindow.WEEKDAY_EVENING
        campus_to_job = self._commute.minutes_between(campus.destination_id, employer.id, evening)
        job_to_home = self._commute.minutes_by_area(employer.id, evening)
        campus_to_home = self._commute.minutes_by_area(campus.destination_id, evening)
        return [
            dataclasses.replace(
                item,
                full_day=FullDayTravel(
                    employer=employer,
                    home_to_campus=item.facts.commute_minutes,
                    campus_to_job=campus_to_job,
                    job_to_home=job_to_home.get(item.facts.area.id, UNKNOWN),
                    campus_to_home=campus_to_home.get(item.facts.area.id, UNKNOWN),
                ),
            )
            for item in ranked
        ]

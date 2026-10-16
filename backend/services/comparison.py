"""Comparison: with this rent and commute limit, how many areas work around each university?"""

from decimal import Decimal

from domain.search import CampusFeasibility, CityComparison, UniversityFeasibility
from domain.specification import MaxCommute, MaxRent, Verdict
from ports.areas import AreaRepository
from ports.catalog import CatalogRepository
from services.facts import AreaFactsCollector
from services.lookup import require_city
from services.timing import stage


class ComparisonService:
    def __init__(
        self, catalog: CatalogRepository, areas: AreaRepository, facts: AreaFactsCollector
    ) -> None:
        self._catalog = catalog
        self._areas = areas
        self._facts = facts

    def compare(
        self, city_id: str, max_rent_eur: Decimal, max_commute_minutes: int
    ) -> CityComparison:
        require_city(self._catalog, city_id)

        # The same specification objects the search uses, so "feasible" means
        # exactly what it means there.
        specification = MaxCommute(max_commute_minutes) & MaxRent(max_rent_eur)
        universities = self._catalog.list_universities(city_id)
        campuses = {
            university.id: self._catalog.list_campuses(university.id) for university in universities
        }
        with stage("facts"):
            facts_by_destination = self._facts.collect_for(
                city_id,
                [campus.destination_id for group in campuses.values() for campus in group],
            )

        result = []
        for university in universities:
            rows = []
            for campus in campuses[university.id]:
                verdicts = [
                    (facts.area.id, specification.evaluate(facts).verdict)
                    for facts in facts_by_destination[campus.destination_id]
                ]
                rows.append(
                    CampusFeasibility(
                        campus=campus,
                        feasible_area_ids=frozenset(
                            area_id for area_id, v in verdicts if v is Verdict.SATISFIED
                        ),
                        excluded=sum(v is Verdict.VIOLATED for _, v in verdicts),
                        unchecked=sum(v is Verdict.UNKNOWN for _, v in verdicts),
                    )
                )
            result.append(UniversityFeasibility(university=university, campuses=tuple(rows)))

        return CityComparison(
            city_id=city_id,
            total_areas=len(self._areas.list_by_city(city_id)),
            universities=tuple(result),
        )

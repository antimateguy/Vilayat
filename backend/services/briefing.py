"""Area briefings: a few sentences that put an area's figures into words.

The engine computes the figures; the model only rewords them. Briefings are
written offline by a job and stored, so reading one never waits for a model.

Two guarantees:

- A text is stored only if it passes the checks in `_problem_with`: it names
  its area exactly, and it contains no figure and no name that was not in its
  input (see services.grounding).
- A stored briefing is shown only while the figures it was written from are
  still the area's current figures and its text still passes those checks.
  After new data is loaded, old briefings disappear until the job is run again.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime

from domain.area import Area, AreaFacts
from domain.briefing import NOT_KNOWN, AreaBriefing, BriefingFacts
from domain.place import PlaceCategory
from domain.unknown import Unknown
from ports.areas import AreaRepository
from ports.briefings import BriefingRepository
from ports.catalog import CatalogRepository
from ports.llm import LLMClient, LLMUnavailableError
from services.errors import NotFoundError
from services.facts import AreaFactsCollector
from services.grounding import unsupported_names, unsupported_numbers
from services.lookup import require_city
from services.timing import stage

MAX_BRIEFING_WORDS = 90
MAX_ATTEMPTS = 2
"""A rejected text is tried once more, with the reason for the rejection."""
_ALLOWED_CAPITALS = ("EUR",)

_INSTRUCTIONS = """\
Write a short briefing about one neighbourhood for a student who is choosing
where to live. Use only the facts below.

Rules:
- Two or three plain sentences, at most 70 words, in English. No headings and no lists.
- Name the neighbourhood, spelt exactly as in the facts.
- Write natural sentences. Use the singular for a count of 1.
- Cover the rent, the everyday amenities and the job access.
- Copy every figure exactly as given. Do not add, round, convert or calculate figures.
- Where a fact is "unknown", say that it is not known. Never estimate it.
- Say nothing that is not in the facts: no landmarks, no transport lines, no
  atmosphere, no advice.
- The businesses counted are cafes, restaurants, bars, shops and supermarkets,
  which typically hire students. They are not job vacancies; never call them that.

Facts:
"""


def briefing_facts(city_name: str, all_facts: Sequence[AreaFacts]) -> dict[int, BriefingFacts]:
    """The figures a briefing is written from, for every area of one city.

    Only figures that do not depend on a campus are used, so one briefing
    serves every student. The comparisons with the rest of the city are
    computed here, so the model never has to compare anything itself.
    """
    rents = sorted(
        facts.rent.monthly_eur for facts in all_facts if not isinstance(facts.rent, Unknown)
    )
    result: dict[int, BriefingFacts] = {}
    for facts in all_facts:
        entry: dict[str, str | int | bool] = {"neighbourhood": facts.area.name, "city": city_name}

        if isinstance(facts.rent, Unknown):
            entry["typical_monthly_rent_eur"] = NOT_KNOWN
        else:
            dearer = sum(1 for rent in rents if rent > facts.rent.monthly_eur)
            entry["typical_monthly_rent_eur"] = round(facts.rent.monthly_eur)
            entry["percent_of_the_citys_areas_with_higher_rent"] = round(100 * dearer / len(rents))
            entry["rent_figure_is_a_placeholder"] = facts.rent.is_sample

        if isinstance(facts.amenity_counts, Unknown):
            entry["everyday_amenities"] = NOT_KNOWN
        else:
            for category, label in _AMENITY_LABELS.items():
                entry[label] = facts.amenity_counts.get(category, 0)

        if isinstance(facts.job_access, Unknown):
            entry["job_access"] = NOT_KNOWN
        else:
            entry["businesses_that_typically_hire_students_within_about_2_km"] = (
                facts.job_access.places_nearby
            )
            entry["percent_of_the_city_with_fewer_such_businesses_nearby"] = round(
                100 * facts.job_access.score
            )
        result[facts.area.id] = entry
    return result


_AMENITY_LABELS = {
    PlaceCategory.SUPERMARKET: "supermarkets",
    PlaceCategory.CAFE: "cafes",
    PlaceCategory.LIBRARY: "libraries",
    PlaceCategory.GYM: "gyms",
}


# How each fact is worded for the model. Plain wording here gives plainer
# sentences back than the key names would.
_WORDING = {
    "neighbourhood": "neighbourhood",
    "city": "city",
    "typical_monthly_rent_eur": "typical monthly rent in EUR",
    "percent_of_the_citys_areas_with_higher_rent": (
        "percent of the city's areas that have a higher rent"
    ),
    "everyday_amenities": "everyday amenities",
    "supermarkets": "supermarkets",
    "cafes": "cafes",
    "libraries": "libraries",
    "gyms": "gyms",
    "job_access": "job access",
    "businesses_that_typically_hire_students_within_about_2_km": (
        "businesses that typically hire students within about 2 km"
    ),
    "percent_of_the_city_with_fewer_such_businesses_nearby": (
        "percent of the city that has fewer such businesses nearby"
    ),
}


# Stored with the briefing, but not given to the model: the page marks a
# placeholder rent with an asterisk, so the text need not repeat it as a warning.
_NOT_FOR_THE_MODEL = frozenset({"rent_figure_is_a_placeholder"})


def _facts_text(facts: BriefingFacts) -> str:
    return "\n".join(
        f"{_WORDING.get(key, key.replace('_', ' '))}: {_shown(value)}"
        for key, value in facts.items()
        if key not in _NOT_FOR_THE_MODEL
    )


def _shown(value: str | int | bool) -> str:
    if isinstance(value, bool):
        return "yes" if value else "no"
    return str(value)


class _CityFigures:
    """Shared by the reader and the writer: the current figures of a city."""

    def __init__(self, catalog: CatalogRepository, collector: AreaFactsCollector) -> None:
        self._catalog = catalog
        self._collector = collector

    def current(self, city_id: str) -> dict[int, BriefingFacts]:
        city = next((c for c in self._catalog.list_cities() if c.id == city_id), None)
        if city is None:
            raise NotFoundError(f"no city with id {city_id}")
        with stage("facts"):
            return briefing_facts(city.name, self._collector.collect(city_id, None))


class BriefingReader:
    """What the API uses. It reads; it never calls a model."""

    def __init__(
        self,
        catalog: CatalogRepository,
        areas: AreaRepository,
        collector: AreaFactsCollector,
        briefings: BriefingRepository,
    ) -> None:
        self._areas = areas
        self._figures = _CityFigures(catalog, collector)
        self._briefings = briefings

    def get(self, area_id: int) -> tuple[Area, AreaBriefing | None]:
        """The area and its briefing; None if there is none that is still current."""
        area = self._areas.get(area_id)
        if area is None:
            raise NotFoundError(f"no area with id {area_id}")
        with stage("briefing"):
            stored = self._briefings.get(area_id)
        if stored is None:
            return area, None
        current = self._figures.current(area.city_id).get(area_id)
        return area, stored if current and _is_current(stored, current) else None


@dataclass(slots=True)
class BriefingReport:
    written: list[str] = field(default_factory=list)
    unchanged: list[str] = field(default_factory=list)
    rejected: dict[str, str] = field(default_factory=dict)
    """Area name -> why the model's text was not stored."""
    not_reached: list[str] = field(default_factory=list)
    """Areas left for the next run: over the limit, or the model stopped answering."""
    stopped_because: str | None = None
    """Set when the model stopped answering part-way through."""


class BriefingWriter:
    """What the offline job uses."""

    def __init__(
        self,
        llm: LLMClient,
        catalog: CatalogRepository,
        collector: AreaFactsCollector,
        briefings: BriefingRepository,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._llm = llm
        self._catalog = catalog
        self._figures = _CityFigures(catalog, collector)
        self._briefings = briefings
        self._clock = clock

    def refresh_city(
        self,
        city_id: str,
        *,
        force: bool = False,
        written_before: datetime | None = None,
        limit: int | None = None,
        after_each: Callable[[], None] = lambda: None,
    ) -> BriefingReport:
        """Write a briefing for every area whose figures changed since its last one.

        `force` rewrites every briefing; `written_before` rewrites those written
        before that moment, so a rewrite that stopped half-way can carry on
        without redoing the finished ones (after a change to the instructions).
        `limit` caps the number of areas attempted in this run. `after_each` runs
        after every stored briefing; the job uses it to commit and to pause.
        If the model stops answering, the run ends and reports what is left;
        running again later carries on from there.
        """
        require_city(self._catalog, city_id)
        report = BriefingReport()
        todo: list[tuple[int, BriefingFacts]] = []
        for area_id, facts in self._figures.current(city_id).items():
            stored = self._briefings.get(area_id)
            outdated = written_before is not None and (
                stored is None or stored.generated_at < written_before
            )
            if not force and not outdated and stored is not None and _is_current(stored, facts):
                report.unchanged.append(_name(facts))
            else:
                todo.append((area_id, facts))

        attempted = todo if limit is None else todo[:limit]
        left = todo[len(attempted) :]
        for position, (area_id, facts) in enumerate(attempted):
            try:
                text, problem = self._write(facts)
            except LLMUnavailableError as error:
                report.stopped_because = str(error)
                left = todo[position:]
                break
            if text is None:
                report.rejected[_name(facts)] = problem or "rejected"
                continue
            self._briefings.save(
                AreaBriefing(
                    area_id=area_id,
                    content=text,
                    facts=facts,
                    model=self._llm.model_name,
                    generated_at=self._clock(),
                )
            )
            report.written.append(_name(facts))
            after_each()
        report.not_reached = [_name(facts) for _, facts in left]
        return report

    def _write(self, facts: BriefingFacts) -> tuple[str | None, str | None]:
        """(text, None) for a text that passes the checks, or (None, the last problem)."""
        prompt = _INSTRUCTIONS + _facts_text(facts)
        problem: str | None = None
        for _ in range(MAX_ATTEMPTS):
            retry = (
                f"\n\nYour previous text was rejected: {problem}. "
                "Write it again and follow every rule."
                if problem
                else ""
            )
            text = _one_paragraph(self._llm.generate_text(prompt + retry))
            problem = _problem_with(text, facts)
            if problem is None:
                return text, None
        return None, problem


def _name(facts: BriefingFacts) -> str:
    return str(facts["neighbourhood"])


def _one_paragraph(text: str) -> str:
    return " ".join(text.split())


def _problem_with(text: str, facts: BriefingFacts) -> str | None:
    """Why a text must not be stored, or None if it passes."""
    words = len(text.split())
    if words > MAX_BRIEFING_WORDS:
        return f"too long ({words} words)"
    if _name(facts) not in text:
        return f"the neighbourhood's name, {_name(facts)}, is missing or misspelt"
    source = [_facts_text(facts)]
    figures = unsupported_numbers(text, source)
    if figures:
        return f"figures that are not in the facts: {', '.join(sorted(figures))}"
    names = unsupported_names(text, source, _ALLOWED_CAPITALS)
    if names:
        return f"names that are not in the facts: {', '.join(sorted(names))}"
    return None


def _is_current(stored: AreaBriefing, facts: BriefingFacts) -> bool:
    """True while a stored briefing may still be shown for these figures."""
    return dict(stored.facts) == dict(facts) and _problem_with(stored.content, facts) is None

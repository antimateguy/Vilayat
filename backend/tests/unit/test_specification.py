"""Hard constraints as specifications: three possible verdicts, and how they combine."""

from decimal import Decimal

import pytest

from domain.area import Area, AreaFacts
from domain.constraints import Constraints
from domain.place import JobAccess
from domain.specification import (
    AllOf,
    Anything,
    MaxCommute,
    MaxRent,
    MinJobAccess,
    Verdict,
)
from domain.unknown import UNKNOWN, Unknown
from tests.unit.engine_world import rent

SATISFIED, VIOLATED, NOT_KNOWN = Verdict.SATISFIED, Verdict.VIOLATED, Verdict.UNKNOWN


def facts(
    *,
    rent_eur: str | None = "600",
    commute: int | Unknown = 30,
    job_score: float | None = 0.5,
) -> AreaFacts:
    return AreaFacts(
        area=Area(id=1, city_id="x", name="Area"),
        cell_count=5,
        rent=UNKNOWN if rent_eur is None else rent(rent_eur),
        commute_minutes=commute,
        amenity_counts={},
        job_access=UNKNOWN if job_score is None else JobAccess(100, job_score),
    )


@pytest.mark.parametrize(
    ("minutes", "verdict"), [(30, SATISFIED), (40, SATISFIED), (41, VIOLATED), (UNKNOWN, NOT_KNOWN)]
)
def test_max_commute(minutes: int | Unknown, verdict: Verdict) -> None:
    assert MaxCommute(40).evaluate(facts(commute=minutes)).verdict is verdict


@pytest.mark.parametrize(
    ("eur", "verdict"),
    [("650", SATISFIED), ("700", SATISFIED), ("700.01", VIOLATED), (None, NOT_KNOWN)],
)
def test_max_rent(eur: str | None, verdict: Verdict) -> None:
    assert MaxRent(Decimal("700")).evaluate(facts(rent_eur=eur)).verdict is verdict


@pytest.mark.parametrize(
    ("score", "verdict"), [(0.6, SATISFIED), (0.5, SATISFIED), (0.49, VIOLATED), (None, NOT_KNOWN)]
)
def test_min_job_access(score: float | None, verdict: Verdict) -> None:
    assert MinJobAccess(0.5).evaluate(facts(job_score=score)).verdict is verdict


def test_a_violation_says_what_was_found_and_what_the_limit_is() -> None:
    evaluation = (MaxCommute(40) & MaxRent(Decimal("700"))).evaluate(
        facts(commute=52, rent_eur="760")
    )

    assert evaluation.violations == (
        "Commute of 52 min is over your 40 min limit.",
        "Rent of 760 EUR is over your 700 EUR ceiling.",
    )
    assert evaluation.missing == ()


def test_all_of_is_violated_as_soon_as_one_part_is_even_if_another_is_unknown() -> None:
    evaluation = (MaxCommute(40) & MaxRent(Decimal("700"))).evaluate(
        facts(commute=UNKNOWN, rent_eur="900")
    )

    # The area is out whatever the commute turns out to be.
    assert evaluation.verdict is VIOLATED
    assert evaluation.violations == ("Rent of 900 EUR is over your 700 EUR ceiling.",)
    assert evaluation.missing == ("No travel time to the campus is stored for this area.",)


def test_all_of_is_unknown_when_nothing_is_violated_but_a_figure_is_missing() -> None:
    evaluation = (MaxCommute(40) & MaxRent(Decimal("700"))).evaluate(facts(rent_eur=None))

    assert evaluation.verdict is NOT_KNOWN
    assert evaluation.missing == ("No rent figure is known for this area.",)


def test_any_of_holds_when_one_part_does_whatever_the_others_say() -> None:
    cheap_or_close = MaxRent(Decimal("500")) | MaxCommute(15)

    assert cheap_or_close.evaluate(facts(rent_eur="450", commute=60)).verdict is SATISFIED
    assert cheap_or_close.evaluate(facts(rent_eur=None, commute=10)).verdict is SATISFIED
    assert cheap_or_close.evaluate(facts(rent_eur="600", commute=60)).verdict is VIOLATED
    assert cheap_or_close.evaluate(facts(rent_eur=None, commute=60)).verdict is NOT_KNOWN


def test_specifications_nest() -> None:
    affordable = MaxRent(Decimal("700"))
    reachable_or_good_for_jobs = MaxCommute(20) | MinJobAccess(0.8)
    specification = affordable & reachable_or_good_for_jobs

    assert specification.evaluate(facts(commute=45, job_score=0.9)).verdict is SATISFIED
    assert specification.evaluate(facts(commute=45, job_score=0.3)).verdict is VIOLATED


def test_nothing_to_check_holds_for_every_area() -> None:
    assert Anything().evaluate(facts(rent_eur=None, commute=UNKNOWN)).verdict is SATISFIED
    assert AllOf(()).evaluate(facts()).verdict is SATISFIED


def test_constraints_become_one_specification() -> None:
    plain = Constraints(campus_id=1, max_commute_minutes=40, max_rent_eur=Decimal("700"))
    with_jobs = Constraints(1, 40, Decimal("700"), min_job_access=0.6)

    area = facts(commute=30, rent_eur="650", job_score=0.5)

    assert plain.to_specification().evaluate(area).verdict is SATISFIED
    assert with_jobs.to_specification().evaluate(area).verdict is VIOLATED

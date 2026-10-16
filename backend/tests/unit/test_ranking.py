"""Ranking: weights decide the order, and every result explains itself."""

from collections.abc import Sequence
from decimal import Decimal

import pytest

from domain.area import Area, AreaFacts
from domain.constraints import Constraints
from domain.place import JobAccess, PlaceCategory
from domain.score import DEFAULT_WEIGHTS, ScoreComponent
from domain.unknown import UNKNOWN, Unknown
from ports.scorer import Scorer
from services.errors import InvalidRequestError
from services.ranking import RankingService
from services.scorers import default_scorers
from tests.unit.engine_world import rent

CONSTRAINTS = Constraints(campus_id=1, max_commute_minutes=40, max_rent_eur=Decimal("700"))
SCORERS = default_scorers(CONSTRAINTS)


def area(
    name: str,
    *,
    rent_eur: str,
    commute: int,
    cells: int,
    amenities: dict[PlaceCategory, int] | Unknown,
    job_score: float | None,
) -> AreaFacts:
    return AreaFacts(
        area=Area(id=hash(name) % 1000, city_id="x", name=name),
        cell_count=cells,
        rent=rent(rent_eur),
        commute_minutes=commute,
        amenity_counts=amenities,
        job_access=UNKNOWN if job_score is None else JobAccess(100, job_score),
    )


# Close, lively and expensive; in between; cheap, far and quiet.
ALTSTADT = area(
    "Altstadt",
    rent_eur="680",
    commute=10,
    cells=4,
    amenities={PlaceCategory.CAFE: 20, PlaceCategory.SUPERMARKET: 6, PlaceCategory.GYM: 4},
    job_score=0.95,
)
NORDEND = area(
    "Nordend",
    rent_eur="600",
    commute=25,
    cells=8,
    amenities={PlaceCategory.CAFE: 4, PlaceCategory.SUPERMARKET: 4},
    job_score=0.6,
)
OSTPARK = area(
    "Ostpark",
    rent_eur="450",
    commute=38,
    cells=10,
    amenities={PlaceCategory.SUPERMARKET: 1},
    job_score=0.2,
)
AREAS = [OSTPARK, ALTSTADT, NORDEND]


def names(weights: dict[str, float]) -> list[str]:
    return [item.facts.area.name for item in RankingService().rank(AREAS, SCORERS, weights)]


def test_default_weights_put_the_balanced_central_area_first() -> None:
    ranked = RankingService().rank(AREAS, SCORERS, DEFAULT_WEIGHTS)

    assert [(item.rank, item.facts.area.name) for item in ranked] == [
        (1, "Altstadt"),
        (2, "Nordend"),
        (3, "Ostpark"),
    ]
    # Altstadt: 0.35 x 0.75 commute + 0.35 x 0.057 rent + 0.15 x 0.605 amenities + 0.15 x 0.95 jobs.
    assert ranked[0].score.total == pytest.approx(0.5157, abs=1e-3)
    assert ranked[0].score.shares == pytest.approx(DEFAULT_WEIGHTS)
    assert all(0 <= item.score.total <= 1 for item in ranked)


def test_changing_the_weights_changes_the_order() -> None:
    assert names({"rent": 1.0}) == ["Ostpark", "Nordend", "Altstadt"]
    assert names({"commute": 1.0}) == ["Altstadt", "Nordend", "Ostpark"]
    assert names({"rent": 0.9, "job_access": 0.1}) == ["Ostpark", "Nordend", "Altstadt"]


def test_only_the_proportions_of_the_weights_matter() -> None:
    service = RankingService()
    as_shares = service.rank(AREAS, SCORERS, {"commute": 0.5, "rent": 0.5})
    as_slider_values = service.rank(AREAS, SCORERS, {"commute": 70, "rent": 70})

    assert [i.score.total for i in as_shares] == pytest.approx(
        [i.score.total for i in as_slider_values]
    )
    assert as_slider_values[0].score.shares == {"commute": 0.5, "rent": 0.5}


def test_reasons_are_ordered_by_what_helped_the_score_most() -> None:
    (altstadt,) = RankingService().rank([ALTSTADT], SCORERS, DEFAULT_WEIGHTS)

    # Contributions: commute 0.26, jobs 0.14, amenities 0.09, rent 0.02.
    assert [reason.split()[0] for reason in altstadt.reasons] == ["10", "About", "30", "Rent"]
    assert altstadt.reasons[0] == (
        "10 min to campus by public transport, 30 min under your 40 min limit."
    )


def test_the_trade_off_is_the_weakest_preference_that_counted() -> None:
    by_name = {
        item.facts.area.name: item
        for item in RankingService().rank(AREAS, SCORERS, DEFAULT_WEIGHTS)
    }

    assert by_name["Altstadt"].trade_off.startswith("Weakest point is rent: Rent about 680 EUR")
    assert by_name["Ostpark"].trade_off.startswith("Weakest point is amenities: 1 everyday")
    # With amenities switched off, Ostpark's weakest remaining point is its commute.
    (ostpark,) = RankingService().rank(
        [OSTPARK], SCORERS, {"commute": 0.5, "rent": 0.3, "job_access": 0.2}
    )
    assert ostpark.trade_off.startswith("Weakest point is commute: 38 min to campus")


def test_an_unknown_figure_is_left_out_and_the_other_weights_are_scaled_up() -> None:
    no_places = area(
        "Neuland", rent_eur="600", commute=25, cells=8, amenities=UNKNOWN, job_score=None
    )

    (ranked,) = RankingService().rank([no_places], SCORERS, DEFAULT_WEIGHTS)

    # Commute and rent each had 0.35 of 0.70 that could be counted.
    assert ranked.score.shares == pytest.approx({"commute": 0.5, "rent": 0.5})
    assert ranked.score.total == pytest.approx(0.5 * 0.375 + 0.5 * (100 / 350))
    # The unknown figures are not hidden: they are listed last.
    assert ranked.reasons[-2:] == (
        "Everyday amenities are unknown.",
        "Part-time job access is unknown.",
    )
    assert "amenities" not in ranked.trade_off


def test_a_missing_figure_does_not_count_as_zero() -> None:
    known = area("Bekannt", rent_eur="600", commute=25, cells=8, amenities={}, job_score=0.0)
    unknown = area(
        "Unbekannt", rent_eur="600", commute=25, cells=8, amenities=UNKNOWN, job_score=None
    )

    by_name = {
        item.facts.area.name: item.score.total
        for item in RankingService().rank([known, unknown], SCORERS, DEFAULT_WEIGHTS)
    }

    # "Bekannt" really has no amenities and no jobs nearby, so it scores lower.
    assert by_name["Bekannt"] < by_name["Unbekannt"]


def test_ties_go_to_the_shorter_commute_then_to_the_name() -> None:
    twins = [
        area(name, rent_eur="600", commute=commute, cells=8, amenities={}, job_score=0.5)
        for name, commute in (("Zwilling", 20), ("Anders", 30), ("Bruder", 20))
    ]

    ranked = RankingService().rank(twins, SCORERS, {"rent": 1.0})

    assert [item.facts.area.name for item in ranked] == ["Bruder", "Zwilling", "Anders"]


@pytest.mark.parametrize(
    ("weights", "message"),
    [
        ({"comute": 1.0}, "no such preference: comute"),
        ({"commute": -0.1, "rent": 1.0}, "cannot be negative"),
        ({"commute": 0.0, "rent": 0.0}, "at least one weight"),
        ({}, "at least one weight"),
    ],
)
def test_impossible_weights_are_rejected(weights: dict[str, float], message: str) -> None:
    with pytest.raises(InvalidRequestError, match=message):
        RankingService().rank(AREAS, SCORERS, weights)


class QuietStreetScorer(Scorer):
    """A preference invented for this test: fewer bars is better."""

    @property
    def name(self) -> str:
        return "quiet"

    def score(self, facts: AreaFacts) -> ScoreComponent:
        counts = facts.amenity_counts
        cafes = 0 if counts is UNKNOWN else counts.get(PlaceCategory.CAFE, 0)
        return ScoreComponent(self.name, 1 / (1 + cafes), f"{cafes} cafes on the doorstep.")


def test_a_new_preference_is_a_new_scorer_class_and_nothing_else_changes() -> None:
    scorers: Sequence[Scorer] = [*SCORERS, QuietStreetScorer()]

    ranked = RankingService().rank(AREAS, scorers, {"quiet": 1.0})

    assert [item.facts.area.name for item in ranked] == ["Ostpark", "Nordend", "Altstadt"]
    assert ranked[0].trade_off == "Weakest point is quiet: 0 cafes on the doorstep."

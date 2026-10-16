"""Comparing what the intent service read from a sentence with what it should have."""

from domain.intent import SearchIntent
from domain.score import adjusted_weights
from evaluation.data import ExpectedIntent

FIELDS = ("city", "campus", "employer", "max_rent_eur", "max_commute_minutes", "weights")


def field_matches(found: SearchIntent, expected: ExpectedIntent) -> dict[str, bool]:
    """For each field, whether the service's result equals the label.

    A field counts as right when it is set to the expected value, and also when
    it is correctly left alone. Weights are compared after the same fixed rule
    the service applies to the stressed and dismissed preferences.
    """
    campus = (
        (found.university.short_name, found.campus.name)
        if found.university and found.campus
        else None
    )
    stressed = expected.important or expected.unimportant
    expected_weights = (
        adjusted_weights(expected.important, expected.unimportant) if stressed else None
    )
    return {
        "city": found.city_id == expected.city,
        "campus": campus == expected.campus,
        "employer": (found.employer.name if found.employer else None) == expected.employer,
        "max_rent_eur": found.max_rent_eur == expected.max_rent_eur,
        "max_commute_minutes": found.max_commute_minutes == expected.max_commute_minutes,
        "weights": (dict(found.weights) if found.weights else None) == expected_weights,
    }

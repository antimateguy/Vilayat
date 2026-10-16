"""Search settings read from a sentence a student typed."""

from collections.abc import Mapping
from dataclasses import dataclass

from domain.city import Campus, University
from domain.destination import Destination


@dataclass(frozen=True, slots=True)
class SearchIntent:
    """What a sentence asked for, as settings the search already understands.

    A field is None when the sentence did not mention it; the setting the
    student already has then stays as it is. Nothing here ranks or filters:
    the settings go into the same search as the ones set by hand.
    """

    city_id: str | None = None
    university: University | None = None
    campus: Campus | None = None
    max_rent_eur: int | None = None
    max_commute_minutes: int | None = None
    employer: Destination | None = None
    weights: Mapping[str, float] | None = None
    """All four preference weights, or None if the sentence stressed none."""
    notes: tuple[str, ...] = ()
    """What was assumed, and what was asked for but could not be used."""

    @property
    def is_empty(self) -> bool:
        """True when the sentence gave no setting at all."""
        return all(
            value is None
            for value in (
                self.city_id,
                self.campus,
                self.max_rent_eur,
                self.max_commute_minutes,
                self.employer,
                self.weights,
            )
        )

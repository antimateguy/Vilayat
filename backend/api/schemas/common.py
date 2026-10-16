"""Building blocks shared by the response schemas."""

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

from domain.unknown import UNKNOWN, Unknown

UnknownValue = Literal["UNKNOWN"]
"""How a missing figure appears in JSON: the string "UNKNOWN", never null and
never a made-up number. A client cannot mistake it for a real value."""


def or_unknown[T](value: T | Unknown) -> T | UnknownValue:
    return "UNKNOWN" if value is UNKNOWN else value


class AreaRef(BaseModel):
    id: int
    name: str = Field(examples=["Maxvorstadt"])


class CampusOut(BaseModel):
    id: int
    university_id: int
    name: str = Field(examples=["City Campus"])
    lat: float = Field(examples=[48.14888])
    lon: float = Field(examples=[11.56777])


class RentOut(BaseModel):
    """An area-level rent estimate. It is never returned without its source."""

    monthly_eur: float = Field(examples=[770.0])
    basis: str = Field(
        description="What the figure measures.", examples=["median asking rent, 1-room flat"]
    )
    source: str
    source_url: str | None
    as_of: date
    is_sample: bool = Field(description="True for placeholder data that is not a real rent.")


class JobAccessOut(BaseModel):
    """A proxy for where student-type employers cluster, not a count of vacancies."""

    score: float = Field(
        ge=0, le=1, description="Share of the city's cells with fewer such businesses nearby."
    )
    places_nearby: int = Field(
        description="Cafes, restaurants, bars, shops and supermarkets within about 2 km."
    )


class FactsOut(BaseModel):
    """What is known about an area. Any figure can be "UNKNOWN"."""

    cell_count: int = Field(description="Number of hexagon cells in the area (about 0.7 km² each).")
    rent: RentOut | UnknownValue
    commute_minutes: int | UnknownValue = Field(
        description="Public-transport minutes to the campus on a weekday morning."
    )
    amenities: dict[str, int] | UnknownValue = Field(
        description="Places per category: supermarket, cafe, library, gym.",
        examples=[{"supermarket": 31, "cafe": 46, "library": 8, "gym": 16}],
    )
    job_access: JobAccessOut | UnknownValue

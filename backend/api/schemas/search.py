"""Schemas for search, area detail and comparison."""

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from api.schemas.common import AreaRef, CampusOut, FactsOut, UnknownValue
from domain.constraints import MAX_COMMUTE_LIMIT_MINUTES, MAX_RENT_LIMIT_EUR
from domain.score import DEFAULT_WEIGHTS


class WeightsIn(BaseModel):
    """How much each preference counts. Only the proportions matter, so slider
    positions such as 70, 70, 30, 30 work as well as shares that add up to 1."""

    model_config = ConfigDict(extra="forbid")

    commute: float = Field(default=DEFAULT_WEIGHTS["commute"], ge=0)
    rent: float = Field(default=DEFAULT_WEIGHTS["rent"], ge=0)
    amenities: float = Field(default=DEFAULT_WEIGHTS["amenities"], ge=0)
    job_access: float = Field(default=DEFAULT_WEIGHTS["job_access"], ge=0)


class SearchIn(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "campus_id": 1,
                    "max_commute_minutes": 35,
                    "max_rent_eur": 800,
                    "weights": {
                        "commute": 0.35,
                        "rent": 0.35,
                        "amenities": 0.15,
                        "job_access": 0.15,
                    },
                    "employer_id": None,
                }
            ]
        },
    )

    campus_id: int
    max_commute_minutes: int = Field(ge=1, le=MAX_COMMUTE_LIMIT_MINUTES)
    max_rent_eur: Decimal = Field(gt=0, le=MAX_RENT_LIMIT_EUR)
    min_job_access: float | None = Field(
        default=None, ge=0, le=1, description="Optional floor on the job access score."
    )
    weights: WeightsIn = Field(default_factory=WeightsIn)
    employer_id: int | None = Field(
        default=None,
        description="An employer to pin. Adds full-day travel to each result; "
        "it never excludes an area or changes the order.",
    )


class ScoreComponentOut(BaseModel):
    name: str = Field(examples=["commute"])
    value: float | UnknownValue = Field(description="0 (worst) to 1 (best).")
    share: float = Field(
        description="The share of the total this preference carried. 0 if it was "
        "switched off or its figure is unknown."
    )
    reason: str = Field(
        examples=["29 min to campus by public transport, 6 min under your 35 min limit."]
    )


class ScoreOut(BaseModel):
    total: float = Field(ge=0, le=1)
    components: list[ScoreComponentOut]


class EmployerRef(BaseModel):
    id: int
    name: str


class FullDayOut(BaseModel):
    """Travel for a day with a job: home, campus, job, home."""

    employer: EmployerRef
    home_to_campus: int | UnknownValue = Field(description="Morning.")
    campus_to_job: int | UnknownValue = Field(description="Afternoon, from the evening timetable.")
    job_to_home: int | UnknownValue = Field(description="Evening.")
    campus_to_home: int | UnknownValue = Field(
        description="Evening; the way home on a day without the job."
    )
    total_minutes: int | UnknownValue = Field(description="The three legs of the day together.")
    extra_minutes: int | UnknownValue = Field(
        description="How much longer than home, campus, home."
    )


class RankedAreaOut(BaseModel):
    rank: int
    area: AreaRef
    facts: FactsOut
    score: ScoreOut
    reasons: list[str] = Field(description="One sentence per preference, the most helpful first.")
    trade_off: str = Field(description="The area's weakest point.")
    full_day: FullDayOut | None = Field(description="Present only when an employer is pinned.")


class ExcludedAreaOut(BaseModel):
    area: AreaRef
    facts: FactsOut
    violations: list[str] = Field(
        examples=[["Commute of 46 min is over your 35 min limit."]],
        description="Which limits the area breaks.",
    )


class UncheckedAreaOut(BaseModel):
    area: AreaRef
    facts: FactsOut
    missing: list[str] = Field(
        examples=[["No rent figure is known for this area."]],
        description="Which figures are missing, so a limit could not be checked.",
    )


class SearchOut(BaseModel):
    """Every area of the city, in exactly one of three groups."""

    city_id: str
    campus: CampusOut
    ranked: list[RankedAreaOut] = Field(description="Areas within every limit, best first.")
    excluded: list[ExcludedAreaOut] = Field(description="Areas that break a limit.")
    unchecked: list[UncheckedAreaOut] = Field(
        description="Areas that break no known limit but lack a figure needed to check one."
    )


class ListingPortalOut(BaseModel):
    name: str = Field(examples=["WG-Gesucht"])
    offers: str = Field(examples=["Rooms in shared flats"])
    url: str


class AreaDetailOut(BaseModel):
    area: AreaRef
    city_id: str
    campus: CampusOut | None
    facts: FactsOut
    return_minutes: int | UnknownValue = Field(
        description="Evening travel from the campus back to the area."
    )
    listing_portals: list[ListingPortalOut] = Field(
        description="City-level search pages of rental portals. This app lists no flats."
    )
    listing_hint: str = Field(examples=["Enter 'Maxvorstadt' as the district on the portal."])


class UniversityRef(BaseModel):
    id: int
    name: str
    short_name: str


class CampusFeasibilityOut(BaseModel):
    campus: CampusOut
    feasible: int = Field(description="Areas within both limits.")
    excluded: int
    unchecked: int = Field(description="Areas where a needed figure is missing.")
    feasible_area_ids: list[int]


class UniversityFeasibilityOut(BaseModel):
    university: UniversityRef
    feasible: int = Field(description="Areas within both limits for at least one campus.")
    campuses: list[CampusFeasibilityOut]


class ComparisonOut(BaseModel):
    city_id: str
    max_rent_eur: float
    max_commute_minutes: int
    total_areas: int
    universities: list[UniversityFeasibilityOut]

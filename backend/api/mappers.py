"""Turning domain objects into response schemas.

The domain knows nothing about JSON. This is the one place that decides how a
domain value looks on the wire, including that UNKNOWN becomes "UNKNOWN".
"""

from collections.abc import Sequence
from typing import Any

import h3

from api.schemas.catalog import DataSourceOut, EmployerOut, UniversityOut
from api.schemas.common import (
    AreaRef,
    CampusOut,
    FactsOut,
    JobAccessOut,
    RentOut,
    UnknownValue,
    or_unknown,
)
from api.schemas.layers import (
    AreaFeature,
    AreaProperties,
    CellFeature,
    CellProperties,
)
from api.schemas.search import (
    CampusFeasibilityOut,
    ComparisonOut,
    EmployerRef,
    ExcludedAreaOut,
    FullDayOut,
    RankedAreaOut,
    ScoreComponentOut,
    ScoreOut,
    SearchOut,
    UncheckedAreaOut,
    UniversityFeasibilityOut,
    UniversityRef,
)
from domain.area import Area, AreaFacts
from domain.city import Campus, University
from domain.destination import Destination
from domain.place import AMENITY_CATEGORIES
from domain.search import CityComparison, FullDayTravel, RankedArea, SearchResult
from domain.source import DataSource
from domain.unknown import UNKNOWN
from services.map_layers import AreaShape, CellValue


def area_ref(area: Area) -> AreaRef:
    return AreaRef(id=area.id, name=area.name)


def campus_out(campus: Campus) -> CampusOut:
    return CampusOut(
        id=campus.id,
        university_id=campus.university_id,
        name=campus.name,
        lat=campus.location.lat,
        lon=campus.location.lon,
    )


def university_out(university: University, campuses: Sequence[Campus]) -> UniversityOut:
    return UniversityOut(
        id=university.id,
        name=university.name,
        short_name=university.short_name,
        campuses=[campus_out(campus) for campus in campuses],
    )


def employer_out(employer: Destination) -> EmployerOut:
    return EmployerOut(
        id=employer.id,
        name=employer.name,
        lat=employer.location.lat,
        lon=employer.location.lon,
        is_sample=employer.is_sample,
    )


def source_out(source: DataSource) -> DataSourceOut:
    return DataSourceOut(
        used_for=source.used_for,
        name=source.name,
        publisher=source.publisher,
        licence=source.licence,
        as_of=or_unknown(source.as_of),
        is_sample=source.is_sample,
        url=source.url,
    )


def facts_out(facts: AreaFacts) -> FactsOut:
    rent: RentOut | UnknownValue = "UNKNOWN"
    if facts.rent is not UNKNOWN:
        rent = RentOut(
            monthly_eur=float(facts.rent.monthly_eur),
            basis=facts.rent.basis,
            source=facts.rent.source,
            source_url=facts.rent.source_url,
            as_of=facts.rent.as_of,
            is_sample=facts.rent.is_sample,
        )
    amenities: dict[str, int] | UnknownValue = "UNKNOWN"
    if facts.amenity_counts is not UNKNOWN:
        # Every category is listed, so a real zero is visible as 0.
        amenities = {
            category.value: facts.amenity_counts.get(category, 0)
            for category in sorted(AMENITY_CATEGORIES)
        }
    job_access: JobAccessOut | UnknownValue = "UNKNOWN"
    if facts.job_access is not UNKNOWN:
        job_access = JobAccessOut(
            score=facts.job_access.score, places_nearby=facts.job_access.places_nearby
        )
    return FactsOut(
        cell_count=facts.cell_count,
        rent=rent,
        commute_minutes=or_unknown(facts.commute_minutes),
        amenities=amenities,
        job_access=job_access,
    )


def full_day_out(full_day: FullDayTravel) -> FullDayOut:
    return FullDayOut(
        employer=EmployerRef(id=full_day.employer.id, name=full_day.employer.name),
        home_to_campus=or_unknown(full_day.home_to_campus),
        campus_to_job=or_unknown(full_day.campus_to_job),
        job_to_home=or_unknown(full_day.job_to_home),
        campus_to_home=or_unknown(full_day.campus_to_home),
        total_minutes=or_unknown(full_day.total_minutes),
        extra_minutes=or_unknown(full_day.extra_minutes),
    )


def ranked_out(item: RankedArea) -> RankedAreaOut:
    return RankedAreaOut(
        rank=item.rank,
        area=area_ref(item.facts.area),
        facts=facts_out(item.facts),
        score=ScoreOut(
            total=item.score.total,
            components=[
                ScoreComponentOut(
                    name=component.scorer,
                    value=or_unknown(component.value),
                    share=item.score.shares.get(component.scorer, 0.0),
                    reason=component.reason,
                )
                for component in item.score.components
            ],
        ),
        reasons=list(item.reasons),
        trade_off=item.trade_off,
        full_day=full_day_out(item.full_day) if item.full_day else None,
    )


def search_out(result: SearchResult) -> SearchOut:
    return SearchOut(
        city_id=result.city_id,
        campus=campus_out(result.campus),
        ranked=[ranked_out(item) for item in result.ranked],
        excluded=[
            ExcludedAreaOut(
                area=area_ref(item.facts.area),
                facts=facts_out(item.facts),
                violations=list(item.violations),
            )
            for item in result.excluded
        ],
        unchecked=[
            UncheckedAreaOut(
                area=area_ref(item.facts.area),
                facts=facts_out(item.facts),
                missing=list(item.missing),
            )
            for item in result.unchecked
        ],
    )


def comparison_out(
    comparison: CityComparison, max_rent_eur: float, max_commute_minutes: int
) -> ComparisonOut:
    return ComparisonOut(
        city_id=comparison.city_id,
        max_rent_eur=max_rent_eur,
        max_commute_minutes=max_commute_minutes,
        total_areas=comparison.total_areas,
        universities=[
            UniversityFeasibilityOut(
                university=UniversityRef(
                    id=item.university.id,
                    name=item.university.name,
                    short_name=item.university.short_name,
                ),
                feasible=item.feasible,
                campuses=[
                    CampusFeasibilityOut(
                        campus=campus_out(campus.campus),
                        feasible=campus.feasible,
                        excluded=campus.excluded,
                        unchecked=campus.unchecked,
                        feasible_area_ids=sorted(campus.feasible_area_ids),
                    )
                    for campus in item.campuses
                ],
            )
            for item in comparison.universities
        ],
    )


def area_feature(shape: AreaShape) -> AreaFeature:
    facts = shape.facts
    counts = facts.amenity_counts
    return AreaFeature(
        id=facts.area.id,
        geometry=dict(shape.outline),
        properties=AreaProperties(
            area_id=facts.area.id,
            name=facts.area.name,
            cell_count=facts.cell_count,
            rent_eur="UNKNOWN" if facts.rent is UNKNOWN else float(facts.rent.monthly_eur),
            rent_is_sample=facts.rent is not UNKNOWN and facts.rent.is_sample,
            commute_minutes=or_unknown(facts.commute_minutes),
            amenities_total=(
                "UNKNOWN"
                if counts is UNKNOWN
                else sum(counts.get(category, 0) for category in AMENITY_CATEGORIES)
            ),
            job_access_score=("UNKNOWN" if facts.job_access is UNKNOWN else facts.job_access.score),
        ),
    )


def hexagon(cell: str) -> dict[str, Any]:
    """The outline of an H3 cell as a GeoJSON polygon.

    H3 gives corners as (latitude, longitude); GeoJSON wants longitude first and
    the first corner repeated at the end to close the ring.
    """
    corners = [[round(lon, 6), round(lat, 6)] for lat, lon in h3.cell_to_boundary(cell)]
    return {"type": "Polygon", "coordinates": [[*corners, corners[0]]]}


def cell_feature(value: CellValue) -> CellFeature:
    return CellFeature(
        id=value.cell,
        geometry=hexagon(value.cell),
        properties=CellProperties(
            cell=value.cell, area_id=value.area_id, value=or_unknown(value.value)
        ),
    )

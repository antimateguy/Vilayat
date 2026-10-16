"""Schemas for an area's commute breakdown."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from api.schemas.common import AreaRef, CampusOut
from api.schemas.search import EmployerRef

LegModeOut = Literal["walk", "bus", "tram", "subway", "rail", "ferry", "other"]


class RouteLegOut(BaseModel):
    mode: LegModeOut = Field(description="`subway` is the U-Bahn, `rail` the S-Bahn and trains.")
    minutes: int = Field(description="Time moving on this leg.")
    wait_minutes: int = Field(description="Waiting before this leg, for example on the platform.")
    distance_m: int
    line: str | None = Field(examples=["U2"], description="Null for walking.")
    from_stop: str | None = Field(examples=["Scheidplatz"])
    to_stop: str | None = Field(examples=["Hauptbahnhof"])
    line_colour: str | None = Field(
        examples=["#DA421E"],
        description="The line's colour from the timetable, when it gives a real one.",
    )
    path: dict[str, Any] = Field(description="GeoJSON LineString, longitude first.")


class CommuteRouteOut(BaseModel):
    departs_at: str = Field(examples=["07:52"], description="Leaving time on a weekday.")
    total_minutes: int
    start: list[float] = Field(
        description="[longitude, latitude] where the journey starts: the street nearest "
        "the centre of the hexagon it was planned from."
    )
    legs: list[RouteLegOut]
    computed_at: datetime


class CommuteSpreadOut(BaseModel):
    """Typical morning times over the area's hexagons."""

    cells: int = Field(description="Hexagons of the area with a journey within two hours.")
    fastest_minutes: int
    median_minutes: int = Field(description="The area's commute figure in the ranking.")
    slowest_minutes: int


class AreaCommuteOut(BaseModel):
    area: AreaRef
    campus: CampusOut
    spread: CommuteSpreadOut | None = Field(
        description="Null when no hexagon of the area has a journey to the campus."
    )
    route: CommuteRouteOut | None = Field(
        description="One typical journey, from the hexagon whose time is closest to the "
        "area's median. Null until the offline job has planned it."
    )
    employer: EmployerRef | None = Field(
        description="The pinned employer, if `employer_id` was sent."
    )
    to_job: CommuteRouteOut | None = Field(
        description="A typical afternoon journey from the campus to the employer (17:00 to "
        "19:00), when an employer is pinned and the journey has been planned."
    )

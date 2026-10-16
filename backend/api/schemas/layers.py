"""GeoJSON schemas for the map layers (RFC 7946: coordinates are longitude, latitude)."""

from typing import Any, Literal

from pydantic import BaseModel, Field

from api.schemas.common import UnknownValue


class AreaProperties(BaseModel):
    area_id: int
    name: str
    cell_count: int
    rent_eur: float | UnknownValue
    rent_is_sample: bool = Field(description="True when the rent is placeholder data.")
    commute_minutes: int | UnknownValue = Field(
        description='Morning minutes to the campus; "UNKNOWN" when no campus was given.'
    )
    amenities_total: int | UnknownValue
    job_access_score: float | UnknownValue


class AreaFeature(BaseModel):
    type: Literal["Feature"] = "Feature"
    id: int
    geometry: dict[str, Any] = Field(
        description="A GeoJSON MultiPolygon, simplified to about 10 m."
    )
    properties: AreaProperties


class AreaFeatureCollection(BaseModel):
    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: list[AreaFeature]


class CellProperties(BaseModel):
    cell: str = Field(description="H3 index, resolution 8.", examples=["881f8d7a49fffff"])
    area_id: int
    value: float | UnknownValue = Field(
        description="Minutes, a count or a 0 to 1 score, depending on the metric."
    )


class CellFeature(BaseModel):
    type: Literal["Feature"] = "Feature"
    id: str
    geometry: dict[str, Any] = Field(description="A GeoJSON Polygon: the hexagon.")
    properties: CellProperties


class CellFeatureCollection(BaseModel):
    type: Literal["FeatureCollection"] = "FeatureCollection"
    metric: str = Field(examples=["commute"])
    features: list[CellFeature]


class TransitLineProperties(BaseModel):
    label: str = Field(examples=["U2"])
    mode: Literal["subway", "rail", "tram"]
    colour: str | None = Field(
        description="The line's colour from the timetable, when it gives a real one."
    )


class TransitLineFeature(BaseModel):
    type: Literal["Feature"] = "Feature"
    geometry: dict[str, Any] = Field(
        description="A GeoJSON LineString through the stops of the line's longest trip."
    )
    properties: TransitLineProperties


class TransitLineCollection(BaseModel):
    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: list[TransitLineFeature]

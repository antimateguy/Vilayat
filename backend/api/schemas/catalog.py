"""Schemas for the reference data: cities, universities, employers and data sources."""

from datetime import date

from pydantic import BaseModel, Field

from api.schemas.common import CampusOut, UnknownValue


class CityOut(BaseModel):
    id: str = Field(examples=["munich"])
    name: str = Field(examples=["Munich"])


class UniversityOut(BaseModel):
    id: int
    name: str = Field(examples=["Technische Universität München"])
    short_name: str = Field(examples=["TUM"])
    campuses: list[CampusOut]


class EmployerOut(BaseModel):
    """A corporate site a student can pin to see the full day's travel."""

    id: int
    name: str = Field(examples=["BMW Group Headquarters"])
    lat: float
    lon: float
    is_sample: bool = Field(description="True while the list of employers is unconfirmed.")


class DataSourceOut(BaseModel):
    used_for: str = Field(examples=["Travel times"])
    name: str
    publisher: str = Field(examples=["Münchner Verkehrs- und Tarifverbund GmbH (MVV)"])
    licence: str = Field(examples=["CC BY"])
    as_of: date | UnknownValue = Field(
        description='The date the data refers to; "UNKNOWN" if it has not been loaded.'
    )
    is_sample: bool
    url: str | None

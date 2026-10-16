"""SQLAlchemy table definitions: the whole database schema in one module.

Classes end in "Row" to tell them apart from the domain classes they are mapped
to. Nothing outside infrastructure imports this module.
"""

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from geoalchemy2 import Geometry, WKBElement
from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Identity,
    Index,
    Integer,
    MetaData,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    false,
    true,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from domain.destination import DestinationKind
from domain.document import EMBEDDING_DIMENSIONS
from domain.place import PlaceCategory
from domain.travel import TimeWindow

SRID_WGS84 = 4326
H3_INDEX_LENGTH = 15

# Fixed names for constraints and indexes, so migrations can refer to them.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_N_label)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def _enum_column(enum_class: type[StrEnum], name: str) -> Enum:
    """Store an enum as text guarded by a CHECK constraint.

    A native Postgres enum type is awkward to change later; a CHECK constraint is
    replaced by an ordinary migration.
    """
    return Enum(
        enum_class,
        name=name,
        native_enum=False,
        create_constraint=True,
        length=32,
        values_callable=lambda members: [member.value for member in members],
    )


def _point() -> Geometry:
    # spatial_index=False: the GiST index is declared explicitly on each table.
    return Geometry("POINT", srid=SRID_WGS84, spatial_index=False)


class Provenance:
    """Columns every loaded dataset carries: where it came from and as of when."""

    source: Mapped[str] = mapped_column(String(200))
    source_url: Mapped[str | None] = mapped_column(Text)
    as_of: Mapped[date] = mapped_column(Date)
    is_sample: Mapped[bool] = mapped_column(Boolean, server_default=false())
    """True for placeholder fixture rows that real data must replace."""


class CityRow(Base):
    __tablename__ = "cities"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(100))


class UniversityRow(Base):
    __tablename__ = "universities"
    __table_args__ = (UniqueConstraint("city_id", "name"),)

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    city_id: Mapped[str] = mapped_column(ForeignKey("cities.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    short_name: Mapped[str] = mapped_column(String(50))


class DestinationRow(Provenance, Base):
    """Anything travel times are computed to: campus, job hotspot or employer site."""

    __tablename__ = "destinations"
    __table_args__ = (
        Index("ix_destinations_geom", "geom", postgresql_using="gist"),
        Index("ix_destinations_city_id_kind", "city_id", "kind"),
    )

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    city_id: Mapped[str] = mapped_column(ForeignKey("cities.id"))
    kind: Mapped[DestinationKind] = mapped_column(_enum_column(DestinationKind, "kind"))
    name: Mapped[str] = mapped_column(String(200))
    geom: Mapped[WKBElement] = mapped_column(_point())


class CampusRow(Base):
    """A university site. Its location lives on the destination row it points to."""

    __tablename__ = "campuses"
    __table_args__ = (UniqueConstraint("university_id", "name"),)

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    university_id: Mapped[int] = mapped_column(ForeignKey("universities.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    destination_id: Mapped[int] = mapped_column(ForeignKey("destinations.id"), unique=True)


class NeighbourhoodRow(Provenance, Base):
    """An area: the unit the product ranks."""

    __tablename__ = "neighbourhoods"
    __table_args__ = (
        UniqueConstraint("city_id", "external_id"),
        Index("ix_neighbourhoods_geom", "geom", postgresql_using="gist"),
    )

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    city_id: Mapped[str] = mapped_column(ForeignKey("cities.id"), index=True)
    external_id: Mapped[str] = mapped_column(String(32))
    """Key of the area in the official source, so a reload updates rather than duplicates."""
    name: Mapped[str] = mapped_column(String(200))
    geom: Mapped[WKBElement] = mapped_column(
        Geometry("MULTIPOLYGON", srid=SRID_WGS84, spatial_index=False)
    )


class CellRow(Base):
    """One H3 hexagon (resolution 8) inside a neighbourhood."""

    __tablename__ = "cells"
    __table_args__ = (
        CheckConstraint(f"length(h3_index) = {H3_INDEX_LENGTH}", name="h3_index_length"),
        CheckConstraint("job_access_score BETWEEN 0 AND 1", name="job_access_score_range"),
        Index("ix_cells_centroid", "centroid", postgresql_using="gist"),
    )

    h3_index: Mapped[str] = mapped_column(String(H3_INDEX_LENGTH), primary_key=True)
    city_id: Mapped[str] = mapped_column(ForeignKey("cities.id"), index=True)
    neighbourhood_id: Mapped[int] = mapped_column(
        ForeignKey("neighbourhoods.id", ondelete="CASCADE"), index=True
    )
    centroid: Mapped[WKBElement] = mapped_column(_point())
    # Written by jobs.compute_job_access; null until that job has run for the city.
    job_places_nearby: Mapped[int | None] = mapped_column(Integer)
    job_access_score: Mapped[float | None] = mapped_column(Float)


class TravelTimeRow(Base):
    """Public-transport minutes from a cell to a destination, written by the offline job.

    The primary key starts with destination and time window because every query
    asks "all cells for this destination in this window".
    A missing row means no route was found; it is never stored as a number.
    """

    __tablename__ = "travel_times"
    __table_args__ = (
        CheckConstraint("minutes >= 0", name="minutes_non_negative"),
        Index("ix_travel_times_cell_id", "cell_id"),
    )

    destination_id: Mapped[int] = mapped_column(
        ForeignKey("destinations.id", ondelete="CASCADE"), primary_key=True
    )
    time_window: Mapped[TimeWindow] = mapped_column(
        _enum_column(TimeWindow, "time_window"), primary_key=True
    )
    cell_id: Mapped[str] = mapped_column(
        ForeignKey("cells.h3_index", ondelete="CASCADE"), primary_key=True
    )
    minutes: Mapped[int] = mapped_column(SmallInteger)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class DestinationTravelTimeRow(Base):
    """Public-transport minutes from one destination to another, for example from
    a campus to an employer. Needed for the middle leg of a day: home, campus,
    job, home. Written by the same offline job as travel_times.
    """

    __tablename__ = "destination_travel_times"
    __table_args__ = (
        CheckConstraint("minutes >= 0", name="minutes_non_negative"),
        CheckConstraint("from_destination_id <> to_destination_id", name="different_destinations"),
    )

    from_destination_id: Mapped[int] = mapped_column(
        ForeignKey("destinations.id", ondelete="CASCADE"), primary_key=True
    )
    to_destination_id: Mapped[int] = mapped_column(
        ForeignKey("destinations.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    time_window: Mapped[TimeWindow] = mapped_column(
        _enum_column(TimeWindow, "time_window"), primary_key=True
    )
    minutes: Mapped[int] = mapped_column(SmallInteger)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AreaRentRow(Provenance, Base):
    """An area-level rent estimate. An area without a row has an UNKNOWN rent."""

    __tablename__ = "area_rents"
    __table_args__ = (
        UniqueConstraint("neighbourhood_id", "source", "as_of"),
        CheckConstraint("monthly_rent_eur > 0", name="rent_positive"),
    )

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    neighbourhood_id: Mapped[int] = mapped_column(
        ForeignKey("neighbourhoods.id", ondelete="CASCADE"), index=True
    )
    monthly_rent_eur: Mapped[Decimal] = mapped_column(Numeric(7, 2))
    basis: Mapped[str] = mapped_column(Text)
    """What the figure measures, for example "median asking rent, 1-room flat"."""


class PlaceRow(Provenance, Base):
    """A point of interest from OpenStreetMap."""

    __tablename__ = "places"
    __table_args__ = (
        UniqueConstraint("osm_type", "osm_id"),
        Index("ix_places_geom", "geom", postgresql_using="gist"),
        Index("ix_places_cell_id_category", "cell_id", "category"),
        Index("ix_places_city_id_category", "city_id", "category"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    city_id: Mapped[str] = mapped_column(ForeignKey("cities.id"))
    osm_type: Mapped[str] = mapped_column(String(8))
    osm_id: Mapped[int] = mapped_column(BigInteger)
    category: Mapped[PlaceCategory] = mapped_column(_enum_column(PlaceCategory, "category"))
    name: Mapped[str | None] = mapped_column(String(300))
    geom: Mapped[WKBElement] = mapped_column(_point())
    cell_id: Mapped[str | None] = mapped_column(ForeignKey("cells.h3_index", ondelete="SET NULL"))
    """The cell the place falls in; null when it lies outside every neighbourhood."""


class DocChunkRow(Base):
    """A passage of an official document with its embedding, for retrieval."""

    __tablename__ = "doc_chunks"
    __table_args__ = (
        UniqueConstraint("document_key", "chunk_index"),
        # HNSW: approximate nearest-neighbour index, here for cosine distance.
        Index(
            "ix_doc_chunks_embedding",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    document_key: Mapped[str] = mapped_column(String(200))
    chunk_index: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(300))
    source_url: Mapped[str] = mapped_column(Text)
    content: Mapped[str] = mapped_column(Text)
    city_id: Mapped[str | None] = mapped_column(ForeignKey("cities.id"))
    """Null when the document applies to every city."""
    retrieved_on: Mapped[date] = mapped_column(Date)
    is_sample: Mapped[bool] = mapped_column(Boolean, server_default=false())
    can_quote: Mapped[bool] = mapped_column(Boolean, server_default=true())
    """False when the source's licence does not allow showing the text itself."""
    embedding: Mapped[Any] = mapped_column(Vector(EMBEDDING_DIMENSIONS))
    embedding_model: Mapped[str] = mapped_column(String(100))


class AreaBriefingRow(Base):
    """The stored AI briefing of an area, with the engine figures it was written from."""

    __tablename__ = "area_briefings"

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    neighbourhood_id: Mapped[int] = mapped_column(
        ForeignKey("neighbourhoods.id", ondelete="CASCADE"), unique=True
    )
    content: Mapped[str] = mapped_column(Text)
    facts: Mapped[dict[str, Any]] = mapped_column(JSONB)
    model: Mapped[str] = mapped_column(String(100))
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AiUsageRow(Base):
    """How many requests went to a model on one of the provider's days.

    Kept in the database, not in memory, so a restart does not reset the count
    and the API and the offline jobs draw on the same daily allowance.
    """

    __tablename__ = "ai_usage"
    __table_args__ = (CheckConstraint("requests >= 0", name="requests_non_negative"),)

    day: Mapped[date] = mapped_column(Date, primary_key=True)
    model: Mapped[str] = mapped_column(String(100), primary_key=True)
    requests: Mapped[int] = mapped_column(Integer)


class CommuteRouteRow(Base):
    """One typical morning journey from an area to a destination, step by step.

    Written by jobs.build_commute_routes. `legs` is a list of objects with mode,
    minutes, wait_minutes, distance_m, line, from_stop, to_stop and path (a list
    of [longitude, latitude] pairs), in travel order.
    """

    __tablename__ = "commute_routes"
    __table_args__ = (CheckConstraint("total_minutes >= 0", name="total_minutes_non_negative"),)

    neighbourhood_id: Mapped[int] = mapped_column(
        ForeignKey("neighbourhoods.id", ondelete="CASCADE"), primary_key=True
    )
    destination_id: Mapped[int] = mapped_column(
        ForeignKey("destinations.id", ondelete="CASCADE"), primary_key=True
    )
    cell_id: Mapped[str] = mapped_column(ForeignKey("cells.h3_index", ondelete="CASCADE"))
    departs_at: Mapped[datetime] = mapped_column(DateTime(timezone=False))
    total_minutes: Mapped[int] = mapped_column(SmallInteger)
    legs: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class DestinationRouteRow(Base):
    """One typical afternoon journey between two destinations, for example from a
    campus to an employer. Same `legs` format as commute_routes."""

    __tablename__ = "destination_routes"
    __table_args__ = (
        CheckConstraint("total_minutes >= 0", name="total_minutes_non_negative"),
        CheckConstraint("from_destination_id <> to_destination_id", name="different_destinations"),
    )

    from_destination_id: Mapped[int] = mapped_column(
        ForeignKey("destinations.id", ondelete="CASCADE"), primary_key=True
    )
    to_destination_id: Mapped[int] = mapped_column(
        ForeignKey("destinations.id", ondelete="CASCADE"), primary_key=True
    )
    departs_at: Mapped[datetime] = mapped_column(DateTime(timezone=False))
    total_minutes: Mapped[int] = mapped_column(SmallInteger)
    legs: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

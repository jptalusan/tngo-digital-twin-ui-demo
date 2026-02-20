from __future__ import annotations

from datetime import datetime
from typing import Optional

from geoalchemy2 import Geometry, WKBElement
from sqlalchemy import ForeignKey, String, Integer, Float, UniqueConstraint, DateTime, func, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class GtfsFeed(Base):
    """Registry of uploaded GTFS feeds. One row per unique zip (keyed by MD5 hash)."""

    __tablename__ = "gtfs_feed"

    id: Mapped[int] = mapped_column(primary_key=True)
    gtfs_id: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    gtfs_name: Mapped[str] = mapped_column(String, nullable=False)
    filename: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    uploaded_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )


class GtfsJob(Base):
    """Async upload job tracker."""

    __tablename__ = "gtfs_job"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    gtfs_id: Mapped[str] = mapped_column(
        String, ForeignKey("gtfs_feed.gtfs_id"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    error: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    row_counts: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=True
    )


class Agency(Base):
    __tablename__ = "gtfs_agency"
    __table_args__ = (UniqueConstraint("gtfs_id", "agency_id", name="uq_gtfs_agency"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    gtfs_id: Mapped[str] = mapped_column(
        String, ForeignKey("gtfs_feed.gtfs_id", ondelete="CASCADE"), nullable=False, index=True
    )
    agency_id: Mapped[str] = mapped_column(String, index=True)
    name: Mapped[str] = mapped_column(String)
    url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    timezone: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    lang: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String, nullable=True)


class Route(Base):
    __tablename__ = "gtfs_route"
    __table_args__ = (UniqueConstraint("gtfs_id", "route_id", name="uq_gtfs_route"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    gtfs_id: Mapped[str] = mapped_column(
        String, ForeignKey("gtfs_feed.gtfs_id", ondelete="CASCADE"), nullable=False, index=True
    )
    route_id: Mapped[str] = mapped_column(String, index=True)
    agency_id: Mapped[Optional[str]] = mapped_column(String, index=True, nullable=True)
    short_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    long_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    route_type: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)


class Stop(Base):
    __tablename__ = "gtfs_stop"
    __table_args__ = (UniqueConstraint("gtfs_id", "stop_id", name="uq_gtfs_stop"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    gtfs_id: Mapped[str] = mapped_column(
        String, ForeignKey("gtfs_feed.gtfs_id", ondelete="CASCADE"), nullable=False, index=True
    )
    stop_id: Mapped[str] = mapped_column(String, index=True)
    name: Mapped[Optional[str]] = mapped_column(String, index=True, nullable=True)
    # PostGIS POINT(lon lat) SRID 4326
    location: Mapped[Optional[WKBElement]] = mapped_column(
        Geometry("POINT", srid=4326, spatial_index=True), nullable=True
    )


class Calendar(Base):
    """GTFS calendar.txt — weekly service pattern.

    GTFS spec uses 0/1 integers for day flags, so we keep Integer here to
    faithfully mirror the source data and avoid coercion surprises on load.
    """

    __tablename__ = "gtfs_calendar"

    id: Mapped[int] = mapped_column(primary_key=True)
    gtfs_id: Mapped[str] = mapped_column(
        String, ForeignKey("gtfs_feed.gtfs_id", ondelete="CASCADE"), nullable=False, index=True
    )
    service_id: Mapped[str] = mapped_column(String, index=True)
    # GTFS spec: 0 or 1 — kept as Integer to match raw CSV values exactly.
    monday: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    tuesday: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    wednesday: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    thursday: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    friday: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    saturday: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    sunday: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # YYYYMMDD strings per GTFS spec — stored as String to avoid timezone drift.
    start_date: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    end_date: Mapped[Optional[str]] = mapped_column(String, nullable=True)


class CalendarDate(Base):
    __tablename__ = "gtfs_calendar_date"

    id: Mapped[int] = mapped_column(primary_key=True)
    gtfs_id: Mapped[str] = mapped_column(
        String, ForeignKey("gtfs_feed.gtfs_id", ondelete="CASCADE"), nullable=False, index=True
    )
    service_id: Mapped[str] = mapped_column(String, index=True)
    date: Mapped[str] = mapped_column(String)
    exception_type: Mapped[int] = mapped_column(Integer)


class Shape(Base):
    __tablename__ = "gtfs_shape"
    __table_args__ = (UniqueConstraint("gtfs_id", "shape_id", name="uq_gtfs_shape"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    gtfs_id: Mapped[str] = mapped_column(
        String, ForeignKey("gtfs_feed.gtfs_id", ondelete="CASCADE"), nullable=False, index=True
    )
    shape_id: Mapped[str] = mapped_column(String, index=True)


class ShapePoint(Base):
    __tablename__ = "gtfs_shape_point"

    id: Mapped[int] = mapped_column(primary_key=True)
    gtfs_id: Mapped[str] = mapped_column(
        String, ForeignKey("gtfs_feed.gtfs_id", ondelete="CASCADE"), nullable=False, index=True
    )
    shape_id: Mapped[str] = mapped_column(String, index=True)
    sequence: Mapped[int] = mapped_column(Integer)
    # PostGIS POINT(lon lat) SRID 4326
    geom: Mapped[Optional[WKBElement]] = mapped_column(
        Geometry("POINT", srid=4326), nullable=True
    )
    dist_traveled: Mapped[Optional[float]] = mapped_column(Float, nullable=True)


class Trip(Base):
    __tablename__ = "gtfs_trip"
    __table_args__ = (UniqueConstraint("gtfs_id", "trip_id", name="uq_gtfs_trip"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    gtfs_id: Mapped[str] = mapped_column(
        String, ForeignKey("gtfs_feed.gtfs_id", ondelete="CASCADE"), nullable=False, index=True
    )
    trip_id: Mapped[str] = mapped_column(String, index=True)
    route_id: Mapped[str] = mapped_column(String, index=True)
    service_id: Mapped[Optional[str]] = mapped_column(String, index=True, nullable=True)
    shape_id: Mapped[Optional[str]] = mapped_column(String, index=True, nullable=True)
    headsign: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    direction_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)


class StopTime(Base):
    __tablename__ = "gtfs_stop_time"
    __table_args__ = (
        UniqueConstraint("gtfs_id", "trip_id", "stop_sequence", name="uq_gtfs_stop_time"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    gtfs_id: Mapped[str] = mapped_column(
        String, ForeignKey("gtfs_feed.gtfs_id", ondelete="CASCADE"), nullable=False, index=True
    )
    trip_id: Mapped[str] = mapped_column(String, index=True)
    stop_id: Mapped[str] = mapped_column(String, index=True)
    arrival_time: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    departure_time: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    stop_sequence: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

from __future__ import annotations

from typing import Optional

from sqlalchemy import String, Integer, Float, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Agency(Base):
    __tablename__ = "agency"

    id: Mapped[int] = mapped_column(primary_key=True)
    agency_id: Mapped[str] = mapped_column(String, unique=True, index=True)
    name: Mapped[str] = mapped_column(String)
    url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    timezone: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    lang: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String, nullable=True)


class Route(Base):
    __tablename__ = "route"

    id: Mapped[int] = mapped_column(primary_key=True)
    route_id: Mapped[str] = mapped_column(String, unique=True, index=True)
    agency_id: Mapped[Optional[str]] = mapped_column(String, index=True)
    short_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    long_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    route_type: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    trips: Mapped[list["Trip"]] = relationship(back_populates="route")


class Stop(Base):
    __tablename__ = "stop"

    id: Mapped[int] = mapped_column(primary_key=True)
    stop_id: Mapped[str] = mapped_column(String, unique=True, index=True)
    name: Mapped[Optional[str]] = mapped_column(String, index=True, nullable=True)
    lat: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    lon: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    stop_times: Mapped[list["StopTime"]] = relationship(back_populates="stop")


class Calendar(Base):
    __tablename__ = "calendar"

    id: Mapped[int] = mapped_column(primary_key=True)
    service_id: Mapped[str] = mapped_column(String, index=True)
    monday: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    tuesday: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    wednesday: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    thursday: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    friday: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    saturday: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    sunday: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    start_date: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    end_date: Mapped[Optional[str]] = mapped_column(String, nullable=True)


class CalendarDate(Base):
    __tablename__ = "calendar_date"

    id: Mapped[int] = mapped_column(primary_key=True)
    service_id: Mapped[str] = mapped_column(String, index=True)
    date: Mapped[str] = mapped_column(String)
    exception_type: Mapped[int] = mapped_column(Integer)


class Shape(Base):
    __tablename__ = "shape"

    id: Mapped[int] = mapped_column(primary_key=True)
    shape_id: Mapped[str] = mapped_column(String, unique=True, index=True)

    points: Mapped[list["ShapePoint"]] = relationship(back_populates="shape")


class ShapePoint(Base):
    __tablename__ = "shape_point"

    id: Mapped[int] = mapped_column(primary_key=True)
    shape_id: Mapped[str] = mapped_column(String, ForeignKey("shape.shape_id"), index=True)
    sequence: Mapped[int] = mapped_column(Integer)
    lat: Mapped[float] = mapped_column(Float)
    lon: Mapped[float] = mapped_column(Float)
    dist_traveled: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    shape: Mapped[Optional[Shape]] = relationship(back_populates="points")


class Trip(Base):
    __tablename__ = "trip"

    id: Mapped[int] = mapped_column(primary_key=True)
    trip_id: Mapped[str] = mapped_column(String, unique=True, index=True)
    route_id: Mapped[str] = mapped_column(String, ForeignKey("route.route_id"), index=True)
    service_id: Mapped[Optional[str]] = mapped_column(String, index=True, nullable=True)
    shape_id: Mapped[Optional[str]] = mapped_column(String, index=True, nullable=True)
    headsign: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    direction_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    route: Mapped[Optional[Route]] = relationship(back_populates="trips")
    stop_times: Mapped[list["StopTime"]] = relationship(back_populates="trip")


class StopTime(Base):
    __tablename__ = "stop_time"
    __table_args__ = (
        UniqueConstraint("trip_id", "stop_sequence", name="uq_stop_time_trip_seq"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    trip_id: Mapped[str] = mapped_column(String, ForeignKey("trip.trip_id"), index=True)
    stop_id: Mapped[str] = mapped_column(String, ForeignKey("stop.stop_id"), index=True)
    arrival_time: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    departure_time: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    stop_sequence: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    trip: Mapped[Optional[Trip]] = relationship(back_populates="stop_times")
    stop: Mapped[Optional[Stop]] = relationship(back_populates="stop_times")

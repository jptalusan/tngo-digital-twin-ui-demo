from __future__ import annotations

from typing import Optional

from geoalchemy2 import Geometry
from sqlalchemy import String, Integer, Float, ForeignKey, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Depot(Base):
    __tablename__ = "depot"

    id: Mapped[int] = mapped_column(primary_key=True)
    depot_id: Mapped[str] = mapped_column(String, unique=True, index=True)
    name: Mapped[str] = mapped_column(String)
    lat: Mapped[float] = mapped_column(Float)
    lon: Mapped[float] = mapped_column(Float)
    address: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    vehicles: Mapped[list["OnDemandVehicle"]] = relationship(back_populates="depot")
    service_zones: Mapped[list["OnDemandServiceZone"]] = relationship(back_populates="depot")


class OnDemandServiceZone(Base):
    """One row per H3 hexagon that belongs to a depot's service zone."""

    __tablename__ = "ondemand_service_zone"

    id: Mapped[int] = mapped_column(primary_key=True)
    depot_id: Mapped[str] = mapped_column(String, ForeignKey("depot.depot_id"), index=True)
    hex_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    h3_resolution: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # Hex boundary stored as a polygon for PostGIS spatial queries
    boundary: Mapped[Optional[object]] = mapped_column(
        Geometry("POLYGON", srid=4326), nullable=True
    )

    depot: Mapped[Optional[Depot]] = relationship(back_populates="service_zones")


class OnDemandVehicle(Base):
    __tablename__ = "ondemand_vehicle"

    id: Mapped[int] = mapped_column(primary_key=True)
    vehicle_id: Mapped[str] = mapped_column(String, unique=True, index=True)
    depot_id: Mapped[str] = mapped_column(String, ForeignKey("depot.depot_id"), index=True)
    capacity: Mapped[int] = mapped_column(Integer)
    status: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    depot: Mapped[Optional[Depot]] = relationship(back_populates="vehicles")
    schedules: Mapped[list["VehicleSchedule"]] = relationship(back_populates="vehicle")


class VehicleSchedule(Base):
    __tablename__ = "vehicle_schedule"

    id: Mapped[int] = mapped_column(primary_key=True)
    vehicle_id: Mapped[str] = mapped_column(String, ForeignKey("ondemand_vehicle.vehicle_id"), index=True)
    service_days: Mapped[str] = mapped_column(String)
    start_time: Mapped[str] = mapped_column(String)
    end_time: Mapped[str] = mapped_column(String)

    vehicle: Mapped[Optional[OnDemandVehicle]] = relationship(back_populates="schedules")


class OnDemandRequest(Base):
    __tablename__ = "ondemand_request"

    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[str] = mapped_column(String, unique=True, index=True)
    origin_lat: Mapped[float] = mapped_column(Float)
    origin_lon: Mapped[float] = mapped_column(Float)
    destination_lat: Mapped[float] = mapped_column(Float)
    destination_lon: Mapped[float] = mapped_column(Float)
    passengers: Mapped[int] = mapped_column(Integer, default=1)
    pickup_window_start_min: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    pickup_window_end_min: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    dropoff_window_end_min: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    requested_at: Mapped[Optional[str]] = mapped_column(String, nullable=True)


class OnDemandTrip(Base):
    __tablename__ = "ondemand_trip"

    id: Mapped[int] = mapped_column(primary_key=True)
    trip_id: Mapped[str] = mapped_column(String, unique=True, index=True)
    request_id: Mapped[str] = mapped_column(String, ForeignKey("ondemand_request.request_id"), index=True)
    vehicle_id: Mapped[Optional[str]] = mapped_column(String, index=True, nullable=True)
    status: Mapped[Optional[str]] = mapped_column(String, nullable=True)


class VehicleRoute(Base):
    __tablename__ = "vehicle_route"

    id: Mapped[int] = mapped_column(primary_key=True)
    route_id: Mapped[str] = mapped_column(String, unique=True, index=True)
    vehicle_id: Mapped[str] = mapped_column(String, ForeignKey("ondemand_vehicle.vehicle_id"), index=True)
    status: Mapped[str] = mapped_column(String, default="active")
    updated_at: Mapped[Optional[DateTime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    stops: Mapped[list["VehicleRouteStop"]] = relationship(
        back_populates="route", cascade="all, delete-orphan"
    )


class VehicleRouteStop(Base):
    __tablename__ = "vehicle_route_stop"

    id: Mapped[int] = mapped_column(primary_key=True)
    route_id: Mapped[str] = mapped_column(String, ForeignKey("vehicle_route.route_id"), index=True)
    sequence: Mapped[int] = mapped_column(Integer)
    lat: Mapped[float] = mapped_column(Float)
    lon: Mapped[float] = mapped_column(Float)
    window_start_min: Mapped[int] = mapped_column(Integer)
    window_end_min: Mapped[int] = mapped_column(Integer)
    delta_load: Mapped[int] = mapped_column(Integer)
    stop_type: Mapped[str] = mapped_column(String)
    request_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    planned_arrival_min: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    planned_departure_min: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    route: Mapped[Optional[VehicleRoute]] = relationship(back_populates="stops")

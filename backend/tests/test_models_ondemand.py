"""Unit tests for on-demand SQLAlchemy models.

Tests cover:
- Depot / vehicle / zone creation and relationships
- VehicleRoute / VehicleRouteStop cascade delete
- OnDemandRequest / OnDemandTrip persistence
- Unique constraints
- VehicleSchedule time parsing assumptions
"""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.db import SessionLocal
from app.models.ondemand import (
    Depot,
    OnDemandRequest,
    OnDemandServiceZone,
    OnDemandTrip,
    OnDemandVehicle,
    VehicleRoute,
    VehicleRouteStop,
    VehicleSchedule,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _depot(session, depot_id: str = "depot-1", name: str = "Test Depot") -> Depot:
    d = Depot(depot_id=depot_id, name=name, lat=35.0, lon=-90.0)
    session.add(d)
    session.flush()
    return d


def _vehicle(
    session,
    vehicle_id: str = "veh-1",
    depot_id: str = "depot-1",
    capacity: int = 4,
) -> OnDemandVehicle:
    v = OnDemandVehicle(vehicle_id=vehicle_id, depot_id=depot_id, capacity=capacity)
    session.add(v)
    session.flush()
    return v


# ---------------------------------------------------------------------------
# Depot
# ---------------------------------------------------------------------------


def test_depot_persists_basic_fields():
    session = SessionLocal()
    try:
        d = Depot(depot_id="d-basic", name="Basic Depot", lat=35.1, lon=-90.1, address="123 Main")
        session.add(d)
        session.commit()

        row = session.execute(
            select(Depot).where(Depot.depot_id == "d-basic")
        ).scalars().first()
        assert row is not None
        assert row.name == "Basic Depot"
        assert row.lat == pytest.approx(35.1)
        assert row.address == "123 Main"
    finally:
        session.rollback()
        session.close()


def test_depot_unique_depot_id():
    session = SessionLocal()
    try:
        session.add(Depot(depot_id="d-dup", name="First", lat=0.0, lon=0.0))
        session.flush()
        session.add(Depot(depot_id="d-dup", name="Second", lat=1.0, lon=1.0))
        with pytest.raises(IntegrityError):
            session.flush()
    finally:
        session.rollback()
        session.close()


def test_depot_optional_address():
    session = SessionLocal()
    try:
        session.add(Depot(depot_id="d-no-addr", name="No Addr", lat=0.0, lon=0.0))
        session.commit()
        row = session.execute(
            select(Depot).where(Depot.depot_id == "d-no-addr")
        ).scalars().first()
        assert row.address is None
    finally:
        session.rollback()
        session.close()


# ---------------------------------------------------------------------------
# OnDemandVehicle
# ---------------------------------------------------------------------------


def test_vehicle_relationship_to_depot():
    session = SessionLocal()
    try:
        depot = _depot(session, "d-veh-rel")
        v = _vehicle(session, "veh-rel-1", "d-veh-rel", capacity=6)
        session.commit()

        refreshed = session.get(Depot, depot.id)
        assert any(v.vehicle_id == "veh-rel-1" for v in refreshed.vehicles)
    finally:
        session.rollback()
        session.close()


def test_vehicle_unique_vehicle_id():
    session = SessionLocal()
    try:
        depot = _depot(session, "d-veh-dup")
        session.add(OnDemandVehicle(vehicle_id="v-dup", depot_id="d-veh-dup", capacity=4))
        session.flush()
        session.add(OnDemandVehicle(vehicle_id="v-dup", depot_id="d-veh-dup", capacity=6))
        with pytest.raises(IntegrityError):
            session.flush()
    finally:
        session.rollback()
        session.close()


def test_vehicle_optional_status():
    session = SessionLocal()
    try:
        depot = _depot(session, "d-veh-status")
        session.add(OnDemandVehicle(vehicle_id="veh-no-status", depot_id="d-veh-status", capacity=4))
        session.commit()
        row = session.execute(
            select(OnDemandVehicle).where(OnDemandVehicle.vehicle_id == "veh-no-status")
        ).scalars().first()
        assert row.status is None
    finally:
        session.rollback()
        session.close()


# ---------------------------------------------------------------------------
# VehicleSchedule
# ---------------------------------------------------------------------------


def test_vehicle_schedule_persists():
    session = SessionLocal()
    try:
        depot = _depot(session, "d-sched")
        v = _vehicle(session, "veh-sched-1", "d-sched")
        schedule = VehicleSchedule(
            vehicle_id="veh-sched-1",
            service_days="mon,tue,wed,thu,fri",
            start_time="06:00",
            end_time="22:00",
        )
        session.add(schedule)
        session.commit()

        row = session.execute(
            select(VehicleSchedule).where(VehicleSchedule.vehicle_id == "veh-sched-1")
        ).scalars().first()
        assert row is not None
        assert row.start_time == "06:00"
        assert row.end_time == "22:00"
        assert "mon" in row.service_days
    finally:
        session.rollback()
        session.close()


def test_vehicle_schedule_relationship():
    session = SessionLocal()
    try:
        depot = _depot(session, "d-sched-rel")
        v = _vehicle(session, "veh-sched-rel", "d-sched-rel")
        session.add(
            VehicleSchedule(
                vehicle_id="veh-sched-rel",
                service_days="mon",
                start_time="08:00",
                end_time="16:00",
            )
        )
        session.commit()

        loaded = session.execute(
            select(OnDemandVehicle).where(OnDemandVehicle.vehicle_id == "veh-sched-rel")
        ).scalars().first()
        assert len(loaded.schedules) == 1
        assert loaded.schedules[0].start_time == "08:00"
    finally:
        session.rollback()
        session.close()


# ---------------------------------------------------------------------------
# OnDemandServiceZone
# ---------------------------------------------------------------------------


def test_service_zone_persists_without_geometry():
    session = SessionLocal()
    try:
        depot = _depot(session, "d-zone")
        zone = OnDemandServiceZone(
            depot_id="d-zone",
            hex_id="8928308280fffff",
            h3_resolution=9,
        )
        session.add(zone)
        session.commit()

        row = session.execute(
            select(OnDemandServiceZone).where(OnDemandServiceZone.hex_id == "8928308280fffff")
        ).scalars().first()
        assert row is not None
        assert row.h3_resolution == 9
        assert row.boundary is None
    finally:
        session.rollback()
        session.close()


def test_service_zone_multiple_per_depot():
    session = SessionLocal()
    try:
        depot = _depot(session, "d-multi-zone")
        for hex_id in ["hex-a", "hex-b", "hex-c"]:
            session.add(
                OnDemandServiceZone(depot_id="d-multi-zone", hex_id=hex_id, h3_resolution=9)
            )
        session.commit()

        zones = session.execute(
            select(OnDemandServiceZone).where(OnDemandServiceZone.depot_id == "d-multi-zone")
        ).scalars().all()
        assert len(zones) == 3
    finally:
        session.rollback()
        session.close()


# ---------------------------------------------------------------------------
# OnDemandRequest
# ---------------------------------------------------------------------------


def test_on_demand_request_persists():
    session = SessionLocal()
    try:
        req = OnDemandRequest(
            request_id="req-001",
            origin_lat=35.1,
            origin_lon=-90.0,
            destination_lat=35.2,
            destination_lon=-89.9,
            passengers=2,
            pickup_window_start_min=480,
            pickup_window_end_min=510,
            dropoff_window_end_min=570,
        )
        session.add(req)
        session.commit()

        row = session.execute(
            select(OnDemandRequest).where(OnDemandRequest.request_id == "req-001")
        ).scalars().first()
        assert row is not None
        assert row.passengers == 2
        assert row.pickup_window_start_min == 480
    finally:
        session.rollback()
        session.close()


def test_on_demand_request_unique_id():
    session = SessionLocal()
    try:
        session.add(
            OnDemandRequest(
                request_id="req-dup", origin_lat=0.0, origin_lon=0.0,
                destination_lat=1.0, destination_lon=1.0, passengers=1,
            )
        )
        session.flush()
        session.add(
            OnDemandRequest(
                request_id="req-dup", origin_lat=2.0, origin_lon=2.0,
                destination_lat=3.0, destination_lon=3.0, passengers=1,
            )
        )
        with pytest.raises(IntegrityError):
            session.flush()
    finally:
        session.rollback()
        session.close()


# ---------------------------------------------------------------------------
# VehicleRoute + VehicleRouteStop cascade
# ---------------------------------------------------------------------------


def test_vehicle_route_stop_cascade_delete():
    """Deleting a VehicleRoute should cascade to its stops."""
    session = SessionLocal()
    try:
        depot = _depot(session, "d-cascade")
        v = _vehicle(session, "veh-cascade", "d-cascade")
        route = VehicleRoute(route_id="route-cascade", vehicle_id="veh-cascade")
        session.add(route)
        session.flush()

        for i in range(3):
            session.add(
                VehicleRouteStop(
                    route_id="route-cascade",
                    sequence=i + 1,
                    lat=35.0 + i * 0.01,
                    lon=-90.0,
                    window_start_min=480 + i * 10,
                    window_end_min=490 + i * 10,
                    delta_load=1 if i % 2 == 0 else -1,
                    stop_type="pickup" if i % 2 == 0 else "dropoff",
                )
            )
        session.commit()

        stop_count = session.execute(
            select(VehicleRouteStop).where(VehicleRouteStop.route_id == "route-cascade")
        ).scalars().all()
        assert len(stop_count) == 3

        # Delete the route — stops should cascade
        session.delete(route)
        session.commit()

        remaining = session.execute(
            select(VehicleRouteStop).where(VehicleRouteStop.route_id == "route-cascade")
        ).scalars().all()
        assert len(remaining) == 0
    finally:
        session.rollback()
        session.close()


def test_vehicle_route_default_status():
    session = SessionLocal()
    try:
        depot = _depot(session, "d-status")
        v = _vehicle(session, "veh-status", "d-status")
        route = VehicleRoute(route_id="route-status-check", vehicle_id="veh-status")
        session.add(route)
        session.commit()

        row = session.execute(
            select(VehicleRoute).where(VehicleRoute.route_id == "route-status-check")
        ).scalars().first()
        assert row.status == "active"
    finally:
        session.rollback()
        session.close()


# ---------------------------------------------------------------------------
# OnDemandTrip
# ---------------------------------------------------------------------------


def test_on_demand_trip_persists():
    session = SessionLocal()
    try:
        req = OnDemandRequest(
            request_id="req-trip-test",
            origin_lat=35.0,
            origin_lon=-90.0,
            destination_lat=35.1,
            destination_lon=-89.9,
            passengers=1,
        )
        session.add(req)
        session.flush()

        trip = OnDemandTrip(
            trip_id="trip-001",
            request_id="req-trip-test",
            vehicle_id="veh-x",
            status="assigned",
        )
        session.add(trip)
        session.commit()

        row = session.execute(
            select(OnDemandTrip).where(OnDemandTrip.trip_id == "trip-001")
        ).scalars().first()
        assert row is not None
        assert row.status == "assigned"
        assert row.vehicle_id == "veh-x"
    finally:
        session.rollback()
        session.close()

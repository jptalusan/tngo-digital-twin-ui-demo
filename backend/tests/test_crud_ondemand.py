"""Integration tests for on-demand CRUD operations.

These tests hit the test database and exercise:
- create_depot (atomic: depot + zones + vehicles + schedules)
- load_vehicle_states (service zone containment logic)
- create_request / persist_insertion
- summarize_fulfillment / summarize_all_requests
- _parse_time helper
"""

from __future__ import annotations

import pytest
from geoalchemy2 import WKTElement
from sqlalchemy import select

from app.crud import ondemand as ondemand_crud
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
from app.services import ondemand as ondemand_service


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# A simple WKT polygon that covers a Memphis-area bounding box
_MEMPHIS_POLYGON = (
    "POLYGON((-90.1 35.1, -90.1 35.2, -89.9 35.2, -89.9 35.1, -90.1 35.1))"
)
# A point inside the above polygon
_MEMPHIS_LAT = 35.15
_MEMPHIS_LON = -90.0
# A point outside the polygon
_OUTSIDE_LAT = 34.0
_OUTSIDE_LON = -88.0


def _build_depot_with_zone(session, depot_id: str, polygon_wkt: str | None = _MEMPHIS_POLYGON):
    """Create a depot + one service zone hexagon with an explicit polygon."""
    depot = Depot(depot_id=depot_id, name=depot_id, lat=_MEMPHIS_LAT, lon=_MEMPHIS_LON)
    session.add(depot)
    session.flush()

    if polygon_wkt:
        zone = OnDemandServiceZone(
            depot_id=depot_id,
            hex_id=f"hex-{depot_id}",
            h3_resolution=9,
            boundary=WKTElement(polygon_wkt, srid=4326),
        )
        session.add(zone)

    vehicle = OnDemandVehicle(
        vehicle_id=f"veh-{depot_id}",
        depot_id=depot_id,
        capacity=4,
    )
    session.add(vehicle)
    session.add(
        VehicleSchedule(
            vehicle_id=f"veh-{depot_id}",
            service_days="mon,tue,wed,thu,fri,sat,sun",
            start_time="05:00",
            end_time="23:00",
        )
    )
    session.flush()
    return depot, vehicle


# ---------------------------------------------------------------------------
# create_depot
# ---------------------------------------------------------------------------


def test_create_depot_atomically():
    session = SessionLocal()
    try:
        depot, vehicles = ondemand_crud.create_depot(
            session=session,
            lat=35.15,
            lon=-90.0,
            address="123 Test St",
            num_vehicles=2,
            capacity=6,
            hex_ids=["hex-aa", "hex-bb"],
            h3_resolution=9,
            hex_boundaries=[_MEMPHIS_POLYGON, _MEMPHIS_POLYGON],
        )
        assert depot.depot_id.startswith("depot-")
        assert depot.name == "123 Test St"
        assert len(vehicles) == 2
        assert all(v.capacity == 6 for v in vehicles)

        zones = session.execute(
            select(OnDemandServiceZone).where(OnDemandServiceZone.depot_id == depot.depot_id)
        ).scalars().all()
        assert len(zones) == 2

        for v in vehicles:
            schedule = session.execute(
                select(VehicleSchedule).where(VehicleSchedule.vehicle_id == v.vehicle_id)
            ).scalars().first()
            assert schedule is not None
            assert schedule.start_time == "05:00"
    finally:
        session.rollback()
        session.close()


def test_create_depot_no_address_uses_depot_id():
    session = SessionLocal()
    try:
        depot, _ = ondemand_crud.create_depot(
            session=session,
            lat=35.0,
            lon=-90.0,
            address=None,
            num_vehicles=1,
            capacity=4,
            hex_ids=[],
            h3_resolution=None,
            hex_boundaries=[],
        )
        assert depot.name == depot.depot_id
    finally:
        session.rollback()
        session.close()


# ---------------------------------------------------------------------------
# load_vehicle_states — service zone containment
# ---------------------------------------------------------------------------


def test_load_vehicle_states_origin_inside_zone():
    """Vehicle is eligible when the origin falls inside its service zone."""
    session = SessionLocal()
    try:
        _build_depot_with_zone(session, "d-inside", _MEMPHIS_POLYGON)
        session.commit()

        states = ondemand_crud.load_vehicle_states(
            session, origin_lat=_MEMPHIS_LAT, origin_lon=_MEMPHIS_LON
        )
        vehicle_ids = {s.vehicle_id for s in states}
        assert "veh-d-inside" in vehicle_ids
    finally:
        session.rollback()
        session.close()


def test_load_vehicle_states_origin_outside_zone():
    """Vehicle is NOT eligible when the origin is outside its service zone."""
    session = SessionLocal()
    try:
        _build_depot_with_zone(session, "d-outside", _MEMPHIS_POLYGON)
        session.commit()

        states = ondemand_crud.load_vehicle_states(
            session, origin_lat=_OUTSIDE_LAT, origin_lon=_OUTSIDE_LON
        )
        vehicle_ids = {s.vehicle_id for s in states}
        assert "veh-d-outside" not in vehicle_ids
    finally:
        session.rollback()
        session.close()


def test_load_vehicle_states_no_zone_is_open():
    """Depot without any service zone rows accepts all origins (open/unzoned)."""
    session = SessionLocal()
    try:
        _build_depot_with_zone(session, "d-open", polygon_wkt=None)
        session.commit()

        # Both inside and outside origins should see this vehicle
        for lat, lon in [(_MEMPHIS_LAT, _MEMPHIS_LON), (_OUTSIDE_LAT, _OUTSIDE_LON)]:
            states = ondemand_crud.load_vehicle_states(session, origin_lat=lat, origin_lon=lon)
            vehicle_ids = {s.vehicle_id for s in states}
            assert "veh-d-open" in vehicle_ids, f"Expected vehicle for lat={lat}, lon={lon}"
    finally:
        session.rollback()
        session.close()


def test_load_vehicle_states_skips_invalid_schedule():
    """Vehicle with start_time >= end_time is excluded."""
    session = SessionLocal()
    try:
        depot = Depot(depot_id="d-bad-sched", name="Bad Sched", lat=_MEMPHIS_LAT, lon=_MEMPHIS_LON)
        session.add(depot)
        session.flush()
        vehicle = OnDemandVehicle(vehicle_id="veh-bad-sched", depot_id="d-bad-sched", capacity=4)
        session.add(vehicle)
        # start_time == end_time — should be skipped
        session.add(
            VehicleSchedule(
                vehicle_id="veh-bad-sched",
                service_days="mon",
                start_time="08:00",
                end_time="08:00",
            )
        )
        session.commit()

        states = ondemand_crud.load_vehicle_states(
            session, origin_lat=_MEMPHIS_LAT, origin_lon=_MEMPHIS_LON
        )
        vehicle_ids = {s.vehicle_id for s in states}
        assert "veh-bad-sched" not in vehicle_ids
    finally:
        session.rollback()
        session.close()


# ---------------------------------------------------------------------------
# create_request
# ---------------------------------------------------------------------------


def test_create_request_returns_id():
    session = SessionLocal()
    try:
        req = ondemand_service.Request(
            request_id=None,
            origin_lat=35.1,
            origin_lon=-90.0,
            destination_lat=35.2,
            destination_lon=-89.9,
            passengers=1,
            pickup_window=ondemand_service.TimeWindow(start_min=480, end_min=510),
            dropoff_window=ondemand_service.TimeWindow(start_min=480, end_min=570),
        )
        request_id = ondemand_crud.create_request(session, req)
        assert request_id.startswith("req-")

        row = session.execute(
            select(OnDemandRequest).where(OnDemandRequest.request_id == request_id)
        ).scalars().first()
        assert row is not None
        assert row.passengers == 1
        assert row.pickup_window_start_min == 480
    finally:
        session.rollback()
        session.close()


def test_create_request_uses_provided_id():
    session = SessionLocal()
    try:
        req = ondemand_service.Request(
            request_id="explicit-id-001",
            origin_lat=35.1,
            origin_lon=-90.0,
            destination_lat=35.2,
            destination_lon=-89.9,
            passengers=2,
            pickup_window=ondemand_service.TimeWindow(start_min=480, end_min=510),
            dropoff_window=ondemand_service.TimeWindow(start_min=480, end_min=570),
        )
        request_id = ondemand_crud.create_request(session, req)
        assert request_id == "explicit-id-001"
    finally:
        session.rollback()
        session.close()


# ---------------------------------------------------------------------------
# persist_insertion
# ---------------------------------------------------------------------------


def test_persist_insertion_creates_route_and_stops():
    session = SessionLocal()
    try:
        depot = Depot(depot_id="d-persist", name="P", lat=35.0, lon=-90.0)
        session.add(depot)
        session.flush()
        session.add(OnDemandVehicle(vehicle_id="veh-persist", depot_id="d-persist", capacity=4))
        # OnDemandTrip has a FK to ondemand_request — the request row must exist first.
        session.add(OnDemandRequest(
            request_id="req-persist-1",
            origin_lat=35.1, origin_lon=-90.0,
            destination_lat=35.2, destination_lon=-89.9,
            passengers=1,
        ))
        session.flush()

        route = [
            ondemand_service.StopEvent(
                lat=35.1,
                lon=-90.0,
                window=ondemand_service.TimeWindow(start_min=480, end_min=510),
                delta_load=1,
                request_id="req-persist-1",
                stop_type="pickup",
            ),
            ondemand_service.StopEvent(
                lat=35.2,
                lon=-89.9,
                window=ondemand_service.TimeWindow(start_min=530, end_min=570),
                delta_load=-1,
                request_id="req-persist-1",
                stop_type="dropoff",
            ),
        ]
        ondemand_crud.persist_insertion(
            session,
            vehicle_id="veh-persist",
            request_id="req-persist-1",
            route=route,
            planned_times=[485, 540],
        )

        db_route = session.execute(
            select(VehicleRoute).where(
                VehicleRoute.vehicle_id == "veh-persist",
                VehicleRoute.status == "active",
            )
        ).scalars().first()
        assert db_route is not None

        stops = session.execute(
            select(VehicleRouteStop)
            .where(VehicleRouteStop.route_id == db_route.route_id)
            .order_by(VehicleRouteStop.sequence)
        ).scalars().all()
        assert len(stops) == 2
        assert stops[0].stop_type == "pickup"
        assert stops[1].stop_type == "dropoff"
        assert stops[0].planned_arrival_min == 485
        assert stops[1].planned_arrival_min == 540

        trip = session.execute(
            select(OnDemandTrip).where(OnDemandTrip.request_id == "req-persist-1")
        ).scalars().first()
        assert trip is not None
        assert trip.status == "assigned"
        assert trip.vehicle_id == "veh-persist"
    finally:
        session.rollback()
        session.close()


def test_persist_insertion_replaces_existing_stops():
    """A second insertion for the same vehicle should replace the route stops."""
    session = SessionLocal()
    try:
        depot = Depot(depot_id="d-replace", name="R", lat=35.0, lon=-90.0)
        session.add(depot)
        session.flush()
        session.add(OnDemandVehicle(vehicle_id="veh-replace", depot_id="d-replace", capacity=4))
        # Both request rows must exist before persist_insertion inserts OnDemandTrip rows.
        for req_id in ("req-r1", "req-r2"):
            session.add(OnDemandRequest(
                request_id=req_id,
                origin_lat=35.1, origin_lon=-90.0,
                destination_lat=35.2, destination_lon=-89.9,
                passengers=1,
            ))
        session.flush()

        def _route(req_id: str) -> list[ondemand_service.StopEvent]:
            return [
                ondemand_service.StopEvent(
                    lat=35.1,
                    lon=-90.0,
                    window=ondemand_service.TimeWindow(480, 510),
                    delta_load=1,
                    request_id=req_id,
                    stop_type="pickup",
                ),
                ondemand_service.StopEvent(
                    lat=35.2,
                    lon=-89.9,
                    window=ondemand_service.TimeWindow(530, 570),
                    delta_load=-1,
                    request_id=req_id,
                    stop_type="dropoff",
                ),
            ]

        ondemand_crud.persist_insertion(session, "veh-replace", "req-r1", _route("req-r1"), [485, 540])
        ondemand_crud.persist_insertion(session, "veh-replace", "req-r2", _route("req-r2") + _route("req-r2"), [485, 540, 600, 620])

        active_route = session.execute(
            select(VehicleRoute).where(
                VehicleRoute.vehicle_id == "veh-replace", VehicleRoute.status == "active"
            )
        ).scalars().first()
        stops = session.execute(
            select(VehicleRouteStop).where(VehicleRouteStop.route_id == active_route.route_id)
        ).scalars().all()
        # Second insertion had 4 stops (2 req × pickup+dropoff)
        assert len(stops) == 4
    finally:
        session.rollback()
        session.close()


# ---------------------------------------------------------------------------
# summarize_fulfillment
# ---------------------------------------------------------------------------


def test_summarize_fulfillment_complete():
    session = SessionLocal()
    try:
        depot = Depot(depot_id="d-fulfill", name="F", lat=35.0, lon=-90.0)
        session.add(depot)
        session.flush()
        session.add(OnDemandVehicle(vehicle_id="veh-fulfill", depot_id="d-fulfill", capacity=4))
        session.flush()

        route = VehicleRoute(route_id="route-fulfill", vehicle_id="veh-fulfill")
        session.add(route)
        session.flush()

        session.add(OnDemandRequest(
            request_id="req-f1",
            origin_lat=35.0, origin_lon=-90.0,
            destination_lat=35.1, destination_lon=-89.9,
            passengers=1,
        ))
        session.add(OnDemandTrip(
            trip_id="trip-f1", request_id="req-f1", vehicle_id="veh-fulfill", status="assigned"
        ))
        session.add_all([
            VehicleRouteStop(
                route_id="route-fulfill", sequence=1,
                lat=35.0, lon=-90.0,
                window_start_min=480, window_end_min=510,
                delta_load=1, stop_type="pickup", request_id="req-f1",
            ),
            VehicleRouteStop(
                route_id="route-fulfill", sequence=2,
                lat=35.1, lon=-89.9,
                window_start_min=530, window_end_min=570,
                delta_load=-1, stop_type="dropoff", request_id="req-f1",
            ),
        ])
        session.commit()

        total, fulfilled, unfulfilled = ondemand_crud.summarize_fulfillment(session, "veh-fulfill")
        assert total == 1
        assert fulfilled == 1
        assert unfulfilled == 0
    finally:
        session.rollback()
        session.close()


def test_summarize_fulfillment_empty_vehicle():
    session = SessionLocal()
    try:
        total, fulfilled, unfulfilled = ondemand_crud.summarize_fulfillment(session, "veh-nonexistent")
        assert total == 0
        assert fulfilled == 0
        assert unfulfilled == 0
    finally:
        session.close()


# ---------------------------------------------------------------------------
# _parse_time internal helper
# ---------------------------------------------------------------------------


def test_parse_time_normal():
    assert ondemand_crud._parse_time("08:30") == 8 * 60 + 30


def test_parse_time_midnight():
    assert ondemand_crud._parse_time("00:00") == 0


def test_parse_time_end_of_day():
    assert ondemand_crud._parse_time("23:59") == 23 * 60 + 59


def test_parse_time_malformed_returns_zero():
    assert ondemand_crud._parse_time("bad") == 0

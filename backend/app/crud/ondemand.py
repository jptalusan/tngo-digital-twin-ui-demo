from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from geoalchemy2 import WKTElement
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.ondemand import (
    Depot,
    OnDemandRequest,
    OnDemandTrip,
    Vehicle,
    VehicleRoute,
    VehicleRouteStop,
    VehicleSchedule,
)
from app.services import ondemand as ondemand_service


def load_vehicle_states(
    session: Session,
    origin_lat: float,
    origin_lon: float,
) -> list[ondemand_service.VehicleState]:
    point = WKTElement(f"POINT({origin_lon} {origin_lat})", srid=4326)
    query = (
        select(Vehicle, Depot)
        .join(Depot, Depot.depot_id == Vehicle.depot_id)
        .where((Depot.service_zone.is_(None)) | (Depot.service_zone.ST_Contains(point)))
    )
    rows = session.execute(query).all()

    vehicles: list[ondemand_service.VehicleState] = []
    for vehicle, _ in rows:
        schedules = (
            session.execute(
                select(VehicleSchedule).where(VehicleSchedule.vehicle_id == vehicle.vehicle_id)
            )
            .scalars()
            .all()
        )
        if not schedules:
            continue
        schedule = schedules[0]
        if _parse_time(schedule.start_time) >= _parse_time(schedule.end_time):
            continue

        route = _load_active_route(session, vehicle.vehicle_id)
        vehicles.append(
            ondemand_service.VehicleState(
                vehicle_id=vehicle.vehicle_id,
                capacity=vehicle.capacity,
                route=route,
            )
        )

    return vehicles


def select_depots_by_name(query: str):
    return select(Depot).where(Depot.name.ilike(f"%{query}%")).limit(10)


def create_request(
    session: Session,
    request: ondemand_service.Request,
) -> str:
    request_id = request.request_id or f"req-{uuid.uuid4().hex[:10]}"
    record = OnDemandRequest(
        request_id=request_id,
        origin_lat=request.origin_lat,
        origin_lon=request.origin_lon,
        destination_lat=request.destination_lat,
        destination_lon=request.destination_lon,
        passengers=request.passengers,
        pickup_window_start_min=request.pickup_window.start_min,
        pickup_window_end_min=request.pickup_window.end_min,
        dropoff_window_end_min=request.dropoff_window.end_min,
        requested_at=datetime.now(timezone.utc).isoformat(),
    )
    session.add(record)
    session.commit()
    return request_id


def persist_insertion(
    session: Session,
    vehicle_id: str,
    request_id: str,
    route: list[ondemand_service.StopEvent],
    planned_times: list[int],
) -> None:
    route_record = _get_or_create_route(session, vehicle_id)

    session.execute(
        delete(VehicleRouteStop).where(VehicleRouteStop.route_id == route_record.route_id)
    )

    stops = []
    for idx, stop in enumerate(route):
        planned_time = planned_times[idx] if idx < len(planned_times) else None
        stops.append(
            VehicleRouteStop(
                route_id=route_record.route_id,
                sequence=idx + 1,
                lat=stop.lat,
                lon=stop.lon,
                window_start_min=stop.window.start_min,
                window_end_min=stop.window.end_min,
                delta_load=stop.delta_load,
                stop_type=stop.stop_type or "unknown",
                request_id=stop.request_id,
                planned_arrival_min=planned_time,
                planned_departure_min=planned_time,
            )
        )

    session.add_all(stops)
    session.add(
        OnDemandTrip(
            trip_id=f"trip-{uuid.uuid4().hex[:10]}",
            request_id=request_id,
            vehicle_id=vehicle_id,
            status="assigned",
        )
    )
    session.commit()


def _load_active_route(session: Session, vehicle_id: str) -> list[ondemand_service.StopEvent]:
    route = (
        session.execute(
            select(VehicleRoute)
            .where(VehicleRoute.vehicle_id == vehicle_id, VehicleRoute.status == "active")
            .order_by(VehicleRoute.updated_at.desc().nullslast())
        )
        .scalars()
        .first()
    )
    if route is None:
        return []

    stops = (
        session.execute(
            select(VehicleRouteStop)
            .where(VehicleRouteStop.route_id == route.route_id)
            .order_by(VehicleRouteStop.sequence)
        )
        .scalars()
        .all()
    )

    return [
        ondemand_service.StopEvent(
            lat=stop.lat,
            lon=stop.lon,
            window=ondemand_service.TimeWindow(stop.window_start_min, stop.window_end_min),
            delta_load=stop.delta_load,
            request_id=stop.request_id,
            stop_type=stop.stop_type,
        )
        for stop in stops
    ]


def _get_or_create_route(session: Session, vehicle_id: str) -> VehicleRoute:
    route = (
        session.execute(
            select(VehicleRoute).where(
                VehicleRoute.vehicle_id == vehicle_id, VehicleRoute.status == "active"
            )
        )
        .scalars()
        .first()
    )
    if route is not None:
        return route

    route = VehicleRoute(route_id=f"route-{uuid.uuid4().hex[:10]}", vehicle_id=vehicle_id)
    session.add(route)
    session.commit()
    return route


def _parse_time(value: str) -> int:
    parts = value.split(":")
    if len(parts) < 2:
        return 0
    return int(parts[0]) * 60 + int(parts[1])

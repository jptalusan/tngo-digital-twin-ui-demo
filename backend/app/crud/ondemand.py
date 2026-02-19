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
    OnDemandServiceZone,
    OnDemandTrip,
    OnDemandVehicle,
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
    schedules_exist = (
        session.execute(select(VehicleSchedule.id).limit(1)).scalars().first() is not None
    )
    point = WKTElement(f"POINT({origin_lon} {origin_lat})", srid=4326)
    # A depot is eligible when it has no service zone rows at all (open/unzoned),
    # or when the origin point falls within any of its hex boundaries.
    depots_with_match = (
        select(OnDemandServiceZone.depot_id)
        .where(OnDemandServiceZone.boundary.ST_Contains(point))
    )
    depots_without_zones = (
        select(Depot.depot_id)
        .where(~Depot.depot_id.in_(select(OnDemandServiceZone.depot_id)))
    )
    eligible_depot_ids = depots_with_match.union(depots_without_zones).subquery()

    query = (
        select(OnDemandVehicle)
        .where(OnDemandVehicle.depot_id.in_(select(eligible_depot_ids)))
    )
    rows = session.execute(query).scalars().all()

    vehicles: list[ondemand_service.VehicleState] = []
    for vehicle in rows:
        if schedules_exist:
            schedules = (
                session.execute(
                    select(VehicleSchedule).where(
                        VehicleSchedule.vehicle_id == vehicle.vehicle_id
                    )
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


def load_active_route_with_times(
    session: Session, vehicle_id: str
) -> list[VehicleRouteStop]:
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

    return (
        session.execute(
            select(VehicleRouteStop)
            .where(VehicleRouteStop.route_id == route.route_id)
            .order_by(VehicleRouteStop.sequence)
        )
        .scalars()
        .all()
    )


def summarize_fulfillment(session: Session, vehicle_id: str) -> tuple[int, int, int]:
    assigned_ids = (
        session.execute(
            select(OnDemandTrip.request_id).where(OnDemandTrip.vehicle_id == vehicle_id)
        )
        .scalars()
        .all()
    )
    assigned_set = {req_id for req_id in assigned_ids if req_id}
    if not assigned_set:
        return 0, 0, 0

    stops = (
        session.execute(
            select(VehicleRouteStop)
            .where(VehicleRouteStop.request_id.in_(assigned_set))
        )
        .scalars()
        .all()
    )

    pickup_seen: set[str] = set()
    dropoff_seen: set[str] = set()
    for stop in stops:
        if not stop.request_id:
            continue
        if stop.stop_type == "pickup":
            pickup_seen.add(stop.request_id)
        elif stop.stop_type == "dropoff":
            dropoff_seen.add(stop.request_id)

    fulfilled = len(pickup_seen & dropoff_seen)
    total_assigned = len(assigned_set)
    unfulfilled = max(0, total_assigned - fulfilled)
    return total_assigned, fulfilled, unfulfilled


def summarize_all_requests(session: Session) -> tuple[int, int, int, int, int]:
    total_requests = session.execute(select(OnDemandRequest.request_id)).scalars().all()
    total_set = {req_id for req_id in total_requests if req_id}
    total_count = len(total_set)

    assigned_ids = session.execute(select(OnDemandTrip.request_id)).scalars().all()
    assigned_set = {req_id for req_id in assigned_ids if req_id}
    assigned_count = len(assigned_set)

    stops = (
        session.execute(
            select(VehicleRouteStop).where(VehicleRouteStop.request_id.in_(assigned_set))
        )
        .scalars()
        .all()
    )

    pickup_seen: set[str] = set()
    dropoff_seen: set[str] = set()
    for stop in stops:
        if not stop.request_id:
            continue
        if stop.stop_type == "pickup":
            pickup_seen.add(stop.request_id)
        elif stop.stop_type == "dropoff":
            dropoff_seen.add(stop.request_id)

    fulfilled = len(pickup_seen & dropoff_seen)
    unassigned = max(0, total_count - assigned_count)
    unfulfilled = max(0, assigned_count - fulfilled)
    return total_count, assigned_count, unassigned, fulfilled, unfulfilled


def create_depot(
    session: Session,
    lat: float,
    lon: float,
    address: Optional[str],
    num_vehicles: int,
    capacity: int,
    hex_ids: list[str],
    h3_resolution: Optional[int],
    hex_boundaries: list[str],  # WKT polygons, one per hex_id (same order)
) -> tuple[Depot, list[OnDemandVehicle]]:
    """Persist a new depot, its service zone hexagons, and its vehicles atomically."""
    depot_id = f"depot-{uuid.uuid4().hex[:10]}"
    name = address or depot_id

    depot = Depot(depot_id=depot_id, name=name, lat=lat, lon=lon, address=address)
    session.add(depot)
    session.flush()  # obtain depot.id so FKs resolve

    for hex_id, wkt in zip(hex_ids, hex_boundaries):
        session.add(
            OnDemandServiceZone(
                depot_id=depot_id,
                hex_id=hex_id,
                h3_resolution=h3_resolution,
                boundary=WKTElement(wkt, srid=4326) if wkt else None,
            )
        )

    new_vehicles: list[OnDemandVehicle] = []
    for _ in range(num_vehicles):
        vehicle_id = f"vehicle-{uuid.uuid4().hex[:10]}"
        v = OnDemandVehicle(vehicle_id=vehicle_id, depot_id=depot_id, capacity=capacity)
        session.add(v)
        new_vehicles.append(v)

    for vehicle in new_vehicles:
        session.add(
            VehicleSchedule(
                vehicle_id=vehicle.vehicle_id,
                service_days="mon,tue,wed,thu,fri,sat,sun",
                start_time="05:00",
                end_time="20:00",
            )
        )

    session.commit()
    session.refresh(depot)
    return depot, new_vehicles


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

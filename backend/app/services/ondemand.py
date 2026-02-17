from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import httpx

from app.core.config import settings
from app.services.planning import get_distance_m


@dataclass(frozen=True)
class TimeWindow:
    start_min: int
    end_min: int


@dataclass(frozen=True)
class StopEvent:
    lat: float
    lon: float
    window: TimeWindow
    delta_load: int
    request_id: Optional[str] = None
    stop_type: Optional[str] = None


@dataclass(frozen=True)
class VehicleState:
    vehicle_id: str
    capacity: int
    route: list[StopEvent]


@dataclass(frozen=True)
class Request:
    request_id: Optional[str]
    origin_lat: float
    origin_lon: float
    destination_lat: float
    destination_lon: float
    passengers: int
    pickup_window: TimeWindow
    dropoff_window: TimeWindow


@dataclass(frozen=True)
class InsertionResult:
    vehicle_id: str
    eta_minutes: int
    distance_km: float
    route: list[StopEvent]
    planned_times: list[int]
    note: str


def compute_route_distance_m(route: list[StopEvent]) -> float:
    if len(route) < 2:
        return 0.0
    total = 0.0
    for prev, curr in zip(route[:-1], route[1:]):
        total += _travel_distance_m(prev.lat, prev.lon, curr.lat, curr.lon)
    return total


def build_osrm_route_geometry(route: list[StopEvent]) -> tuple[Optional[str], Optional[float], Optional[float]]:
    if not settings.enable_osrm:
        return None, None, None
    if len(route) < 2:
        return None, None, None

    coords = ";".join(f"{stop.lon},{stop.lat}" for stop in route)
    url = f"{settings.osrm_url}/route/v1/driving/{coords}"
    params = {"overview": "full", "geometries": "polyline"}
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
    except Exception:
        return None, None, None

    routes = data.get("routes") or []
    if not routes:
        return None, None, None
    route_info = routes[0]
    return (
        route_info.get("geometry"),
        route_info.get("distance"),
        route_info.get("duration"),
    )


def build_osrm_leg_geometry(
    origin: StopEvent, destination: StopEvent
) -> tuple[Optional[str], Optional[float], Optional[float]]:
    if not settings.enable_osrm:
        return None, None, None
    url = f"{settings.osrm_url}/route/v1/driving/{origin.lon},{origin.lat};{destination.lon},{destination.lat}"
    params = {"overview": "full", "geometries": "polyline"}
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
    except Exception:
        return None, None, None

    routes = data.get("routes") or []
    if not routes:
        return None, None, None
    route_info = routes[0]
    return (
        route_info.get("geometry"),
        route_info.get("distance"),
        route_info.get("duration"),
    )


def estimate_direct_leg(
    origin_lat: float,
    origin_lon: float,
    destination_lat: float,
    destination_lon: float,
) -> tuple[float, int, Optional[str]]:
    geometry = None
    distance_m = _travel_distance_m(origin_lat, origin_lon, destination_lat, destination_lon)
    duration_s = int(round(_travel_time_min(origin_lat, origin_lon, destination_lat, destination_lon) * 60))
    if settings.enable_osrm:
        geom, dist, dur = build_osrm_leg_geometry(
            StopEvent(origin_lat, origin_lon, TimeWindow(0, 0), 0),
            StopEvent(destination_lat, destination_lon, TimeWindow(0, 0), 0),
        )
        if geom:
            geometry = geom
        if dist is not None:
            distance_m = float(dist)
        if dur is not None:
            duration_s = int(round(float(dur)))
    return distance_m, duration_s, geometry


def _default_speed_kmph() -> float:
    return float(getattr(settings, "default_on_demand_speed_kmph", 30.0))


def _osrm_table(lat1: float, lon1: float, lat2: float, lon2: float) -> tuple[Optional[float], Optional[float]]:
    if not settings.enable_osrm:
        return None, None
    url = f"{settings.osrm_url}/table/v1/driving/{lon1},{lat1};{lon2},{lat2}"
    params = {"annotations": "duration,distance"}
    try:
        with httpx.Client(timeout=5.0) as client:
            resp = client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
    except Exception:
        return None, None

    durations = data.get("durations") or []
    distances = data.get("distances") or []
    duration_s = None
    distance_m = None
    if len(durations) > 0 and len(durations[0]) > 1:
        value = durations[0][1]
        duration_s = None if value is None else float(value)
    if len(distances) > 0 and len(distances[0]) > 1:
        value = distances[0][1]
        distance_m = None if value is None else float(value)
    return duration_s, distance_m


def _travel_time_min(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    duration_s, _ = _osrm_table(lat1, lon1, lat2, lon2)
    if duration_s is not None:
        return duration_s / 60
    distance_m = get_distance_m(lat1, lon1, lat2, lon2)
    speed_mps = (_default_speed_kmph() * 1000) / 3600
    return distance_m / max(speed_mps, 0.1) / 60


def _travel_distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    _, distance_m = _osrm_table(lat1, lon1, lat2, lon2)
    if distance_m is not None:
        return distance_m
    return get_distance_m(lat1, lon1, lat2, lon2)


def _simulate_route(
    route: list[StopEvent],
    start_min: int,
    capacity: int,
) -> Optional[list[int]]:
    times: list[int] = []
    current_time = start_min
    current_load = 0

    prev_lat = None
    prev_lon = None

    for stop in route:
        if prev_lat is not None:
            travel_min = _travel_time_min(prev_lat, prev_lon, stop.lat, stop.lon)
            current_time += int(round(travel_min))

        if current_time < stop.window.start_min:
            current_time = stop.window.start_min
        if current_time > stop.window.end_min:
            return None

        current_load += stop.delta_load
        if current_load < 0 or current_load > capacity:
            return None

        times.append(current_time)
        prev_lat, prev_lon = stop.lat, stop.lon

    return times


def _build_stop_events(request: Request) -> tuple[StopEvent, StopEvent]:
    pickup = StopEvent(
        lat=request.origin_lat,
        lon=request.origin_lon,
        window=request.pickup_window,
        delta_load=request.passengers,
        request_id=request.request_id,
        stop_type="pickup",
    )
    dropoff = StopEvent(
        lat=request.destination_lat,
        lon=request.destination_lon,
        window=request.dropoff_window,
        delta_load=-request.passengers,
        request_id=request.request_id,
        stop_type="dropoff",
    )
    return pickup, dropoff


def find_best_insertion(
    vehicles: list[VehicleState],
    request: Request,
    start_min: int,
) -> Optional[InsertionResult]:
    pickup, dropoff = _build_stop_events(request)
    best: Optional[InsertionResult] = None

    for vehicle in vehicles:
        base_route = vehicle.route
        if not base_route:
            candidate_route = [pickup, dropoff]
            times = _simulate_route(candidate_route, start_min, vehicle.capacity)
            if times is None:
                continue
            eta_minutes = max(0, times[0] - start_min)
            distance_m = _travel_distance_m(
                request.origin_lat,
                request.origin_lon,
                request.destination_lat,
                request.destination_lon,
            )
            result = InsertionResult(
                vehicle_id=vehicle.vehicle_id,
                eta_minutes=eta_minutes,
                distance_km=round(distance_m / 1000, 2),
                route=candidate_route,
                planned_times=times,
                note="Direct insertion into empty route",
            )
            best = _choose_best(best, result)
            continue

        for i in range(len(base_route) + 1):
            for j in range(i + 1, len(base_route) + 2):
                candidate_route = base_route[:i] + [pickup] + base_route[i:j - 1] + [dropoff] + base_route[j - 1 :]
                times = _simulate_route(candidate_route, start_min, vehicle.capacity)
                if times is None:
                    continue
                eta_minutes = max(0, times[0] - start_min)
                distance_m = _travel_distance_m(
                    request.origin_lat,
                    request.origin_lon,
                    request.destination_lat,
                    request.destination_lon,
                )
                result = InsertionResult(
                    vehicle_id=vehicle.vehicle_id,
                    eta_minutes=eta_minutes,
                    distance_km=round(distance_m / 1000, 2),
                    route=candidate_route,
                    planned_times=times,
                    note="Inserted pickup/dropoff into existing route",
                )
                best = _choose_best(best, result)

    return best


def _choose_best(current: Optional[InsertionResult], candidate: InsertionResult) -> InsertionResult:
    if current is None:
        return candidate
    if candidate.eta_minutes < current.eta_minutes:
        return candidate
    if candidate.eta_minutes == current.eta_minutes and candidate.distance_km < current.distance_km:
        return candidate
    return current

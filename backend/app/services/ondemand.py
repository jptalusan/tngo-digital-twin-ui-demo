from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

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


def _default_speed_kmph() -> float:
    return float(getattr(settings, "default_on_demand_speed_kmph", 30.0))


def _travel_time_min(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    distance_m = get_distance_m(lat1, lon1, lat2, lon2)
    speed_mps = (_default_speed_kmph() * 1000) / 3600
    return distance_m / max(speed_mps, 0.1) / 60


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
            distance_m = get_distance_m(
                request.origin_lat, request.origin_lon, request.destination_lat, request.destination_lon
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
                distance_m = get_distance_m(
                    request.origin_lat, request.origin_lon, request.destination_lat, request.destination_lon
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

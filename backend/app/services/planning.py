from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.gtfs import Stop, StopTime, Trip


@dataclass(frozen=True)
class StopCandidate:
    stop: Stop
    distance_m: float
    walk_duration_s: int


@dataclass(frozen=True)
class TransitCandidate:
    trip_id: str
    route_id: str
    from_stop: Stop
    to_stop: Stop
    depart_time_min: int
    arrive_time_min: int
    wait_time_s: int
    in_vehicle_s: int


@dataclass(frozen=True)
class LegCandidate:
    mode: str
    from_stop_id: Optional[str]
    to_stop_id: Optional[str]
    distance_m: Optional[float]
    duration_s: int
    route_id: Optional[str] = None
    trip_id: Optional[str] = None


@dataclass(frozen=True)
class ItineraryCandidate:
    legs: list[LegCandidate]
    total_duration_s: int
    total_walk_m: float
    total_wait_s: int
    total_invehicle_s: int
    score: float
    score_breakdown: dict


@dataclass(frozen=True)
class FixedLineConstraints:
    max_walk_meters: int
    max_wait_minutes: int
    max_invehicle_minutes: int
    max_total_minutes: int
    score_weight_total_minutes: float
    score_weight_wait_minutes: float
    score_weight_walk_meters: float


@dataclass(frozen=True)
class FixedLineInputs:
    origin_lat: float
    origin_lon: float
    destination_lat: float
    destination_lon: float
    depart_at_min: int
    constraints: FixedLineConstraints


def find_nearby_stops(
    session: Session,
    lat: float,
    lon: float,
    max_distance_m: float,
) -> list[StopCandidate]:
    if max_distance_m <= 0:
        return []

    dlat = max_distance_m / 111_320
    dlon = max_distance_m / (111_320 * max(0.1, abs(_cos_deg(lat))))

    stops = (
        session.execute(
            select(Stop).where(
                Stop.lat.is_not(None),
                Stop.lon.is_not(None),
                Stop.lat.between(lat - dlat, lat + dlat),
                Stop.lon.between(lon - dlon, lon + dlon),
            )
        )
        .scalars()
        .all()
    )

    candidates: list[StopCandidate] = []
    for stop in stops:
        if stop.lat is None or stop.lon is None:
            continue
        dist = get_distance_m(lat, lon, stop.lat, stop.lon)
        if dist <= max_distance_m:
            walk_duration = int(dist / settings.default_walk_speed_mps)
            candidates.append(StopCandidate(stop=stop, distance_m=dist, walk_duration_s=walk_duration))

    return candidates




def find_transit_candidates(
    session: Session,
    access_stops: list[StopCandidate],
    egress_stops: list[StopCandidate],
    depart_at_min: int,
    max_wait_minutes: int,
    max_invehicle_minutes: int,
) -> list[TransitCandidate]:
    if not access_stops or not egress_stops:
        return []

    access_ids = {candidate.stop.stop_id for candidate in access_stops}
    egress_ids = {candidate.stop.stop_id for candidate in egress_stops}

    access_stop_times = (
        session.execute(select(StopTime).where(StopTime.stop_id.in_(access_ids)))
        .scalars()
        .all()
    )
    egress_stop_times = (
        session.execute(select(StopTime).where(StopTime.stop_id.in_(egress_ids)))
        .scalars()
        .all()
    )

    egress_by_trip: dict[str, list[StopTime]] = {}
    for st in egress_stop_times:
        egress_by_trip.setdefault(st.trip_id, []).append(st)

    trip_ids = {st.trip_id for st in access_stop_times}
    trips = (
        session.execute(select(Trip).where(Trip.trip_id.in_(trip_ids)))
        .scalars()
        .all()
    )
    trip_map = {trip.trip_id: trip for trip in trips}

    access_stop_map = {candidate.stop.stop_id: candidate.stop for candidate in access_stops}
    egress_stop_map = {candidate.stop.stop_id: candidate.stop for candidate in egress_stops}

    candidates: list[TransitCandidate] = []
    for access_st in access_stop_times:
        if access_st.trip_id not in egress_by_trip:
            continue
        if access_st.stop_sequence is None:
            continue

        depart_min = _parse_time_min(access_st.departure_time or access_st.arrival_time)
        if depart_min is None or depart_min < depart_at_min:
            continue

        wait_min = depart_min - depart_at_min
        if wait_min > max_wait_minutes:
            continue

        for egress_st in egress_by_trip[access_st.trip_id]:
            if egress_st.stop_sequence is None:
                continue
            if egress_st.stop_sequence <= access_st.stop_sequence:
                continue

            arrive_min = _parse_time_min(egress_st.arrival_time or egress_st.departure_time)
            if arrive_min is None:
                continue

            in_vehicle_min = arrive_min - depart_min
            if in_vehicle_min <= 0 or in_vehicle_min > max_invehicle_minutes:
                continue

            trip = trip_map.get(access_st.trip_id)
            if trip is None:
                continue

            from_stop = access_stop_map.get(access_st.stop_id)
            to_stop = egress_stop_map.get(egress_st.stop_id)
            if from_stop is None or to_stop is None:
                continue

            candidates.append(
                TransitCandidate(
                    trip_id=access_st.trip_id,
                    route_id=trip.route_id,
                    from_stop=from_stop,
                    to_stop=to_stop,
                    depart_time_min=depart_min,
                    arrive_time_min=arrive_min,
                    wait_time_s=wait_min * 60,
                    in_vehicle_s=in_vehicle_min * 60,
                )
            )

    return candidates


def build_fixed_line_itineraries(
    session: Session,
    inputs: FixedLineInputs,
) -> list[ItineraryCandidate]:
    access = find_nearby_stops(
        session, inputs.origin_lat, inputs.origin_lon, inputs.constraints.max_walk_meters
    )
    egress = find_nearby_stops(
        session, inputs.destination_lat, inputs.destination_lon, inputs.constraints.max_walk_meters
    )

    candidates = find_transit_candidates(
        session,
        access,
        egress,
        inputs.depart_at_min,
        inputs.constraints.max_wait_minutes,
        inputs.constraints.max_invehicle_minutes,
    )

    itineraries: list[ItineraryCandidate] = []
    for candidate in candidates:
        walk_access = next((c for c in access if c.stop.stop_id == candidate.from_stop.stop_id), None)
        walk_egress = next((c for c in egress if c.stop.stop_id == candidate.to_stop.stop_id), None)

        walk_access_s = walk_access.walk_duration_s if walk_access else 0
        walk_egress_s = walk_egress.walk_duration_s if walk_egress else 0
        total_s = walk_access_s + candidate.wait_time_s + candidate.in_vehicle_s + walk_egress_s
        if total_s > inputs.constraints.max_total_minutes * 60:
            continue

        legs: list[LegCandidate] = []
        if walk_access_s > 0:
            legs.append(
                LegCandidate(
                    mode="walk",
                    from_stop_id=None,
                    to_stop_id=candidate.from_stop.stop_id,
                    distance_m=walk_access.distance_m if walk_access else None,
                    duration_s=walk_access_s,
                )
            )

        legs.append(
            LegCandidate(
                mode="transit",
                from_stop_id=candidate.from_stop.stop_id,
                to_stop_id=candidate.to_stop.stop_id,
                distance_m=None,
                duration_s=candidate.in_vehicle_s,
                route_id=candidate.route_id,
                trip_id=candidate.trip_id,
            )
        )

        if walk_egress_s > 0:
            legs.append(
                LegCandidate(
                    mode="walk",
                    from_stop_id=candidate.to_stop.stop_id,
                    to_stop_id=None,
                    distance_m=walk_egress.distance_m if walk_egress else None,
                    duration_s=walk_egress_s,
                )
            )

        total_walk_m = (walk_access.distance_m if walk_access else 0.0) + (
            walk_egress.distance_m if walk_egress else 0.0
        )
        total_minutes = total_s / 60
        score = (
            total_minutes * inputs.constraints.score_weight_total_minutes
            + (candidate.wait_time_s / 60) * inputs.constraints.score_weight_wait_minutes
            + total_walk_m * inputs.constraints.score_weight_walk_meters
        )
        score_breakdown = {
            "total_minutes": total_minutes,
            "wait_minutes": candidate.wait_time_s / 60,
            "walk_meters": total_walk_m,
            "weight_total_minutes": inputs.constraints.score_weight_total_minutes,
            "weight_wait_minutes": inputs.constraints.score_weight_wait_minutes,
            "weight_walk_meters": inputs.constraints.score_weight_walk_meters,
            "score": score,
        }

        itineraries.append(
            ItineraryCandidate(
                legs=legs,
                total_duration_s=total_s,
                total_walk_m=total_walk_m,
                total_wait_s=candidate.wait_time_s,
                total_invehicle_s=candidate.in_vehicle_s,
                score=score,
                score_breakdown=score_breakdown,
            )
        )

    return sorted(itineraries, key=lambda item: item.score)[:3]


def _parse_time_min(value: Optional[str]) -> Optional[int]:
    if not value:
        return None
    parts = value.split(":")
    if len(parts) < 2:
        return None
    try:
        hours = int(parts[0])
        minutes = int(parts[1])
        seconds = int(parts[2]) if len(parts) > 2 else 0
    except ValueError:
        return None
    return hours * 60 + minutes + (1 if seconds >= 30 else 0)


def get_distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    if settings.enable_osrm:
        # Placeholder for OSRM integration (fall back to haversine for now).
        return _haversine_m(lat1, lon1, lat2, lon2)
    return _haversine_m(lat1, lon1, lat2, lon2)


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    import math

    rad = math.pi / 180
    dlat = (lat2 - lat1) * rad
    dlon = (lon2 - lon1) * rad
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1 * rad) * math.cos(lat2 * rad) * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return 6371000.0 * c


def _cos_deg(deg: float) -> float:
    import math

    return math.cos(deg * math.pi / 180)

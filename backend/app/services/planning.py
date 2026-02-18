from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from geoalchemy2.functions import ST_DWithin, ST_Transform, ST_X, ST_Y
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.logging.config import get_logger
from app.models.gtfs import Stop, StopTime, Trip
from app.crud import gtfs as gtfs_crud

_SRID_M = 3857


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
    min_transfer_minutes: int


@dataclass(frozen=True)
class FixedLineInputs:
    origin_lat: float
    origin_lon: float
    destination_lat: float
    destination_lon: float
    depart_at_min: int
    transfer_limit: int
    active_service_ids: Optional[set[str]]
    constraints: FixedLineConstraints
    extra_access_stop_ids: Optional[set[str]] = None
    extra_egress_stop_ids: Optional[set[str]] = None


def find_nearby_stops(
    session: Session,
    lat: float,
    lon: float,
    max_distance_m: float,
    extra_stop_ids: Optional[set[str]] = None,
) -> list[StopCandidate]:
    if max_distance_m <= 0:
        return []

    origin_wgs = func.ST_SetSRID(func.ST_MakePoint(lon, lat), 4326)
    origin_m = func.ST_Transform(origin_wgs, _SRID_M)

    rows = (
        session.execute(
            select(
                Stop,
                ST_X(Stop.location).label("stop_lon"),
                ST_Y(Stop.location).label("stop_lat"),
            ).where(
                Stop.location.is_not(None),
                ST_DWithin(
                    ST_Transform(Stop.location, _SRID_M),
                    origin_m,
                    max_distance_m,
                ),
            )
        )
        .all()
    )

    candidates: list[StopCandidate] = []
    for row in rows:
        stop, stop_lon, stop_lat = row
        dist = get_distance_m(lat, lon, stop_lat, stop_lon)
        walk_duration = int(dist / settings.default_walk_speed_mps)
        candidates.append(StopCandidate(stop=stop, distance_m=dist, walk_duration_s=walk_duration))

    if extra_stop_ids:
        extra_rows = (
            session.execute(
                select(
                    Stop,
                    ST_X(Stop.location).label("stop_lon"),
                    ST_Y(Stop.location).label("stop_lat"),
                ).where(
                    Stop.stop_id.in_(extra_stop_ids),
                    Stop.location.is_not(None),
                )
            )
            .all()
        )
        for row in extra_rows:
            stop, stop_lon, stop_lat = row
            candidates.append(StopCandidate(stop=stop, distance_m=0.0, walk_duration_s=0))

    # Deduplicate by stop_id, prefer shorter walk duration
    dedup: dict[str, StopCandidate] = {}
    for candidate in candidates:
        key = candidate.stop.stop_id
        if key not in dedup or candidate.walk_duration_s < dedup[key].walk_duration_s:
            dedup[key] = candidate

    return list(dedup.values())




def find_transit_candidates(
    session: Session,
    access_stops: list[StopCandidate],
    egress_stops: list[StopCandidate],
    depart_at_min: int,
    max_wait_minutes: int,
    max_invehicle_minutes: int,
    active_trip_ids: Optional[set[str]] = None,
) -> list[TransitCandidate]:
    if not access_stops or not egress_stops:
        return []

    access_ids = {candidate.stop.stop_id for candidate in access_stops}
    egress_ids = {candidate.stop.stop_id for candidate in egress_stops}

    time_start = _min_to_time(depart_at_min)
    time_end = _min_to_time(depart_at_min + max_wait_minutes)

    access_query = (
        select(StopTime)
        .join(Trip, StopTime.trip_id == Trip.trip_id)
        .where(StopTime.stop_id.in_(access_ids))
        .where(
            func.coalesce(StopTime.departure_time, StopTime.arrival_time).between(
                time_start, time_end
            )
        )
    )
    if active_trip_ids is not None:
        access_query = access_query.where(StopTime.trip_id.in_(active_trip_ids))

    access_stop_times = session.execute(access_query).scalars().all()

    trip_ids = {st.trip_id for st in access_stop_times}
    if not trip_ids:
        return []

    egress_query = select(StopTime).where(
        StopTime.stop_id.in_(egress_ids), StopTime.trip_id.in_(trip_ids)
    )
    egress_stop_times = session.execute(egress_query).scalars().all()

    egress_by_trip: dict[str, list[StopTime]] = {}
    for st in egress_stop_times:
        egress_by_trip.setdefault(st.trip_id, []).append(st)

    trips = gtfs_crud.load_trips_for_ids(session, trip_ids)
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
    active_trip_ids: Optional[set[str]] = None
    if inputs.active_service_ids is not None:
        trips = gtfs_crud.load_trips_for_service_ids(session, inputs.active_service_ids)
        active_trip_ids = {trip.trip_id for trip in trips}

    access = find_nearby_stops(
        session,
        inputs.origin_lat,
        inputs.origin_lon,
        inputs.constraints.max_walk_meters,
        extra_stop_ids=inputs.extra_access_stop_ids,
    )
    egress = find_nearby_stops(
        session,
        inputs.destination_lat,
        inputs.destination_lon,
        inputs.constraints.max_walk_meters,
        extra_stop_ids=inputs.extra_egress_stop_ids,
    )

    candidates = find_transit_candidates(
        session,
        access,
        egress,
        inputs.depart_at_min,
        inputs.constraints.max_wait_minutes,
        inputs.constraints.max_invehicle_minutes,
        active_trip_ids=active_trip_ids,
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

    if inputs.transfer_limit >= 1:
        itineraries.extend(
            _build_itineraries_with_transfers(
                session,
                access,
                egress,
                inputs.depart_at_min,
                inputs.constraints,
                max_transfers=inputs.transfer_limit,
                active_trip_ids=active_trip_ids,
            )
        )

    return sorted(itineraries, key=lambda item: item.score)[:3]


def _build_itineraries_with_transfers(
    session: Session,
    access: list[StopCandidate],
    egress: list[StopCandidate],
    depart_at_min: int,
    constraints: FixedLineConstraints,
    active_trip_ids: Optional[set[str]] = None,
    max_transfers: int = 1,
) -> list[ItineraryCandidate]:
    if not access or not egress:
        return []

    access_ids = {candidate.stop.stop_id for candidate in access}
    egress_ids = {candidate.stop.stop_id for candidate in egress}

    time_start = _min_to_time(depart_at_min)
    time_end = _min_to_time(depart_at_min + constraints.max_total_minutes)

    access_query = (
        select(StopTime)
        .join(Trip, StopTime.trip_id == Trip.trip_id)
        .where(StopTime.stop_id.in_(access_ids))
        .where(
            func.coalesce(StopTime.departure_time, StopTime.arrival_time).between(
                time_start, time_end
            )
        )
    )
    if active_trip_ids is not None:
        access_query = access_query.where(StopTime.trip_id.in_(active_trip_ids))

    access_stop_times = session.execute(access_query).scalars().all()

    trip_ids = {st.trip_id for st in access_stop_times}
    if active_trip_ids is not None:
        trip_ids |= active_trip_ids
    if not trip_ids:
        return []

    egress_query = select(StopTime).where(
        StopTime.stop_id.in_(egress_ids),
        StopTime.trip_id.in_(trip_ids),
    )
    egress_stop_times = session.execute(egress_query).scalars().all()

    trip_ids = {st.trip_id for st in access_stop_times} | {
        st.trip_id for st in egress_stop_times
    }
    trip_stop_times = gtfs_crud.load_stop_times_for_trips(session, trip_ids)

    trip_map = {trip.trip_id: trip for trip in gtfs_crud.load_trips_for_ids(session, trip_ids)}

    stops_by_trip: dict[str, list[StopTime]] = {}
    for st in trip_stop_times:
        stops_by_trip.setdefault(st.trip_id, []).append(st)

    for st_list in stops_by_trip.values():
        st_list.sort(key=lambda st: st.stop_sequence or 0)

    access_walk_map = {candidate.stop.stop_id: candidate for candidate in access}
    egress_walk_map = {candidate.stop.stop_id: candidate for candidate in egress}

    stop_index: dict[str, list[StopTime]] = {}
    for st in trip_stop_times:
        dep_min = _parse_time_min(st.departure_time or st.arrival_time)
        if dep_min is None:
            continue
        stop_index.setdefault(st.stop_id, []).append(st)

    for st_list in stop_index.values():
        st_list.sort(key=lambda st: _parse_time_min(st.departure_time or st.arrival_time) or 0)

    # Build nearby stop map for transfer between different stop_ids
    stop_ids = set(stop_index.keys())
    coord_rows = (
        session.execute(
            select(
                Stop.stop_id,
                ST_Y(Stop.location).label("stop_lat"),
                ST_X(Stop.location).label("stop_lon"),
            ).where(
                Stop.stop_id.in_(stop_ids),
                Stop.location.is_not(None),
            )
        )
        .all()
    )
    stop_coords = {row.stop_id: (row.stop_lat, row.stop_lon) for row in coord_rows}
    transfer_radius = settings.transfer_walk_radius_m
    transfer_radius_lat = transfer_radius / 111_320
    transfer_radius_lon_factor = 1 / 111_320

    stop_items = [
        (stop_id, coord[0], coord[1])
        for stop_id, coord in stop_coords.items()
    ]

    nearby_stops: dict[str, list[tuple[str, float]]] = {}
    for stop_id, lat, lon in stop_items:
        candidates = []
        for other_id, o_lat, o_lon in stop_items:
            if other_id == stop_id:
                continue
            if abs(o_lat - lat) > transfer_radius_lat:
                continue
            if abs(o_lon - lon) > transfer_radius_lon_factor * max(0.1, abs(_cos_deg(lat))) * transfer_radius:
                continue
            dist = get_distance_m(lat, lon, o_lat, o_lon)
            if dist <= transfer_radius:
                candidates.append((other_id, dist))
        nearby_stops[stop_id] = candidates

    itineraries: list[ItineraryCandidate] = []
    debug_traces: list[str] = []
    MAX_STATES = 2000
    states = []

    for candidate in access:
        start_time = depart_at_min + int(candidate.walk_duration_s / 60)
        states.append(
            {
                "stop_id": candidate.stop.stop_id,
                "time_min": start_time,
                "legs": [
                    LegCandidate(
                        mode="walk",
                        from_stop_id=None,
                        to_stop_id=candidate.stop.stop_id,
                        distance_m=candidate.distance_m,
                        duration_s=candidate.walk_duration_s,
                    )
                ]
                if candidate.walk_duration_s > 0
                else [],
                "total_wait_s": 0,
                "total_invehicle_s": 0,
                "trips_taken": 0,
                "total_walk_m": candidate.distance_m,
            }
        )

    visited = set()
    while states and len(itineraries) < 25:
        state = states.pop(0)
        key = (state["stop_id"], state["time_min"], state["trips_taken"])
        if key in visited:
            continue
        visited.add(key)
        if len(visited) > MAX_STATES:
            break

        stop_id = state["stop_id"]
        time_min = state["time_min"]
        trips_taken = state["trips_taken"]
        if trips_taken - 1 > max_transfers:
            continue

        # Check egress
        if stop_id in egress_walk_map:
            walk_egress = egress_walk_map[stop_id]
            walk_egress_s = walk_egress.walk_duration_s
            total_s = (
                (time_min - depart_at_min) * 60
                + walk_egress_s
            )
            if total_s <= constraints.max_total_minutes * 60:
                legs = list(state["legs"])
                if not any(leg.mode == "transit" for leg in legs):
                    continue
                if walk_egress_s > 0:
                    legs.append(
                        LegCandidate(
                            mode="walk",
                            from_stop_id=stop_id,
                            to_stop_id=None,
                            distance_m=walk_egress.distance_m,
                            duration_s=walk_egress_s,
                        )
                    )
                total_walk_m = state["total_walk_m"] + walk_egress.distance_m
                score = (
                    (total_s / 60) * constraints.score_weight_total_minutes
                    + (state["total_wait_s"] / 60) * constraints.score_weight_wait_minutes
                    + total_walk_m * constraints.score_weight_walk_meters
                )
                score_breakdown = {
                    "total_minutes": total_s / 60,
                    "wait_minutes": state["total_wait_s"] / 60,
                    "walk_meters": total_walk_m,
                    "weight_total_minutes": constraints.score_weight_total_minutes,
                    "weight_wait_minutes": constraints.score_weight_wait_minutes,
                    "weight_walk_meters": constraints.score_weight_walk_meters,
                    "score": score,
                }
                itineraries.append(
                    ItineraryCandidate(
                        legs=legs,
                        total_duration_s=total_s,
                        total_walk_m=total_walk_m,
                        total_wait_s=state["total_wait_s"],
                        total_invehicle_s=state["total_invehicle_s"],
                        score=score,
                        score_breakdown=score_breakdown,
                    )
                )
                debug_traces.append(
                    f"egress reached stop={stop_id} time={time_min} trips={trips_taken} legs={len(legs)}"
                )

        # Transfer-walk between nearby stops (different stop_ids)
        for other_id, dist_m in nearby_stops.get(stop_id, []):
            walk_s = int(dist_m / settings.default_walk_speed_mps)
            new_time = time_min + int(round(walk_s / 60))
            new_legs = list(state["legs"])
            if walk_s > 0:
                new_legs.append(
                    LegCandidate(
                        mode="transfer",
                        from_stop_id=stop_id,
                        to_stop_id=other_id,
                        distance_m=dist_m,
                        duration_s=walk_s,
                    )
                )
            states.append(
                {
                    "stop_id": other_id,
                    "time_min": new_time,
                    "legs": new_legs,
                    "total_wait_s": state["total_wait_s"],
                    "total_invehicle_s": state["total_invehicle_s"],
                    "trips_taken": trips_taken,
                    "total_walk_m": state["total_walk_m"] + dist_m,
                }
            )
            if len(debug_traces) < 20:
                debug_traces.append(
                    f"transfer-walk {stop_id} -> {other_id} ({int(dist_m)}m) time={new_time}"
                )

        # Board trips from this stop
        for st in stop_index.get(stop_id, []):
            depart_min = _parse_time_min(st.departure_time or st.arrival_time)
            if depart_min is None:
                continue
            if depart_min < time_min:
                continue
            wait_min = depart_min - time_min
            if wait_min > constraints.max_wait_minutes:
                continue

            trip_stops = stops_by_trip.get(st.trip_id, [])
            if not trip_stops:
                continue

            for down_st in trip_stops:
                if down_st.stop_sequence is None or st.stop_sequence is None:
                    continue
                if down_st.stop_sequence <= st.stop_sequence:
                    continue
                arrive_min = _parse_time_min(down_st.arrival_time or down_st.departure_time)
                if arrive_min is None or arrive_min <= depart_min:
                    continue
                in_vehicle_min = arrive_min - depart_min
                if in_vehicle_min > constraints.max_invehicle_minutes:
                    continue

                trip = trip_map.get(st.trip_id)
                if trip is None:
                    continue

                new_legs = list(state["legs"])
                if wait_min > 0 and trips_taken > 0:
                    new_legs.append(
                        LegCandidate(
                            mode="transfer",
                            from_stop_id=stop_id,
                            to_stop_id=stop_id,
                            distance_m=None,
                            duration_s=wait_min * 60,
                        )
                    )
                new_legs.append(
                    LegCandidate(
                        mode="transit",
                        from_stop_id=st.stop_id,
                        to_stop_id=down_st.stop_id,
                        distance_m=None,
                        duration_s=in_vehicle_min * 60,
                        route_id=trip.route_id,
                        trip_id=trip.trip_id,
                    )
                )
                states.append(
                    {
                        "stop_id": down_st.stop_id,
                        "time_min": arrive_min,
                        "legs": new_legs,
                        "total_wait_s": state["total_wait_s"] + wait_min * 60,
                        "total_invehicle_s": state["total_invehicle_s"] + in_vehicle_min * 60,
                        "trips_taken": trips_taken + 1,
                        "total_walk_m": state["total_walk_m"],
                    }
                )
                if len(debug_traces) < 20:
                    debug_traces.append(
                        f"board trip={st.trip_id} from={st.stop_id} to={down_st.stop_id} dep={depart_min} arr={arrive_min}"
                    )

    if debug_traces:
        logger.info("search trace: %s", debug_traces)
    return itineraries


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


def _min_to_time(total_min: int) -> str:
    hours = total_min // 60
    minutes = total_min % 60
    return f"{hours:02d}:{minutes:02d}:00"


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
logger = get_logger("fixed_line_search")

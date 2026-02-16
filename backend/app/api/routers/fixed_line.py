from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db import get_session
from app.schemas import planning as schemas
from app.services import planning as planning_service
from app.services import hubs
from app.logging.config import get_logger
from app.crud import gtfs as gtfs_crud
from app.services.planning import get_distance_m
import httpx

logger = get_logger("fixed_line")

router = APIRouter(tags=["fixed-line"])


def _fill_leg_metrics(
    session: Session,
    origin: list[float],
    destination: list[float],
    legs: list[schemas.Leg],
) -> None:
    stop_ids: set[str] = set()
    for leg in legs:
        if leg.from_stop_id:
            stop_ids.add(leg.from_stop_id)
        if leg.to_stop_id:
            stop_ids.add(leg.to_stop_id)

    stop_map = {
        stop.stop_id: (stop.lat, stop.lon)
        for stop in gtfs_crud.load_stops_by_ids(session, stop_ids)
        if stop.lat is not None and stop.lon is not None
    }

    def _coords_for_leg(
        leg: schemas.Leg,
    ) -> tuple[tuple[float, float] | None, tuple[float, float] | None]:
        if leg.from_stop_id is None and leg.to_stop_id is None:
            return None, None
        if leg.from_stop_id is None and leg.to_stop_id:
            to_coords = stop_map.get(leg.to_stop_id)
            if to_coords is None:
                return None, None
            return (origin[0], origin[1]), to_coords
        if leg.to_stop_id is None and leg.from_stop_id:
            from_coords = stop_map.get(leg.from_stop_id)
            if from_coords is None:
                return None, None
            return from_coords, (destination[0], destination[1])
        if leg.from_stop_id and leg.to_stop_id:
            from_coords = stop_map.get(leg.from_stop_id)
            to_coords = stop_map.get(leg.to_stop_id)
            if from_coords is None or to_coords is None:
                return None, None
            return from_coords, to_coords
        return None, None

    brt_speed_mps = settings.default_brt_speed_kmph * 1000 / 3600
    def _osrm_leg_geometry(
        from_lat: float, from_lon: float, to_lat: float, to_lon: float
    ) -> tuple[Optional[str], Optional[float], Optional[float]]:
        if not settings.enable_osrm:
            return None, None, None
        url = f"{settings.osrm_url}/route/v1/driving/{from_lon},{from_lat};{to_lon},{to_lat}"
        params = {"overview": "full", "geometries": "polyline"}
        try:
            with httpx.Client(timeout=8.0) as client:
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

    for leg in legs:
        if leg.distance_m is None or leg.duration_s is None:
            from_coords, to_coords = _coords_for_leg(leg)
            if from_coords is None or to_coords is None:
                continue
            if leg.distance_m is None:
                leg.distance_m = round(
                    get_distance_m(from_coords[0], from_coords[1], to_coords[0], to_coords[1]),
                    2,
                )
            if leg.duration_s is None and leg.distance_m is not None:
                if leg.mode == "walk":
                    leg.duration_s = int(leg.distance_m / settings.default_walk_speed_mps)
                elif leg.route_id == "BOC_BRT":
                    leg.duration_s = int(leg.distance_m / brt_speed_mps)

        if leg.geometry is None:
            from_coords, to_coords = _coords_for_leg(leg)
            if from_coords is None or to_coords is None:
                continue
            geom, dist, dur = _osrm_leg_geometry(
                from_coords[0], from_coords[1], to_coords[0], to_coords[1]
            )
            if geom:
                leg.geometry = geom
            if leg.distance_m is None and dist is not None:
                leg.distance_m = round(dist, 2)
            if leg.duration_s is None and dur is not None:
                leg.duration_s = int(round(dur))


def _decode_polyline(polyline: str) -> list[tuple[float, float]]:
    coords: list[tuple[float, float]] = []
    index = 0
    lat = 0
    lon = 0
    length = len(polyline)
    while index < length:
        shift = 0
        result = 0
        while True:
            if index >= length:
                break
            b = ord(polyline[index]) - 63
            index += 1
            result |= (b & 0x1F) << shift
            shift += 5
            if b < 0x20:
                break
        dlat = ~(result >> 1) if (result & 1) else (result >> 1)
        lat += dlat

        shift = 0
        result = 0
        while True:
            if index >= length:
                break
            b = ord(polyline[index]) - 63
            index += 1
            result |= (b & 0x1F) << shift
            shift += 5
            if b < 0x20:
                break
        dlon = ~(result >> 1) if (result & 1) else (result >> 1)
        lon += dlon

        coords.append((lat / 1e5, lon / 1e5))
    return coords


def _encode_polyline(coords: list[tuple[float, float]]) -> str:
    def _encode_value(value: int) -> str:
        value = ~(value << 1) if value < 0 else (value << 1)
        chunks = []
        while value >= 0x20:
            chunks.append(chr((0x20 | (value & 0x1F)) + 63))
            value >>= 5
        chunks.append(chr(value + 63))
        return "".join(chunks)

    result = []
    last_lat = 0
    last_lon = 0
    for lat, lon in coords:
        ilat = int(round(lat * 1e5))
        ilon = int(round(lon * 1e5))
        result.append(_encode_value(ilat - last_lat))
        result.append(_encode_value(ilon - last_lon))
        last_lat = ilat
        last_lon = ilon
    return "".join(result)


def _aggregate_geometry(legs: list[schemas.Leg]) -> Optional[str]:
    merged: list[tuple[float, float]] = []
    for leg in legs:
        if not leg.geometry:
            continue
        try:
            points = _decode_polyline(leg.geometry)
        except Exception:
            continue
        if not points:
            continue
        if not merged:
            merged.extend(points)
            continue
        if merged[-1] == points[0]:
            merged.extend(points[1:])
        else:
            merged.extend(points)
    if not merged:
        return None
    return _encode_polyline(merged)


@router.post(
    "/plan/fixed-line",
    response_model=schemas.FixedLineResponse,
    summary="Plan fixed-line itinerary",
    description="Plan a fixed-line itinerary using GTFS schedules and walking access/egress.",
)
def plan_fixed_line(
    payload: schemas.FixedLineRequest,
    session: Session = Depends(get_session),
) -> schemas.FixedLineResponse:
    if payload.depart_at_min is not None and payload.arrive_by_min is not None:
        raise HTTPException(status_code=400, detail="Use depart_at_min or arrive_by_min, not both.")

    agency_timezone = gtfs_crud.get_agency_timezone(session)
    if payload.agency_timezone and agency_timezone and payload.agency_timezone != agency_timezone:
        raise HTTPException(
            status_code=400,
            detail=f"agency_timezone mismatch. GTFS={agency_timezone}, request={payload.agency_timezone}",
        )

    service_date = payload.service_date
    if service_date is None and agency_timezone:
        try:
            now = datetime.now(ZoneInfo(agency_timezone))
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        service_date = now.strftime("%Y%m%d")

    active_service_ids = (
        gtfs_crud.get_active_service_ids(session, service_date) if service_date else None
    )

    constraints = planning_service.FixedLineConstraints(
        max_walk_meters=payload.max_walk_meters,
        max_wait_minutes=payload.max_wait_minutes or settings.default_max_wait_minutes,
        max_invehicle_minutes=payload.max_invehicle_minutes
        or settings.default_max_invehicle_minutes,
        max_total_minutes=payload.max_total_minutes or settings.default_max_total_minutes,
        score_weight_total_minutes=payload.score_weight_total_minutes
        or settings.score_weight_total_minutes,
        score_weight_wait_minutes=payload.score_weight_wait_minutes
        or settings.score_weight_wait_minutes,
        score_weight_walk_meters=payload.score_weight_walk_meters
        or settings.score_weight_walk_meters,
        min_transfer_minutes=settings.default_min_transfer_minutes,
    )
    depart_at_min = payload.depart_at_min
    if depart_at_min is None and payload.arrive_by_min is not None:
        depart_at_min = max(0, payload.arrive_by_min - constraints.max_total_minutes)

    if payload.boc_request:
        ingress = gtfs_crud.find_nearest_stop_by_prefix(
            session,
            hubs.BOC_PREFIX,
            payload.origin[0],
            payload.origin[1],
            settings.boc_hub_search_m,
        )
        egress = gtfs_crud.find_nearest_stop_by_prefix(
            session,
            hubs.BOC_PREFIX,
            payload.destination[0],
            payload.destination[1],
            settings.boc_hub_search_m,
        )
        if ingress is None or egress is None:
            return schemas.FixedLineResponse(
                itineraries=[],
                note="BOC request: no BOC ingress/egress stop found within search radius.",
            )

        logger.info(
            "boc_request ingress=%s egress=%s",
            ingress.stop_id,
            egress.stop_id,
        )

        inputs = planning_service.FixedLineInputs(
            origin_lat=payload.origin[0],
            origin_lon=payload.origin[1],
            destination_lat=ingress.lat or payload.origin[0],
            destination_lon=ingress.lon or payload.origin[1],
            depart_at_min=depart_at_min or 0,
            transfer_limit=payload.transfer_limit or settings.default_transfer_limit,
            active_service_ids=active_service_ids,
            constraints=constraints,
            extra_access_stop_ids=None,
            extra_egress_stop_ids={ingress.stop_id},
        )

        first_leg_candidates = planning_service.build_fixed_line_itineraries(session, inputs)
        if not first_leg_candidates:
            return schemas.FixedLineResponse(
                itineraries=[],
                note="BOC request: no fixed-line path to BOC ingress stop.",
            )

        first = first_leg_candidates[0]
        legs = [
            schemas.Leg(
                mode=leg.mode,
                from_stop_id=leg.from_stop_id,
                to_stop_id=leg.to_stop_id,
                distance_m=leg.distance_m,
                duration_s=leg.duration_s,
                route_id=leg.route_id,
                trip_id=leg.trip_id,
            )
            for leg in first.legs
        ]

        _fill_leg_metrics(
            session,
            payload.origin,
            [ingress.lat or payload.origin[0], ingress.lon or payload.origin[1]],
            legs,
        )

        brt_leg = schemas.Leg(
            mode="transit",
            from_stop_id=ingress.stop_id,
            to_stop_id=egress.stop_id,
            distance_m=None,
            duration_s=None,
            route_id="BOC_BRT",
            trip_id=None,
        )
        legs.append(brt_leg)

        walk_m = get_distance_m(
            egress.lat or payload.destination[0],
            egress.lon or payload.destination[1],
            payload.destination[0],
            payload.destination[1],
        )
        walk_s = int(walk_m / settings.default_walk_speed_mps)
        walk_leg = None
        if walk_s > 0:
            walk_leg = schemas.Leg(
                mode="walk",
                from_stop_id=egress.stop_id,
                to_stop_id=None,
                distance_m=round(walk_m, 2),
                duration_s=walk_s,
            )
            legs.append(walk_leg)

        leg_subset = [brt_leg]
        if walk_leg is not None:
            leg_subset.append(walk_leg)
        _fill_leg_metrics(session, payload.origin, payload.destination, leg_subset)
        total_walk_m = first.total_walk_m + walk_m
        total_duration_s = first.total_duration_s + walk_s
        score = schemas.ScoreBreakdown(
            total_minutes=round(total_duration_s / 60, 4),
            wait_minutes=round(first.total_wait_s / 60, 4),
            walk_meters=round(total_walk_m, 2),
            weight_total_minutes=constraints.score_weight_total_minutes,
            weight_wait_minutes=constraints.score_weight_wait_minutes,
            weight_walk_meters=constraints.score_weight_walk_meters,
            score=round(
                (total_duration_s / 60) * constraints.score_weight_total_minutes
                + (first.total_wait_s / 60) * constraints.score_weight_wait_minutes
                + total_walk_m * constraints.score_weight_walk_meters,
                4,
            ),
        )

        itinerary = schemas.Itinerary(
            legs=legs,
            total_duration_s=total_duration_s,
            total_walk_m=total_walk_m,
            total_wait_s=first.total_wait_s,
            total_invehicle_s=first.total_invehicle_s,
            geometry=_aggregate_geometry(legs),
            score=score,
        )

        return schemas.FixedLineResponse(
            itineraries=[itinerary],
            note="BOC request: manual pipeline (origin->BOC ingress->BOC egress->walk).",
        )

    inputs = planning_service.FixedLineInputs(
        origin_lat=payload.origin[0],
        origin_lon=payload.origin[1],
        destination_lat=payload.destination[0],
        destination_lon=payload.destination[1],
        depart_at_min=depart_at_min or 0,
        transfer_limit=payload.transfer_limit or settings.default_transfer_limit,
        active_service_ids=active_service_ids,
        constraints=constraints,
        extra_access_stop_ids=None,
        extra_egress_stop_ids=None,
    )

    itinerary_candidates = planning_service.build_fixed_line_itineraries(session, inputs)
    itineraries: list[schemas.Itinerary] = []
    for candidate in itinerary_candidates:
        legs = [
            schemas.Leg(
                mode=leg.mode,
                from_stop_id=leg.from_stop_id,
                to_stop_id=leg.to_stop_id,
                distance_m=leg.distance_m,
                duration_s=leg.duration_s,
                route_id=leg.route_id,
                trip_id=leg.trip_id,
            )
            for leg in candidate.legs
        ]
        _fill_leg_metrics(session, payload.origin, payload.destination, legs)
        itineraries.append(
            schemas.Itinerary(
                legs=legs,
                total_duration_s=candidate.total_duration_s,
                total_walk_m=candidate.total_walk_m,
                total_wait_s=candidate.total_wait_s,
                total_invehicle_s=candidate.total_invehicle_s,
                geometry=_aggregate_geometry(legs),
                score=schemas.ScoreBreakdown(
                    total_minutes=round(candidate.score_breakdown["total_minutes"], 4),
                    wait_minutes=round(candidate.score_breakdown["wait_minutes"], 4),
                    walk_meters=round(candidate.score_breakdown["walk_meters"], 2),
                    weight_total_minutes=candidate.score_breakdown["weight_total_minutes"],
                    weight_wait_minutes=candidate.score_breakdown["weight_wait_minutes"],
                    weight_walk_meters=candidate.score_breakdown["weight_walk_meters"],
                    score=round(candidate.score_breakdown["score"], 4),
                ),
            )
        )

    note = "Rule-based itinerary selection using stop distance and time constraints."
    return schemas.FixedLineResponse(itineraries=itineraries, note=note)

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_session
from app.schemas import planning as schemas
from app.services import ondemand as ondemand_service
from app.crud import ondemand as ondemand_crud
from app.core.config import settings

router = APIRouter(tags=["on-demand"])


@router.post(
    "/plan/on-demand",
    response_model=schemas.OnDemandResponse,
    summary="Plan on-demand trip",
    description="Assign an on-demand vehicle using insertion heuristic and persist the updated route.",
)
def plan_on_demand(
    payload: schemas.OnDemandRequest,
    session: Session = Depends(get_session),
) -> schemas.OnDemandResponse:
    pickup_start = payload.pickup_window_start_min or 0
    pickup_end = payload.pickup_window_end_min or (pickup_start + 30)
    dropoff_end = payload.dropoff_window_end_min or (pickup_start + 90)

    request_id = f"req-{uuid.uuid4().hex[:10]}"
    request = ondemand_service.Request(
        request_id=request_id,
        origin_lat=payload.origin[0],
        origin_lon=payload.origin[1],
        destination_lat=payload.destination[0],
        destination_lon=payload.destination[1],
        passengers=payload.passengers,
        pickup_window=ondemand_service.TimeWindow(pickup_start, pickup_end),
        dropoff_window=ondemand_service.TimeWindow(pickup_start, dropoff_end),
    )

    ondemand_crud.create_request(session, request)
    vehicles = ondemand_crud.load_vehicle_states(session, request.origin_lat, request.origin_lon)
    result = ondemand_service.find_best_insertion(vehicles, request, start_min=pickup_start)

    weight_total = payload.score_weight_total_minutes or settings.score_weight_total_minutes
    weight_wait = payload.score_weight_wait_minutes or settings.score_weight_wait_minutes
    weight_walk = payload.score_weight_walk_meters or settings.score_weight_walk_meters

    if result is None:
        score = schemas.ScoreBreakdown(
            total_minutes=0.0,
            wait_minutes=0.0,
            walk_meters=0.0,
            weight_total_minutes=weight_total,
            weight_wait_minutes=weight_wait,
            weight_walk_meters=weight_walk,
            score=0.0,
        )
        return schemas.OnDemandResponse(
            vehicle_id="",
            eta_minutes=0,
            distance_km=0.0,
            total_duration_s=0,
            total_wait_s=0,
            total_invehicle_s=0,
            total_walk_m=0.0,
            total_transit_distance_m=0.0,
            total_vehicle_distance_m=0.0,
            itineraries=[
                schemas.Itinerary(
                    itinerary_id="ondemand-1",
                    legs=[],
                    total_duration_s=0,
                    total_walk_m=0.0,
                    total_wait_s=0,
                    total_invehicle_s=0,
                    total_transit_distance_m=0.0,
                    total_vehicle_distance_m=0.0,
                    geometry=None,
                    score=score,
                )
            ],
            score=score,
            note="No feasible vehicle found for the requested windows.",
        )

    ondemand_crud.persist_insertion(
        session,
        result.vehicle_id,
        request_id,
        result.route,
        result.planned_times,
    )

    pickup_time = None
    dropoff_time = None
    for stop, planned_min in zip(result.route, result.planned_times):
        if stop.request_id != request_id:
            continue
        if stop.stop_type == "pickup":
            pickup_time = planned_min
        elif stop.stop_type == "dropoff":
            dropoff_time = planned_min

    if pickup_time is None:
        pickup_time = pickup_start
    if dropoff_time is None:
        dropoff_time = pickup_time

    total_wait_s = max(0, pickup_time - pickup_start) * 60
    total_invehicle_s = max(0, dropoff_time - pickup_time) * 60
    total_duration_s = max(0, dropoff_time - pickup_start) * 60

    score = schemas.ScoreBreakdown(
        total_minutes=round(total_duration_s / 60, 4),
        wait_minutes=round(total_wait_s / 60, 4),
        walk_meters=0.0,
        weight_total_minutes=weight_total,
        weight_wait_minutes=weight_wait,
        weight_walk_meters=weight_walk,
        score=round(
            (total_duration_s / 60) * weight_total
            + (total_wait_s / 60) * weight_wait
            + 0.0 * weight_walk,
            4,
        ),
    )

    distance_m, duration_s, geometry = ondemand_service.estimate_direct_leg(
        payload.origin[0], payload.origin[1], payload.destination[0], payload.destination[1]
    )

    return schemas.OnDemandResponse(
        vehicle_id=result.vehicle_id,
        eta_minutes=result.eta_minutes,
        distance_km=result.distance_km,
        total_duration_s=total_duration_s,
        total_wait_s=total_wait_s,
        total_invehicle_s=total_invehicle_s,
        total_walk_m=0.0,
        total_transit_distance_m=round(distance_m, 2),
        total_vehicle_distance_m=round(distance_m, 2),
        itineraries=[
            schemas.Itinerary(
                itinerary_id="ondemand-1",
                legs=[
                    schemas.Leg(
                        mode="on-demand",
                        from_stop_id=None,
                        to_stop_id=None,
                        distance_m=round(distance_m, 2),
                        duration_s=duration_s,
                        geometry=geometry,
                        route_id=None,
                        trip_id=None,
                    )
                ],
                total_duration_s=total_duration_s,
                total_walk_m=0.0,
                total_wait_s=total_wait_s,
                total_invehicle_s=total_invehicle_s,
                total_transit_distance_m=round(distance_m, 2),
                total_vehicle_distance_m=round(distance_m, 2),
                geometry=geometry,
                score=score,
            )
        ],
        score=score,
        note=result.note,
    )


@router.post(
    "/plan/private-vehicle",
    response_model=schemas.PrivateVehicleResponse,
    summary="Plan private vehicle trip",
    description="Return a point-to-point private vehicle itinerary using OSRM routing.",
)
def plan_private_vehicle(
    payload: schemas.PrivateVehicleRequest,
    session: Session = Depends(get_session),
) -> schemas.PrivateVehicleResponse:
    weight_total = payload.score_weight_total_minutes or settings.score_weight_total_minutes
    weight_wait = payload.score_weight_wait_minutes or settings.score_weight_wait_minutes
    weight_walk = payload.score_weight_walk_meters or settings.score_weight_walk_meters

    distance_m, duration_s, geometry = ondemand_service.estimate_direct_leg(
        payload.origin[0],
        payload.origin[1],
        payload.destination[0],
        payload.destination[1],
    )

    score = schemas.ScoreBreakdown(
        total_minutes=round(duration_s / 60, 4),
        wait_minutes=0.0,
        walk_meters=0.0,
        weight_total_minutes=weight_total,
        weight_wait_minutes=weight_wait,
        weight_walk_meters=weight_walk,
        score=round((duration_s / 60) * weight_total, 4),
    )

    itinerary = schemas.Itinerary(
        itinerary_id="private-1",
        legs=[
            schemas.Leg(
                mode="private",
                from_stop_id=None,
                to_stop_id=None,
                distance_m=round(distance_m, 2),
                duration_s=duration_s,
                geometry=geometry,
                route_id=None,
                trip_id=None,
            )
        ],
        total_duration_s=duration_s,
        total_walk_m=0.0,
        total_wait_s=0,
        total_invehicle_s=duration_s,
        total_transit_distance_m=round(distance_m, 2),
        total_vehicle_distance_m=round(distance_m, 2),
        geometry=geometry,
        score=score,
    )

    return schemas.PrivateVehicleResponse(
        best_itinerary=itinerary.itinerary_id,
        total_duration_s=itinerary.total_duration_s,
        total_wait_s=itinerary.total_wait_s,
        total_invehicle_s=itinerary.total_invehicle_s,
        total_walk_m=itinerary.total_walk_m,
        total_transit_distance_m=round(distance_m, 2),
        total_vehicle_distance_m=round(distance_m, 2),
        score=score,
        itineraries=[itinerary],
        note="Private vehicle OSRM route.",
    )


@router.post(
    "/on-demand/evaluate",
    response_model=schemas.OnDemandEvaluateResponse,
    summary="Evaluate on-demand vehicle schedule",
    description="Evaluate the active on-demand schedule for a vehicle and return aggregate metrics.",
)
def evaluate_on_demand(
    payload: schemas.OnDemandEvaluateRequest,
    session: Session = Depends(get_session),
) -> schemas.OnDemandEvaluateResponse:
    stops = ondemand_crud.load_active_route_with_times(session, payload.vehicle_id)
    if not stops:
        raise HTTPException(status_code=404, detail="No active route found for vehicle.")

    if any(stop.planned_arrival_min is None for stop in stops):
        raise HTTPException(
            status_code=400,
            detail="Active route has no planned times. Insert at least one request first.",
        )

    pickup_by_request = {}
    dropoff_by_request = {}
    route_events = []
    for stop in stops:
        if stop.lat is not None and stop.lon is not None:
            route_events.append(
                ondemand_service.StopEvent(
                    lat=stop.lat,
                    lon=stop.lon,
                    window=ondemand_service.TimeWindow(0, 0),
                    delta_load=0,
                )
            )
        if stop.request_id:
            if stop.stop_type == "pickup":
                pickup_by_request[stop.request_id] = stop
            elif stop.stop_type == "dropoff":
                dropoff_by_request[stop.request_id] = stop

    total_distance_m = ondemand_service.compute_route_distance_m(route_events)

    total_wait_s = 0
    total_invehicle_s = 0
    for request_id, pickup in pickup_by_request.items():
        dropoff = dropoff_by_request.get(request_id)
        if dropoff is None:
            continue
        wait_min = max(0, pickup.planned_arrival_min - (pickup.window_start_min or 0))
        in_vehicle_min = max(0, dropoff.planned_arrival_min - pickup.planned_arrival_min)
        total_wait_s += wait_min * 60
        total_invehicle_s += in_vehicle_min * 60

    first_time = stops[0].planned_arrival_min or 0
    last_time = stops[-1].planned_arrival_min or first_time
    total_duration_s = max(0, last_time - first_time) * 60

    weight_total = payload.score_weight_total_minutes or settings.score_weight_total_minutes
    weight_wait = payload.score_weight_wait_minutes or settings.score_weight_wait_minutes
    weight_walk = payload.score_weight_walk_meters or settings.score_weight_walk_meters

    score = schemas.ScoreBreakdown(
        total_minutes=round(total_duration_s / 60, 4),
        wait_minutes=round(total_wait_s / 60, 4),
        walk_meters=0.0,
        weight_total_minutes=weight_total,
        weight_wait_minutes=weight_wait,
        weight_walk_meters=weight_walk,
        score=round(
            (total_duration_s / 60) * weight_total + (total_wait_s / 60) * weight_wait,
            4,
        ),
    )

    return schemas.OnDemandEvaluateResponse(
        vehicle_id=payload.vehicle_id,
        stop_count=len(stops),
        total_duration_s=total_duration_s,
        total_wait_s=total_wait_s,
        total_invehicle_s=total_invehicle_s,
        total_distance_m=round(total_distance_m, 2),
        score=score,
        note="Active route evaluation.",
    )


@router.post(
    "/on-demand/fulfillment",
    response_model=schemas.OnDemandFulfillmentResponse,
    summary="Summarize on-demand fulfillment",
    description="Return fulfilled vs unfulfilled assigned requests for a vehicle.",
)
def fulfillment_on_demand(
    payload: schemas.OnDemandFulfillmentRequest,
    session: Session = Depends(get_session),
) -> schemas.OnDemandFulfillmentResponse:
    total_assigned, fulfilled, unfulfilled = ondemand_crud.summarize_fulfillment(
        session, payload.vehicle_id
    )
    return schemas.OnDemandFulfillmentResponse(
        vehicle_id=payload.vehicle_id,
        total_assigned=total_assigned,
        fulfilled=fulfilled,
        unfulfilled=unfulfilled,
        note="Fulfillment computed from assigned trips and route stops.",
    )


@router.get(
    "/on-demand/summary",
    response_model=schemas.OnDemandSummaryResponse,
    summary="Summarize all on-demand requests",
    description="Return totals and percentages for all on-demand requests.",
)
def summary_on_demand(
    session: Session = Depends(get_session),
) -> schemas.OnDemandSummaryResponse:
    (
        total_count,
        assigned_count,
        unassigned_count,
        fulfilled_count,
        unfulfilled_count,
    ) = ondemand_crud.summarize_all_requests(session)

    assigned_pct = round((assigned_count / total_count) * 100, 2) if total_count else 0.0
    fulfilled_pct = round((fulfilled_count / total_count) * 100, 2) if total_count else 0.0

    return schemas.OnDemandSummaryResponse(
        total_requests=total_count,
        assigned_requests=assigned_count,
        unassigned_requests=unassigned_count,
        fulfilled_requests=fulfilled_count,
        unfulfilled_requests=unfulfilled_count,
        assigned_pct=assigned_pct,
        fulfilled_pct=fulfilled_pct,
        note="Summary computed from on-demand requests, trips, and route stops.",
    )


@router.post(
    "/on-demand/manifest",
    response_model=schemas.OnDemandManifestResponse,
    summary="Generate on-demand OSRM manifest",
    description="Generate a route geometry for the active schedule of a vehicle.",
)
def manifest_on_demand(
    payload: schemas.OnDemandManifestRequest,
    session: Session = Depends(get_session),
) -> schemas.OnDemandManifestResponse:
    stops = ondemand_crud.load_active_route_with_times(session, payload.vehicle_id)
    if not stops:
        raise HTTPException(status_code=404, detail="No active route found for vehicle.")

    route_events = []
    manifest_stops: list[schemas.OnDemandManifestStop] = []
    manifest_legs: list[schemas.OnDemandManifestLeg] = []
    for stop in stops:
        if stop.lat is None or stop.lon is None:
            continue
        route_events.append(
            ondemand_service.StopEvent(
                lat=stop.lat,
                lon=stop.lon,
                window=ondemand_service.TimeWindow(0, 0),
                delta_load=0,
            )
        )
        manifest_stops.append(
            schemas.OnDemandManifestStop(
                sequence=stop.sequence,
                lat=stop.lat,
                lon=stop.lon,
                stop_type=stop.stop_type,
                request_id=stop.request_id,
                window_start_min=stop.window_start_min,
                window_end_min=stop.window_end_min,
                planned_arrival_min=stop.planned_arrival_min,
                planned_departure_min=stop.planned_departure_min,
            )
        )

    geometry, distance_m, duration_s = ondemand_service.build_osrm_route_geometry(route_events)

    for idx, (prev, curr) in enumerate(zip(route_events[:-1], route_events[1:])):
        leg_geom, leg_dist, leg_dur = ondemand_service.build_osrm_leg_geometry(prev, curr)
        prev_stop = manifest_stops[idx]
        curr_stop = manifest_stops[idx + 1]
        manifest_legs.append(
            schemas.OnDemandManifestLeg(
                mode="on-demand",
                from_stop_id=None,
                to_stop_id=None,
                from_sequence=prev_stop.sequence,
                to_sequence=curr_stop.sequence,
                from_lat=prev.lat,
                from_lon=prev.lon,
                to_lat=curr.lat,
                to_lon=curr.lon,
                geometry=leg_geom,
                distance_m=None if leg_dist is None else round(leg_dist, 2),
                duration_s=None if leg_dur is None else int(round(leg_dur)),
                route_id=None,
                trip_id=None,
            )
        )

    note = "OSRM route generated from active route stops."
    if geometry is None:
        note = "OSRM route unavailable. Check OSRM service or route stops."

    return schemas.OnDemandManifestResponse(
        vehicle_id=payload.vehicle_id,
        stop_count=len(route_events),
        stops=manifest_stops,
        legs=manifest_legs,
        geometry=geometry,
        distance_m=None if distance_m is None else round(distance_m, 2),
        duration_s=None if duration_s is None else round(duration_s, 2),
        note=note,
    )

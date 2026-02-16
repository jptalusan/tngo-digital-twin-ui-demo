from __future__ import annotations

import math
import random
import uuid
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.config import settings
from datetime import datetime
from zoneinfo import ZoneInfo
from fastapi import HTTPException
from app.db import get_session
from app.schemas import planning as schemas
from app.services import planning as planning_service
from app.services import ondemand as ondemand_service
from app.crud import ondemand as ondemand_crud
from app.crud import gtfs as gtfs_crud

router = APIRouter(tags=["planning"])


@router.get("/autocomplete", response_model=list[schemas.AutocompleteResult])
def autocomplete(
    query: str = Query(min_length=1),
    session: Session = Depends(get_session),
) -> list[schemas.AutocompleteResult]:
    stop_results = session.execute(gtfs_crud.select_stops_by_name(query)).scalars().all()
    depot_results = session.execute(ondemand_crud.select_depots_by_name(query)).scalars().all()

    results: list[schemas.AutocompleteResult] = []
    for stop in stop_results:
        if stop.lat is None or stop.lon is None:
            continue
        results.append(
            schemas.AutocompleteResult(
                id=stop.stop_id,
                name=stop.name or stop.stop_id,
                coordinates=[stop.lat, stop.lon],
            )
        )
    for depot in depot_results:
        results.append(
            schemas.AutocompleteResult(
                id=depot.depot_id,
                name=depot.name,
                coordinates=[depot.lat, depot.lon],
            )
        )

    return results[:10]


@router.post("/reverse-geocode", response_model=schemas.ReverseGeocodeResponse)
def reverse_geocode(payload: schemas.ReverseGeocodeRequest) -> schemas.ReverseGeocodeResponse:
    lat, lon = payload.coordinates
    street_number = random.randint(1000, 9999)
    streets = [
        "Main St",
        "Poplar Ave",
        "Union Ave",
        "Madison Ave",
        "Park Ave",
        "Highland St",
    ]
    street = random.choice(streets)
    name = f"{street_number} {street}"
    return schemas.ReverseGeocodeResponse(name=name, address=f"{name}, Memphis, TN")


@router.post("/navigate", response_model=schemas.NavigateResponse)
def navigate(payload: schemas.NavigateRequest) -> schemas.NavigateResponse:
    routes: list[schemas.Route] = []
    for mode in payload.modes:
        routes.append(_generate_mock_route(mode, payload.origin, payload.destination))

    return schemas.NavigateResponse(routes=routes)


@router.post("/bus/geometry", response_model=schemas.BusRouteGeometryResponse)
def bus_geometry(payload: schemas.BusRouteGeometryRequest) -> schemas.BusRouteGeometryResponse:
    start_lat = 35.1495 + (random.random() - 0.5) * 0.1
    start_lng = -90.0490 + (random.random() - 0.5) * 0.1
    end_lat = 35.1495 + (random.random() - 0.5) * 0.1
    end_lng = -90.0490 + (random.random() - 0.5) * 0.1

    geometry: list[list[float]] = []
    steps = 10
    for i in range(steps + 1):
        progress = i / steps
        lat = start_lat + (end_lat - start_lat) * progress + (random.random() - 0.5) * 0.01
        lng = start_lng + (end_lng - start_lng) * progress + (random.random() - 0.5) * 0.01
        geometry.append([lat, lng])

    return schemas.BusRouteGeometryResponse(
        geometry=geometry,
        distance=f"{(random.random() * 5 + 2):.1f} mi",
        duration=f"{random.randint(15, 35)} min",
    )


@router.post("/evaluate", response_model=schemas.EvaluationResponse)
def evaluate(payload: schemas.OperatorEvaluateRequest) -> schemas.EvaluationResponse:
    center_lat = 35.1495
    center_lng = -90.0490

    coverage_area = [
        [
            [center_lat + 0.05, center_lng - 0.06],
            [center_lat + 0.06, center_lng + 0.04],
            [center_lat - 0.03, center_lng + 0.06],
            [center_lat - 0.05, center_lng - 0.04],
            [center_lat + 0.05, center_lng - 0.06],
        ]
    ]

    heatmap_data = [
        {
            "coordinates": [
                center_lat + (random.random() - 0.5) * 0.08,
                center_lng + (random.random() - 0.5) * 0.08,
            ],
            "intensity": random.random(),
        }
        for _ in range(50)
    ]

    service_boundaries = [
        [
            [center_lat + 0.03, center_lng - 0.04],
            [center_lat + 0.04, center_lng + 0.02],
            [center_lat - 0.01, center_lng + 0.03],
            [center_lat - 0.02, center_lng - 0.02],
            [center_lat + 0.03, center_lng - 0.04],
        ],
        [
            [center_lat - 0.02, center_lng - 0.03],
            [center_lat - 0.01, center_lng + 0.01],
            [center_lat - 0.04, center_lng + 0.02],
            [center_lat - 0.05, center_lng - 0.01],
            [center_lat - 0.02, center_lng - 0.03],
        ],
    ]

    return schemas.EvaluationResponse(
        success=True,
        message="Evaluation complete",
        metrics=schemas.EvaluationMetrics(
            totalCoverage="85%",
            estimatedCost="$125,000/month",
            ridership="12,500 passengers/day",
            averageWaitTime="8.5 minutes",
            serviceHours="18 hours/day",
        ),
        coverageArea=coverage_area,
        heatmapData=heatmap_data,
        serviceBoundaries=service_boundaries,
    )


@router.post("/plan/fixed-line", response_model=schemas.FixedLineResponse)
def plan_fixed_line(
    payload: schemas.FixedLineRequest,
    session: Session = Depends(get_session),
) -> schemas.FixedLineResponse:
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
    inputs = planning_service.FixedLineInputs(
        origin_lat=payload.origin[0],
        origin_lon=payload.origin[1],
        destination_lat=payload.destination[0],
        destination_lon=payload.destination[1],
        depart_at_min=payload.depart_at_min or 0,
        transfer_limit=payload.transfer_limit or settings.default_transfer_limit,
        active_service_ids=active_service_ids,
        constraints=constraints,
    )

    itinerary_candidates = planning_service.build_fixed_line_itineraries(session, inputs)
    itineraries = [
        schemas.Itinerary(
            legs=[
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
            ],
            total_duration_s=candidate.total_duration_s,
            total_walk_m=candidate.total_walk_m,
            total_wait_s=candidate.total_wait_s,
            total_invehicle_s=candidate.total_invehicle_s,
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
        for candidate in itinerary_candidates
    ]

    note = "Rule-based itinerary selection using stop distance and time constraints."
    return schemas.FixedLineResponse(itineraries=itineraries, note=note)


@router.post("/plan/on-demand", response_model=schemas.OnDemandResponse)
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

    if result is None:
        return schemas.OnDemandResponse(
            vehicle_id="",
            eta_minutes=0,
            distance_km=0.0,
            note="No feasible vehicle found for the requested windows.",
        )

    ondemand_crud.persist_insertion(
        session,
        result.vehicle_id,
        request_id,
        result.route,
        result.planned_times,
    )

    return schemas.OnDemandResponse(
        vehicle_id=result.vehicle_id,
        eta_minutes=result.eta_minutes,
        distance_km=result.distance_km,
        note=result.note,
    )


def _generate_mock_route(mode: str, origin: list[float], destination: list[float]) -> schemas.Route:
    segments: list[schemas.RouteSegment] = []
    coordinates: list[list[float]] = []

    d_lat = destination[0] - origin[0]
    d_lng = destination[1] - origin[1]

    if mode == "car":
        p1 = [origin[0] + d_lat * 0.2, origin[1]]
        p2 = [origin[0] + d_lat * 0.2, origin[1] + d_lng * 0.4]
        p3 = [origin[0] + d_lat * 0.6, origin[1] + d_lng * 0.4]
        p4 = [origin[0] + d_lat * 0.6, origin[1] + d_lng * 0.8]
        p5 = [destination[0], origin[1] + d_lng * 0.8]

        coordinates = [origin, p1, p2, p3, p4, p5, destination]

        segments.append(
            schemas.RouteSegment(
                instruction="Drive to neighborhood streets",
                distance="0.8 mi",
                duration="4 min",
                coordinates=[origin, p1, p2],
                type="drive",
            )
        )
        segments.append(
            schemas.RouteSegment(
                instruction="Turn onto arterial road",
                distance="2.5 mi",
                duration="8 min",
                coordinates=[p2, p3, p4],
                type="drive",
            )
        )
        segments.append(
            schemas.RouteSegment(
                instruction="Navigate to destination",
                distance="1.0 mi",
                duration="3 min",
                coordinates=[p4, p5, destination],
                type="drive",
            )
        )
    elif mode == "on-demand":
        mid = [origin[0] + d_lat * 0.5, origin[1] + d_lng * 0.5]
        control = [mid[0] - d_lng * 0.3, mid[1] + d_lat * 0.3]

        curve_points: list[list[float]] = []
        steps = 20
        for i in range(steps + 1):
            t = i / steps
            lat = (1 - t) * (1 - t) * origin[0] + 2 * (1 - t) * t * control[0] + t * t * destination[0]
            lng = (1 - t) * (1 - t) * origin[1] + 2 * (1 - t) * t * control[1] + t * t * destination[1]
            curve_points.append([lat, lng])

        coordinates = curve_points
        segments.append(
            schemas.RouteSegment(
                instruction="Direct shuttle service",
                distance="3.8 mi",
                duration="12 min",
                coordinates=curve_points,
                type="drive",
            )
        )
    elif mode == "bus":
        corner = [origin[0], destination[1]]
        walk_start = [origin[0], origin[1] + d_lng * 0.05]
        bus_end = [destination[0] - d_lat * 0.05, destination[1]]

        coordinates = [origin, walk_start, corner, bus_end, destination]
        segments.append(
            schemas.RouteSegment(
                instruction="Walk to bus stop",
                distance="0.2 mi",
                duration="3 min",
                coordinates=[origin, walk_start],
                type="walk",
            )
        )
        segments.append(
            schemas.RouteSegment(
                instruction="Take Bus Line A",
                distance="4.5 mi",
                duration="25 min",
                coordinates=[walk_start, corner, bus_end],
                type="transit",
            )
        )
        segments.append(
            schemas.RouteSegment(
                instruction="Walk to destination",
                distance="0.2 mi",
                duration="3 min",
                coordinates=[bus_end, destination],
                type="walk",
            )
        )
    else:
        corner = [destination[0], origin[1]]
        hub = [corner[0] * 0.95 + origin[0] * 0.05, corner[1]]
        coordinates = [origin, hub, destination]
        segments.append(
            schemas.RouteSegment(
                instruction="Shuttle to Transit Hub" if "on-demand" in mode else "Drive to Transit Hub",
                distance="2.0 mi",
                duration="10 min",
                coordinates=[origin, hub],
                type="drive",
            )
        )
        segments.append(
            schemas.RouteSegment(
                instruction="Transfer to Express Bus",
                distance="3.0 mi",
                duration="15 min",
                coordinates=[hub, destination],
                type="transit",
            )
        )

    total_duration = sum(int(seg.duration.split()[0]) for seg in segments)
    total_distance = sum(float(seg.distance.split()[0]) for seg in segments)

    return schemas.Route(
        mode=mode,
        totalDuration=f"{total_duration} min",
        totalDistance=f"{total_distance:.1f} mi",
        segments=segments,
        coordinates=coordinates,
    )


def _haversine_km(origin: list[float], destination: list[float]) -> float:
    lat1, lon1 = origin
    lat2, lon2 = destination
    rad = math.pi / 180
    dlat = (lat2 - lat1) * rad
    dlon = (lon2 - lon1) * rad
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1 * rad) * math.cos(lat2 * rad) * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return 6371.0 * c

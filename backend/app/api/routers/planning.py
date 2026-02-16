from __future__ import annotations

import math
import random
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_session
from app.schemas import planning as schemas
from app.services import planning as planning_service
from app.crud import ondemand as ondemand_crud
from app.crud import gtfs as gtfs_crud

router = APIRouter(tags=["planning"])


@router.get(
    "/autocomplete",
    response_model=list[schemas.AutocompleteResult],
    summary="Autocomplete stops/depots",
    description="Search stop and depot names for autocomplete suggestions.",
)
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


@router.post(
    "/reverse-geocode",
    response_model=schemas.ReverseGeocodeResponse,
    summary="Reverse geocode",
    description="Mock reverse geocoding for a coordinate.",
)
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


@router.post(
    "/navigate",
    response_model=schemas.NavigateResponse,
    summary="Navigate (legacy)",
    description="Legacy navigation endpoint returning mock routes by mode.",
)
def navigate(payload: schemas.NavigateRequest) -> schemas.NavigateResponse:
    routes: list[schemas.Route] = []
    for mode in payload.modes:
        routes.append(_generate_mock_route(mode, payload.origin, payload.destination))

    return schemas.NavigateResponse(routes=routes)


@router.post(
    "/bus/geometry",
    response_model=schemas.BusRouteGeometryResponse,
    summary="Bus geometry (legacy)",
    description="Mock bus route geometry generator.",
)
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


@router.post(
    "/evaluate",
    response_model=schemas.EvaluationResponse,
    summary="Evaluate (legacy)",
    description="Mock operator evaluation endpoint.",
)
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

from __future__ import annotations

import math
from fastapi import APIRouter, Depends, Query, HTTPException
import httpx
from geoalchemy2.functions import ST_X, ST_Y
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_session
from app.models.gtfs import Stop
from app.schemas import planning as schemas
from app.services import planning as planning_service
from app.crud import ondemand as ondemand_crud
from app.crud import gtfs as gtfs_crud
from app.core.config import settings
import random

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

    stop_ids = [s.stop_id for s in stop_results]
    stop_coord_rows = (
        session.execute(
            select(
                Stop.stop_id,
                ST_Y(Stop.location).label("lat"),
                ST_X(Stop.location).label("lon"),
            ).where(Stop.stop_id.in_(stop_ids), Stop.location.is_not(None))
        )
        .all()
    )
    stop_coord_map = {row.stop_id: (row.lat, row.lon) for row in stop_coord_rows}

    results: list[schemas.AutocompleteResult] = []
    for stop in stop_results:
        coords = stop_coord_map.get(stop.stop_id)
        if coords is None:
            continue
        results.append(
            schemas.AutocompleteResult(
                id=stop.stop_id,
                name=stop.name or stop.stop_id,
                coordinates=[coords[0], coords[1]],
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
    description="Reverse geocoding for a coordinate using Nominatim.",
)
def reverse_geocode(payload: schemas.ReverseGeocodeRequest) -> schemas.ReverseGeocodeResponse:
    lat, lon = payload.coordinates
    if not settings.enable_nominatim:
        raise HTTPException(status_code=503, detail="Nominatim reverse geocoding disabled.")

    url = f"{settings.nominatim_url.rstrip('/')}/reverse"
    params = {
        "format": "jsonv2",
        "lat": lat,
        "lon": lon,
        "zoom": 18,
        "addressdetails": 1,
    }
    headers = {"User-Agent": settings.nominatim_user_agent}
    if settings.nominatim_email:
        headers["From"] = settings.nominatim_email

    try:
        with httpx.Client(timeout=8.0) as client:
            resp = client.get(url, params=params, headers=headers)
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    display_name = data.get("display_name") or "Unknown address"
    name = data.get("name") or display_name.split(",")[0].strip()
    return schemas.ReverseGeocodeResponse(name=name, address=display_name)


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
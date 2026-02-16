from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_session
from app.models.gtfs import Stop
from app.schemas.nearest_stops import NearestStopsRequest, NearestStop
from app.services.planning import get_distance_m
from sqlalchemy import select

router = APIRouter(tags=["nearest-stops"])


@router.post(
    "/nearest-stops",
    response_model=list[NearestStop],
    summary="Find nearest GTFS stops",
    description="Return the nearest GTFS stops to a coordinate within a max distance.",
)
def nearest_stops(
    payload: NearestStopsRequest,
    session: Session = Depends(get_session),
) -> list[NearestStop]:
    lat, lon = payload.coordinates
    max_distance = payload.max_distance_m

    dlat = max_distance / 111_320
    dlon = max_distance / (111_320 * max(0.1, abs(_cos_deg(lat))))

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

    results: list[NearestStop] = []
    for stop in stops:
        if stop.lat is None or stop.lon is None:
            continue
        dist = get_distance_m(lat, lon, stop.lat, stop.lon)
        if dist <= max_distance:
            results.append(
                NearestStop(
                    stop_id=stop.stop_id,
                    name=stop.name,
                    lat=stop.lat,
                    lon=stop.lon,
                    distance_m=round(dist, 2),
                )
            )

    results.sort(key=lambda item: item.distance_m)
    return results[: payload.limit]


def _cos_deg(deg: float) -> float:
    import math

    return math.cos(deg * math.pi / 180)

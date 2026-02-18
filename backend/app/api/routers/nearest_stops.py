from __future__ import annotations

from geoalchemy2 import WKTElement
from geoalchemy2.functions import ST_Distance, ST_DWithin, ST_Transform, ST_X, ST_Y
from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_session
from app.models.gtfs import Stop
from app.schemas.nearest_stops import NearestStop, NearestStopsRequest

router = APIRouter(tags=["nearest-stops"])

# Use EPSG:3857 (Web Mercator, metres) for ST_DWithin distance filtering.
_SRID_M = 3857


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

    origin_wgs = func.ST_SetSRID(func.ST_MakePoint(lon, lat), 4326)
    origin_m = func.ST_Transform(origin_wgs, _SRID_M)

    rows = (
        session.execute(
            select(
                Stop.stop_id,
                Stop.name,
                ST_X(Stop.location).label("lon"),
                ST_Y(Stop.location).label("lat"),
                ST_Distance(
                    ST_Transform(Stop.location, _SRID_M),
                    origin_m,
                ).label("distance_m"),
            )
            .where(
                Stop.location.is_not(None),
                ST_DWithin(
                    ST_Transform(Stop.location, _SRID_M),
                    origin_m,
                    max_distance,
                ),
            )
            .order_by("distance_m")
            .limit(payload.limit)
        )
        .all()
    )

    return [
        NearestStop(
            stop_id=row.stop_id,
            name=row.name,
            lat=row.lat,
            lon=row.lon,
            distance_m=round(row.distance_m, 2),
        )
        for row in rows
    ]

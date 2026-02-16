from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db import get_session
from app.schemas import planning as schemas
from app.services import planning as planning_service
from app.crud import gtfs as gtfs_crud

router = APIRouter(tags=["fixed-line"])


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

    inputs = planning_service.FixedLineInputs(
        origin_lat=payload.origin[0],
        origin_lon=payload.origin[1],
        destination_lat=payload.destination[0],
        destination_lon=payload.destination[1],
        depart_at_min=depart_at_min or 0,
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

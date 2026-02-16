from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db import get_session
from app.schemas import planning as schemas
from pydantic import BaseModel
from app.services import planning as planning_service
from app.services import ondemand as ondemand_service
from app.crud import ondemand as ondemand_crud
from app.crud import gtfs as gtfs_crud
from app.models.gtfs import Stop
from app.logging.config import get_logger

logger = get_logger("multimodal")

router = APIRouter(tags=["multimodal"])


class MultimodalResult(BaseModel):
    label: Literal[
        "fixed-line",
        "on-demand",
        "on-demand->fixed-line->walk",
        "walk->fixed-line->on-demand",
        "on-demand->fixed-line->on-demand",
    ]
    itinerary: schemas.Itinerary


def _build_fixed_line(
    session: Session,
    payload: schemas.FixedLineRequest,
) -> list[schemas.Itinerary]:
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
        service_date = None
        try:
            from datetime import datetime
            from zoneinfo import ZoneInfo

            now = datetime.now(ZoneInfo(agency_timezone))
            service_date = now.strftime("%Y%m%d")
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

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

    extra_access: set[str] = set()
    extra_egress: set[str] = set()

    inputs = planning_service.FixedLineInputs(
        origin_lat=payload.origin[0],
        origin_lon=payload.origin[1],
        destination_lat=payload.destination[0],
        destination_lon=payload.destination[1],
        depart_at_min=depart_at_min or 0,
        transfer_limit=payload.transfer_limit or settings.default_transfer_limit,
        active_service_ids=active_service_ids,
        constraints=constraints,
        extra_access_stop_ids=extra_access or None,
        extra_egress_stop_ids=extra_egress or None,
    )

    candidates = planning_service.build_fixed_line_itineraries(session, inputs)
    return [
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
        for candidate in candidates
    ]


def _build_on_demand_leg(
    session: Session,
    origin: list[float],
    destination: list[float],
    passengers: int,
    pickup_start: int,
    pickup_end: int,
    dropoff_end: int,
) -> schemas.Leg | None:
    request = ondemand_service.Request(
        request_id=None,
        origin_lat=origin[0],
        origin_lon=origin[1],
        destination_lat=destination[0],
        destination_lon=destination[1],
        passengers=passengers,
        pickup_window=ondemand_service.TimeWindow(pickup_start, pickup_end),
        dropoff_window=ondemand_service.TimeWindow(pickup_start, dropoff_end),
    )
    vehicles = ondemand_crud.load_vehicle_states(session, origin[0], origin[1])
    result = ondemand_service.find_best_insertion(vehicles, request, start_min=pickup_start)
    if result is None:
        return None

    return schemas.Leg(
        mode="on-demand",
        from_stop_id=None,
        to_stop_id=None,
        distance_m=result.distance_km * 1000,
        duration_s=result.eta_minutes * 60,
    )


def _combine(
    access: schemas.Leg | None,
    fixed: schemas.Itinerary,
    egress: schemas.Leg | None,
) -> schemas.Itinerary:
    legs = []
    total_walk = fixed.total_walk_m
    total_wait = fixed.total_wait_s
    total_invehicle = fixed.total_invehicle_s
    total_duration = fixed.total_duration_s

    if access:
        legs.append(access)
        total_duration += access.duration_s or 0
    legs.extend(fixed.legs)
    if egress:
        legs.append(egress)
        total_duration += egress.duration_s or 0

    score = schemas.ScoreBreakdown(
        total_minutes=round(total_duration / 60, 4),
        wait_minutes=round(total_wait / 60, 4),
        walk_meters=round(total_walk, 2),
        weight_total_minutes=1.0,
        weight_wait_minutes=0.0,
        weight_walk_meters=0.0,
        score=round(total_duration / 60, 4),
    )

    return schemas.Itinerary(
        legs=legs,
        total_duration_s=total_duration,
        total_walk_m=total_walk,
        total_wait_s=total_wait,
        total_invehicle_s=total_invehicle,
        score=score,
    )


@router.post(
    "/plan/multimodal",
    response_model=list[MultimodalResult],
    summary="Plan multimodal options",
    description="Return fixed-line, on-demand, and multimodal combinations for the same OD request.",
)
def plan_multimodal(
    payload: schemas.FixedLineRequest,
    session: Session = Depends(get_session),
):
    pickup_start = payload.depart_at_min or 0
    if payload.arrive_by_min is not None and payload.depart_at_min is None:
        pickup_start = max(0, payload.arrive_by_min - settings.default_max_total_minutes)
    pickup_end = pickup_start + 30
    dropoff_end = pickup_start + 90

    fixed_itineraries = _build_fixed_line(session, payload)
    results: list[MultimodalResult] = []

    if fixed_itineraries:
        results.append(
            MultimodalResult(label="fixed-line", itinerary=fixed_itineraries[0])
        )

    ondemand_leg = _build_on_demand_leg(
        session,
        payload.origin,
        payload.destination,
        passengers=1,
        pickup_start=pickup_start,
        pickup_end=pickup_end,
        dropoff_end=dropoff_end,
    )
    if ondemand_leg:
        only_ondemand = schemas.Itinerary(
            legs=[ondemand_leg],
            total_duration_s=ondemand_leg.duration_s or 0,
            total_walk_m=0.0,
            total_wait_s=0,
            total_invehicle_s=ondemand_leg.duration_s or 0,
            score=schemas.ScoreBreakdown(
                total_minutes=round((ondemand_leg.duration_s or 0) / 60, 4),
                wait_minutes=0.0,
                walk_meters=0.0,
                weight_total_minutes=1.0,
                weight_wait_minutes=0.0,
                weight_walk_meters=0.0,
                score=round((ondemand_leg.duration_s or 0) / 60, 4),
            ),
        )
        results.append(MultimodalResult(label="on-demand", itinerary=only_ondemand))

    if fixed_itineraries:
        base = fixed_itineraries[0]
        access_leg = None
        egress_leg = None
        if base.legs:
            first_leg = base.legs[0]
            last_leg = base.legs[-1]
            if first_leg.to_stop_id is not None:
                stop = (
                    session.execute(select(Stop).where(Stop.stop_id == first_leg.to_stop_id))
                    .scalars()
                    .first()
                )
                if stop and stop.lat is not None and stop.lon is not None:
                    access_leg = _build_on_demand_leg(
                        session,
                        payload.origin,
                        [stop.lat, stop.lon],
                        passengers=1,
                        pickup_start=pickup_start,
                        pickup_end=pickup_end,
                        dropoff_end=dropoff_end,
                    )
            if last_leg.from_stop_id is not None:
                stop = (
                    session.execute(select(Stop).where(Stop.stop_id == last_leg.from_stop_id))
                    .scalars()
                    .first()
                )
                if stop and stop.lat is not None and stop.lon is not None:
                    egress_leg = _build_on_demand_leg(
                        session,
                        [stop.lat, stop.lon],
                        payload.destination,
                        passengers=1,
                        pickup_start=pickup_start,
                        pickup_end=pickup_end,
                        dropoff_end=dropoff_end,
                    )

        combined = _combine(access_leg, base, None)
        results.append(
            MultimodalResult(label="on-demand->fixed-line->walk", itinerary=combined)
        )

        combined = _combine(None, base, egress_leg)
        results.append(
            MultimodalResult(label="walk->fixed-line->on-demand", itinerary=combined)
        )

        combined = _combine(access_leg, base, egress_leg)
        results.append(
            MultimodalResult(label="on-demand->fixed-line->on-demand", itinerary=combined)
        )

    return results

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_session
from app.schemas import planning as schemas
from app.services import ondemand as ondemand_service
from app.crud import ondemand as ondemand_crud

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

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
from app.services.leg_geometry import fill_leg_metrics, aggregate_geometry
from app.services.leg_merge import merge_walk_on_demand

logger = get_logger("fixed_line")

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

        fill_leg_metrics(
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
        fill_leg_metrics(session, payload.origin, payload.destination, leg_subset)
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
            itinerary_id="fixed-1",
            legs=merge_walk_on_demand(legs),
            total_duration_s=total_duration_s,
            total_walk_m=total_walk_m,
            total_wait_s=first.total_wait_s,
            total_invehicle_s=first.total_invehicle_s,
            total_transit_distance_m=round(
                sum(
                    leg.distance_m or 0
                    for leg in legs
                    if leg.mode in ("transit", "transfer")
                ),
                2,
            ),
            total_vehicle_distance_m=round(
                sum(
                    leg.distance_m or 0
                    for leg in legs
                    if leg.mode in ("transit", "transfer")
                ),
                2,
            ),
            geometry=aggregate_geometry(legs),
            score=score,
        )

        return schemas.FixedLineResponse(
            best_itinerary=itinerary.itinerary_id,
            total_duration_s=itinerary.total_duration_s,
            total_wait_s=itinerary.total_wait_s,
            total_invehicle_s=itinerary.total_invehicle_s,
            total_walk_m=itinerary.total_walk_m,
            score=itinerary.score,
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
    for idx, candidate in enumerate(itinerary_candidates, start=1):
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
        fill_leg_metrics(session, payload.origin, payload.destination, legs)
        legs = merge_walk_on_demand(legs)
        total_walk_m = sum(
            leg.distance_m or 0 for leg in legs if leg.mode == "walk"
        )
        total_transit_distance_m = sum(
            leg.distance_m or 0 for leg in legs if leg.mode in ("transit", "transfer")
        )
        itineraries.append(
            schemas.Itinerary(
                itinerary_id=f"fixed-{idx}",
                legs=legs,
                total_duration_s=candidate.total_duration_s,
                total_walk_m=round(total_walk_m, 2),
                total_wait_s=candidate.total_wait_s,
                total_invehicle_s=candidate.total_invehicle_s,
                total_transit_distance_m=round(total_transit_distance_m, 2),
                total_vehicle_distance_m=round(total_transit_distance_m, 2),
                geometry=aggregate_geometry(legs),
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
    best = min(itineraries, key=lambda item: item.score.score) if itineraries else None
    return schemas.FixedLineResponse(
        best_itinerary=best.itinerary_id if best else None,
        total_duration_s=best.total_duration_s if best else None,
        total_wait_s=best.total_wait_s if best else None,
        total_invehicle_s=best.total_invehicle_s if best else None,
        total_walk_m=best.total_walk_m if best else None,
        total_transit_distance_m=best.total_transit_distance_m if best else None,
        total_vehicle_distance_m=best.total_vehicle_distance_m if best else None,
        score=best.score if best else None,
        itineraries=itineraries,
        note=note,
    )

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from geoalchemy2.functions import ST_X, ST_Y
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db import get_session
from app.schemas import planning as schemas
from app.services import planning as planning_service
from app.services import ondemand as ondemand_service
from app.crud import ondemand as ondemand_crud
from app.crud import gtfs as gtfs_crud
from app.models.gtfs import Stop
from app.logging.config import get_logger
from app.services.leg_geometry import fill_leg_metrics, aggregate_geometry, fill_leg_addresses
from app.services import hubs
from app.services.leg_merge import merge_walk_on_demand

logger = get_logger("multimodal")

router = APIRouter(tags=["multimodal"])


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
            return []

        boc_inputs = planning_service.FixedLineInputs(
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
        candidates = planning_service.build_fixed_line_itineraries(session, boc_inputs)
        if not candidates:
            return []
        first = candidates[0]
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

        walk_m = planning_service.get_distance_m(
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

        total_walk_m = sum(
            leg.distance_m or 0 for leg in legs if leg.mode == "walk"
        )
        total_transit_distance_m = sum(
            leg.distance_m or 0 for leg in legs if leg.mode in ("transit", "transfer")
        )
        score = schemas.ScoreBreakdown(
            total_minutes=round(first.total_duration_s / 60, 4),
            wait_minutes=round(first.total_wait_s / 60, 4),
            walk_meters=round(total_walk_m, 2),
            weight_total_minutes=constraints.score_weight_total_minutes,
            weight_wait_minutes=constraints.score_weight_wait_minutes,
            weight_walk_meters=constraints.score_weight_walk_meters,
            score=round(
                (first.total_duration_s / 60) * constraints.score_weight_total_minutes
                + (first.total_wait_s / 60) * constraints.score_weight_wait_minutes
                + total_walk_m * constraints.score_weight_walk_meters,
                4,
            ),
        )
        return [
            schemas.Itinerary(
                itinerary_id="fixed-boc-1",
                legs=legs,
                total_duration_s=first.total_duration_s,
                total_walk_m=round(total_walk_m, 2),
                total_wait_s=first.total_wait_s,
                total_invehicle_s=first.total_invehicle_s,
                total_transit_distance_m=round(total_transit_distance_m, 2),
                total_vehicle_distance_m=round(total_transit_distance_m, 2),
                geometry=aggregate_geometry(legs),
                score=score,
            )
        ]

    candidates = planning_service.build_fixed_line_itineraries(session, inputs)
    itineraries: list[schemas.Itinerary] = []
    for idx, candidate in enumerate(candidates, start=1):
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
        itineraries.append(
            schemas.Itinerary(
                itinerary_id=f"fixed-{idx}",
                legs=legs,
                total_duration_s=candidate.total_duration_s,
                total_walk_m=candidate.total_walk_m,
                total_wait_s=candidate.total_wait_s,
                total_invehicle_s=candidate.total_invehicle_s,
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
    return itineraries


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

    distance_m, duration_s, geometry = ondemand_service.estimate_direct_leg(
        origin[0], origin[1], destination[0], destination[1]
    )
    return schemas.Leg(
        mode="on-demand",
        from_stop_id=None,
        to_stop_id=None,
        from_coords=schemas.Coordinate(lat=origin[0], lon=origin[1]),
        to_coords=schemas.Coordinate(lat=destination[0], lon=destination[1]),
        distance_m=round(distance_m, 2),
        duration_s=duration_s,
        geometry=geometry,
    )


def _build_taxi_leg(
    origin: list[float],
    destination: list[float],
) -> schemas.Leg:
    distance_m, duration_s, geometry = ondemand_service.estimate_direct_leg(
        origin[0], origin[1], destination[0], destination[1]
    )
    return schemas.Leg(
        mode="on-demand",
        from_stop_id=None,
        to_stop_id=None,
        from_coords=schemas.Coordinate(lat=origin[0], lon=origin[1]),
        to_coords=schemas.Coordinate(lat=destination[0], lon=destination[1]),
        distance_m=round(distance_m, 2),
        duration_s=duration_s,
        geometry=geometry,
    )




def _combine(
    access: schemas.Leg | None,
    fixed: schemas.Itinerary,
    egress: schemas.Leg | None,
    weight_total: float,
    weight_wait: float,
    weight_walk: float,
) -> schemas.Itinerary:
    legs = []
    total_walk = fixed.total_walk_m
    total_wait = fixed.total_wait_s
    total_invehicle = fixed.total_invehicle_s
    total_duration = fixed.total_duration_s

    if access:
        legs.append(access)
        total_duration += access.duration_s or 0
        total_invehicle += access.duration_s or 0
    legs.extend(fixed.legs)
    if egress:
        legs.append(egress)
        total_duration += egress.duration_s or 0
        total_invehicle += egress.duration_s or 0

    legs = merge_walk_on_demand(legs)
    total_duration = sum(leg.duration_s or 0 for leg in legs)
    total_walk = sum(
        leg.distance_m or 0 for leg in legs if leg.mode == "walk"
    )
    total_wait = sum(leg.duration_s or 0 for leg in legs if leg.mode == "transfer")
    total_invehicle = sum(
        leg.duration_s or 0 for leg in legs if leg.mode not in ("walk", "transfer")
    )
    score = schemas.ScoreBreakdown(
        total_minutes=round(total_duration / 60, 4),
        wait_minutes=round(total_wait / 60, 4),
        walk_meters=round(total_walk, 2),
        weight_total_minutes=weight_total,
        weight_wait_minutes=weight_wait,
        weight_walk_meters=weight_walk,
        score=round(
            (total_duration / 60) * weight_total
            + (total_wait / 60) * weight_wait
            + total_walk * weight_walk,
            4,
        ),
    )

    return schemas.Itinerary(
        itinerary_id="combined",
        legs=legs,
        total_duration_s=total_duration,
        total_walk_m=total_walk,
        total_wait_s=total_wait,
        total_invehicle_s=total_invehicle,
        geometry=aggregate_geometry(legs),
        score=score,
    )


def _metrics_for_legs(
    legs: list[schemas.Leg],
    weight_total: float,
    weight_wait: float,
    weight_walk: float,
) -> schemas.ItineraryMetrics:
    total_duration = sum(leg.duration_s or 0 for leg in legs)
    total_walk_m = sum(
        leg.distance_m or 0
        for leg in legs
        if leg.mode == "walk"
    )
    total_transit_distance_m = sum(
        leg.distance_m or 0
        for leg in legs
        if leg.mode in ("transit", "transfer", "on-demand", "private")
    )
    total_vehicle_distance_m = sum(
        leg.distance_m or 0
        for leg in legs
        if leg.mode in ("transit", "transfer", "on-demand", "private")
    )
    total_wait_s = sum(leg.duration_s or 0 for leg in legs if leg.mode == "transfer")
    total_invehicle_s = sum(
        leg.duration_s or 0 for leg in legs if leg.mode not in ("walk", "transfer")
    )
    score = schemas.ScoreBreakdown(
        total_minutes=round(total_duration / 60, 4),
        wait_minutes=round(total_wait_s / 60, 4),
        walk_meters=round(total_walk_m, 2),
        weight_total_minutes=weight_total,
        weight_wait_minutes=weight_wait,
        weight_walk_meters=weight_walk,
        score=round(
            (total_duration / 60) * weight_total
            + (total_wait_s / 60) * weight_wait
            + total_walk_m * weight_walk,
            4,
        ),
    )
    return schemas.ItineraryMetrics(
        total_duration_s=total_duration,
        total_wait_s=total_wait_s,
        total_invehicle_s=total_invehicle_s,
        total_walk_m=round(total_walk_m, 2),
        total_transit_distance_m=round(total_transit_distance_m, 2),
        total_vehicle_distance_m=round(total_vehicle_distance_m, 2),
        score=score,
    )


def _metrics_for_modes(
    legs: list[schemas.Leg],
    include_on_demand: bool,
    weight_total: float,
    weight_wait: float,
    weight_walk: float,
) -> schemas.ItineraryMetrics:
    selected = [
        leg for leg in legs if (leg.mode == "on-demand") == include_on_demand
    ]
    return _metrics_for_legs(selected, weight_total, weight_wait, weight_walk)


@router.post(
    "/plan/multimodal",
    response_model=schemas.MultimodalResponse,
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
    results: list[schemas.MultimodalItinerary] = []
    itinerary_counter = 1

    weight_total = payload.score_weight_total_minutes or settings.score_weight_total_minutes
    weight_wait = payload.score_weight_wait_minutes or settings.score_weight_wait_minutes
    weight_walk = payload.score_weight_walk_meters or settings.score_weight_walk_meters

    build_leg = _build_taxi_leg if payload.force_taxi else None
    if not payload.force_taxi:
        build_leg = lambda a, b: _build_on_demand_leg(
            session,
            a,
            b,
            passengers=1,
            pickup_start=pickup_start,
            pickup_end=pickup_end,
            dropoff_end=dropoff_end,
        )

    ondemand_leg = build_leg(payload.origin, payload.destination) if build_leg else None
    if ondemand_leg:
        only_ondemand = schemas.Itinerary(
            itinerary_id="ondemand-only",
            legs=[ondemand_leg],
            total_duration_s=ondemand_leg.duration_s or 0,
            total_walk_m=0.0,
            total_wait_s=0,
            total_invehicle_s=ondemand_leg.duration_s or 0,
            total_transit_distance_m=round(ondemand_leg.distance_m or 0, 2),
            total_vehicle_distance_m=round(ondemand_leg.distance_m or 0, 2),
            geometry=aggregate_geometry([ondemand_leg]),
            score=schemas.ScoreBreakdown(
                total_minutes=round((ondemand_leg.duration_s or 0) / 60, 4),
                wait_minutes=0.0,
                walk_meters=0.0,
                weight_total_minutes=weight_total,
                weight_wait_minutes=weight_wait,
                weight_walk_meters=weight_walk,
                score=round(
                    ((ondemand_leg.duration_s or 0) / 60) * weight_total,
                    4,
                ),
            ),
        )
        fill_leg_addresses(only_ondemand.legs)
        results.append(
            schemas.MultimodalItinerary(
                itinerary_id=f"multi-{itinerary_counter}",
                legs=only_ondemand.legs,
                metrics=schemas.MultimodalMetrics(
                    overall=_metrics_for_legs(
                        only_ondemand.legs, weight_total, weight_wait, weight_walk
                    ),
                    on_demand=_metrics_for_modes(
                        only_ondemand.legs, True, weight_total, weight_wait, weight_walk
                    ),
                    fixed_line=_metrics_for_modes(
                        only_ondemand.legs, False, weight_total, weight_wait, weight_walk
                    ),
                ),
            )
        )
        itinerary_counter += 1

    if fixed_itineraries:
        limit = payload.multimodal_limit or len(fixed_itineraries)
        for base in fixed_itineraries[:limit]:
            access_leg = None
            egress_leg = None
            if base.legs:
                first_leg = base.legs[0]
                last_leg = base.legs[-1]
                if first_leg.to_stop_id is not None:
                    stop_row = (
                        session.execute(
                            select(
                                ST_Y(Stop.location).label("lat"),
                                ST_X(Stop.location).label("lon"),
                            ).where(Stop.stop_id == first_leg.to_stop_id, Stop.location.is_not(None))
                        )
                        .first()
                    )
                    if stop_row:
                        access_leg = build_leg(payload.origin, [stop_row.lat, stop_row.lon]) if build_leg else None
                if last_leg.from_stop_id is not None:
                    stop_row = (
                        session.execute(
                            select(
                                ST_Y(Stop.location).label("lat"),
                                ST_X(Stop.location).label("lon"),
                            ).where(Stop.stop_id == last_leg.from_stop_id, Stop.location.is_not(None))
                        )
                        .first()
                    )
                    if stop_row:
                        egress_leg = build_leg([stop_row.lat, stop_row.lon], payload.destination) if build_leg else None

            combined = _combine(access_leg, base, None, weight_total, weight_wait, weight_walk)
            fill_leg_addresses(combined.legs)
            results.append(
                schemas.MultimodalItinerary(
                    itinerary_id=f"multi-{itinerary_counter}",
                    legs=combined.legs,
                    metrics=schemas.MultimodalMetrics(
                        overall=_metrics_for_legs(
                            combined.legs, weight_total, weight_wait, weight_walk
                        ),
                        on_demand=_metrics_for_modes(
                            combined.legs, True, weight_total, weight_wait, weight_walk
                        ),
                        fixed_line=_metrics_for_modes(
                            combined.legs, False, weight_total, weight_wait, weight_walk
                        ),
                    ),
                )
            )
            itinerary_counter += 1

            combined = _combine(None, base, egress_leg, weight_total, weight_wait, weight_walk)
            fill_leg_addresses(combined.legs)
            results.append(
                schemas.MultimodalItinerary(
                    itinerary_id=f"multi-{itinerary_counter}",
                    legs=combined.legs,
                    metrics=schemas.MultimodalMetrics(
                        overall=_metrics_for_legs(
                            combined.legs, weight_total, weight_wait, weight_walk
                        ),
                        on_demand=_metrics_for_modes(
                            combined.legs, True, weight_total, weight_wait, weight_walk
                        ),
                        fixed_line=_metrics_for_modes(
                            combined.legs, False, weight_total, weight_wait, weight_walk
                        ),
                    ),
                )
            )
            itinerary_counter += 1

            combined = _combine(access_leg, base, egress_leg, weight_total, weight_wait, weight_walk)
            fill_leg_addresses(combined.legs)
            results.append(
                schemas.MultimodalItinerary(
                    itinerary_id=f"multi-{itinerary_counter}",
                    legs=combined.legs,
                    metrics=schemas.MultimodalMetrics(
                        overall=_metrics_for_legs(
                            combined.legs, weight_total, weight_wait, weight_walk
                        ),
                        on_demand=_metrics_for_modes(
                            combined.legs, True, weight_total, weight_wait, weight_walk
                        ),
                        fixed_line=_metrics_for_modes(
                            combined.legs, False, weight_total, weight_wait, weight_walk
                        ),
                    ),
                )
            )
            itinerary_counter += 1

    best = (
        min(results, key=lambda item: item.metrics.overall.score.score)
        if results
        else None
    )
    results = sorted(results, key=lambda item: item.metrics.overall.score.score)
    limit = payload.multimodal_number or 3
    results = results[: max(1, limit)]
    best = results[0] if results else None
    best_overall = best.metrics.overall if best else None
    return schemas.MultimodalResponse(
        best_itinerary=best.itinerary_id if best else None,
        total_duration_s=best_overall.total_duration_s if best_overall else None,
        total_wait_s=best_overall.total_wait_s if best_overall else None,
        total_invehicle_s=best_overall.total_invehicle_s if best_overall else None,
        total_walk_m=best_overall.total_walk_m if best_overall else None,
        total_transit_distance_m=best_overall.total_transit_distance_m if best_overall else None,
        total_vehicle_distance_m=best_overall.total_vehicle_distance_m if best_overall else None,
        score=best_overall.score if best_overall else None,
        itineraries=results,
        note="Multimodal itineraries with per-segment metrics.",
    )

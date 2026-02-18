from __future__ import annotations

from app.schemas import planning as schemas
from app.services.leg_geometry import aggregate_geometry


def compute_itinerary_metrics(
    legs: list[schemas.Leg],
    weight_total: float,
    weight_wait: float,
    weight_walk: float,
) -> schemas.ItineraryMetrics:
    total_duration = sum(leg.duration_s or 0 for leg in legs)
    total_walk_m = sum(leg.distance_m or 0 for leg in legs if leg.mode == "walk")
    total_transit_distance_m = sum(
        leg.distance_m or 0
        for leg in legs
        if leg.mode in ("transit", "transfer", "on-demand", "private")
    )
    total_vehicle_distance_m = total_transit_distance_m
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
        geometry=aggregate_geometry(legs),
        score=score,
    )

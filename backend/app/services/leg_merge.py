from __future__ import annotations

from app.schemas import planning as schemas
from app.services import ondemand as ondemand_service


def merge_walk_on_demand(legs: list[schemas.Leg]) -> list[schemas.Leg]:
    if not legs:
        return legs
    merged: list[schemas.Leg] = []
    idx = 0
    while idx < len(legs):
        current = legs[idx]
        next_leg = legs[idx + 1] if idx + 1 < len(legs) else None
        if next_leg and current.mode == "walk" and next_leg.mode == "on-demand":
            if current.from_coords and next_leg.to_coords:
                distance_m, duration_s, geometry = ondemand_service.estimate_direct_leg(
                    current.from_coords.lat,
                    current.from_coords.lon,
                    next_leg.to_coords.lat,
                    next_leg.to_coords.lon,
                )
                merged.append(
                    schemas.Leg(
                        mode="on-demand",
                        from_stop_id=None,
                        to_stop_id=None,
                        from_coords=current.from_coords,
                        to_coords=next_leg.to_coords,
                        distance_m=round(distance_m, 2),
                        duration_s=duration_s,
                        geometry=geometry,
                    )
                )
                idx += 2
                continue
        if next_leg and current.mode == "on-demand" and next_leg.mode == "walk":
            if current.from_coords and next_leg.to_coords:
                distance_m, duration_s, geometry = ondemand_service.estimate_direct_leg(
                    current.from_coords.lat,
                    current.from_coords.lon,
                    next_leg.to_coords.lat,
                    next_leg.to_coords.lon,
                )
                merged.append(
                    schemas.Leg(
                        mode="on-demand",
                        from_stop_id=None,
                        to_stop_id=None,
                        from_coords=current.from_coords,
                        to_coords=next_leg.to_coords,
                        distance_m=round(distance_m, 2),
                        duration_s=duration_s,
                        geometry=geometry,
                    )
                )
                idx += 2
                continue
        merged.append(current)
        idx += 1
    return merged

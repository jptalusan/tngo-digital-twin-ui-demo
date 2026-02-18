from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class CreateDepotRequest(BaseModel):
    coordinates: list[float] = Field(
        min_length=2,
        max_length=2,
        description="Depot location as [lat, lon].",
    )
    address: Optional[str] = Field(
        default=None,
        description="Human-readable address (optional; used as depot name if provided).",
    )
    vehicles: int = Field(ge=1, description="Number of vehicles to provision for this depot.")
    capacity: int = Field(ge=1, description="Passenger capacity for each vehicle (homogeneous fleet).")
    service_zone_hex_ids: list[str] = Field(
        description="Array of H3 hex IDs that form the depot's service zone.",
    )
    h3_resolution: Optional[int] = Field(
        default=None,
        description="H3 resolution level (derived from any hex ID if omitted).",
    )


class DepotVehicleSummary(BaseModel):
    vehicle_id: str
    capacity: int


class CreateDepotResponse(BaseModel):
    depot_id: str
    name: str
    lat: float
    lon: float
    address: Optional[str]
    vehicle_count: int
    capacity: int
    hex_count: int
    vehicles: list[DepotVehicleSummary]

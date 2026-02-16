from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field


class NearestStopsRequest(BaseModel):
    coordinates: List[float] = Field(
        min_length=2, max_length=2, description="Coordinates as [lat, lon]."
    )
    max_distance_m: float = Field(
        default=2000, description="Max distance in meters for candidate stops."
    )
    limit: int = Field(default=10, description="Max number of stops to return.")


class NearestStop(BaseModel):
    stop_id: str
    name: str | None
    lat: float
    lon: float
    distance_m: float

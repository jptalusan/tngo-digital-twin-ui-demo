from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class AutocompleteResult(BaseModel):
    id: str
    name: str
    coordinates: List[float]


class ReverseGeocodeRequest(BaseModel):
    coordinates: List[float] = Field(min_length=2, max_length=2)


class ReverseGeocodeResponse(BaseModel):
    name: str
    address: str


class RouteSegment(BaseModel):
    instruction: str
    distance: str
    duration: str
    coordinates: List[List[float]]
    type: str


class Route(BaseModel):
    mode: str
    totalDuration: str
    totalDistance: str
    segments: List[RouteSegment]
    coordinates: List[List[float]]


class NavigateRequest(BaseModel):
    origin: List[float] = Field(min_length=2, max_length=2)
    destination: List[float] = Field(min_length=2, max_length=2)
    modes: List[str]


class NavigateResponse(BaseModel):
    routes: List[Route]


class BusRouteGeometryRequest(BaseModel):
    origin: str
    destination: str


class BusRouteGeometryResponse(BaseModel):
    geometry: List[List[float]]
    distance: str
    duration: str


class OperatorEvaluateMode(BaseModel):
    type: str
    config: dict


class OperatorEvaluateRequest(BaseModel):
    modes: List[OperatorEvaluateMode]


class EvaluationMetrics(BaseModel):
    totalCoverage: str
    estimatedCost: str
    ridership: str
    averageWaitTime: str
    serviceHours: str


class EvaluationResponse(BaseModel):
    success: bool
    message: str
    metrics: EvaluationMetrics
    coverageArea: List[List[List[float]]]
    heatmapData: List[dict]
    serviceBoundaries: List[List[List[float]]]


class FixedLineRequest(BaseModel):
    origin: List[float] = Field(min_length=2, max_length=2)
    destination: List[float] = Field(min_length=2, max_length=2)
    depart_at_min: Optional[int] = None
    service_date: Optional[str] = None
    agency_timezone: Optional[str] = None
    max_walk_meters: int = 800
    max_wait_minutes: Optional[int] = None
    max_invehicle_minutes: Optional[int] = None
    max_total_minutes: Optional[int] = None
    transfer_limit: Optional[int] = None
    score_weight_total_minutes: Optional[float] = None
    score_weight_wait_minutes: Optional[float] = None
    score_weight_walk_meters: Optional[float] = None


class Leg(BaseModel):
    mode: str
    from_stop_id: Optional[str] = None
    to_stop_id: Optional[str] = None
    distance_m: Optional[float] = None
    duration_s: Optional[int] = None
    route_id: Optional[str] = None
    trip_id: Optional[str] = None


class ScoreBreakdown(BaseModel):
    total_minutes: float
    wait_minutes: float
    walk_meters: float
    weight_total_minutes: float
    weight_wait_minutes: float
    weight_walk_meters: float
    score: float


class Itinerary(BaseModel):
    legs: List[Leg]
    total_duration_s: int
    total_walk_m: float
    total_wait_s: int
    total_invehicle_s: int
    score: ScoreBreakdown


class FixedLineResponse(BaseModel):
    itineraries: List[Itinerary]
    note: str


class OnDemandRequest(BaseModel):
    origin: List[float] = Field(min_length=2, max_length=2)
    destination: List[float] = Field(min_length=2, max_length=2)
    passengers: int = 1
    pickup_window_start_min: Optional[int] = None
    pickup_window_end_min: Optional[int] = None
    dropoff_window_end_min: Optional[int] = None


class OnDemandResponse(BaseModel):
    vehicle_id: str
    eta_minutes: int
    distance_km: float
    note: str

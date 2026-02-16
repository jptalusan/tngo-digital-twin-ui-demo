from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class AutocompleteResult(BaseModel):
    """Autocomplete suggestion for stops/depots."""
    id: str
    name: str
    coordinates: List[float] = Field(description="Coordinates as [lat, lon].")


class ReverseGeocodeRequest(BaseModel):
    coordinates: List[float] = Field(
        min_length=2,
        max_length=2,
        description="Coordinates as [lat, lon] to reverse geocode.",
    )


class ReverseGeocodeResponse(BaseModel):
    """Resolved name/address for a coordinate."""
    name: str
    address: str


class RouteSegment(BaseModel):
    """Segment used by legacy navigation endpoint."""
    instruction: str
    distance: str
    duration: str
    coordinates: List[List[float]]
    type: str


class Route(BaseModel):
    """Route used by legacy navigation endpoint."""
    mode: str
    totalDuration: str
    totalDistance: str
    segments: List[RouteSegment]
    coordinates: List[List[float]]


class NavigateRequest(BaseModel):
    origin: List[float] = Field(min_length=2, max_length=2, description="Origin [lat, lon].")
    destination: List[float] = Field(
        min_length=2, max_length=2, description="Destination [lat, lon]."
    )
    modes: List[str]


class NavigateResponse(BaseModel):
    """Legacy navigation response."""
    routes: List[Route]


class BusRouteGeometryRequest(BaseModel):
    """Legacy bus geometry request."""
    origin: str
    destination: str


class BusRouteGeometryResponse(BaseModel):
    """Legacy bus geometry response."""
    geometry: List[List[float]]
    distance: str
    duration: str


class OperatorEvaluateMode(BaseModel):
    """Legacy evaluation mode config."""
    type: str
    config: dict


class OperatorEvaluateRequest(BaseModel):
    """Legacy evaluation request."""
    modes: List[OperatorEvaluateMode]


class EvaluationMetrics(BaseModel):
    """Legacy evaluation metrics."""
    totalCoverage: str
    estimatedCost: str
    ridership: str
    averageWaitTime: str
    serviceHours: str


class EvaluationResponse(BaseModel):
    """Legacy evaluation response."""
    success: bool
    message: str
    metrics: EvaluationMetrics
    coverageArea: List[List[List[float]]]
    heatmapData: List[dict]
    serviceBoundaries: List[List[List[float]]]


class FixedLineRequest(BaseModel):
    """Request for fixed-line planning."""    
    origin: List[float] = Field(
        min_length=2, max_length=2, description="Origin [lat, lon]."
    )
    destination: List[float] = Field(
        min_length=2, max_length=2, description="Destination [lat, lon]."
    )
    depart_at_min: Optional[int] = Field(
        default=None, description="Minutes since midnight for departure."
    )
    arrive_by_min: Optional[int] = Field(
        default=None, description="Minutes since midnight to arrive by (heuristic)."
    )
    service_date: Optional[str] = Field(
        default=None, description="Service date in YYYYMMDD."
    )
    agency_timezone: Optional[str] = Field(
        default=None, description="Agency timezone for validation."
    )
    max_walk_meters: int = 800
    max_wait_minutes: Optional[int] = None
    max_invehicle_minutes: Optional[int] = None
    max_total_minutes: Optional[int] = None
    transfer_limit: Optional[int] = None
    score_weight_total_minutes: Optional[float] = None
    score_weight_wait_minutes: Optional[float] = None
    score_weight_walk_meters: Optional[float] = None


class Leg(BaseModel):
    """A single leg in an itinerary."""
    mode: str
    from_stop_id: Optional[str] = None
    to_stop_id: Optional[str] = None
    distance_m: Optional[float] = None
    duration_s: Optional[int] = None
    route_id: Optional[str] = None
    trip_id: Optional[str] = None


class ScoreBreakdown(BaseModel):
    """Score breakdown for itinerary comparison."""
    total_minutes: float
    wait_minutes: float
    walk_meters: float
    weight_total_minutes: float
    weight_wait_minutes: float
    weight_walk_meters: float
    score: float


class Itinerary(BaseModel):
    """An ordered set of legs with aggregate metrics."""
    legs: List[Leg]
    total_duration_s: int
    total_walk_m: float
    total_wait_s: int
    total_invehicle_s: int
    score: ScoreBreakdown


class FixedLineResponse(BaseModel):
    """Fixed-line planning response."""
    itineraries: List[Itinerary]
    note: str


class OnDemandRequest(BaseModel):
    """Request for on-demand planning."""
    origin: List[float] = Field(min_length=2, max_length=2, description="Origin [lat, lon].")
    destination: List[float] = Field(
        min_length=2, max_length=2, description="Destination [lat, lon]."
    )
    passengers: int = 1
    pickup_window_start_min: Optional[int] = None
    pickup_window_end_min: Optional[int] = None
    dropoff_window_end_min: Optional[int] = None


class OnDemandResponse(BaseModel):
    """On-demand planning response."""
    vehicle_id: str
    eta_minutes: int
    distance_km: float
    note: str

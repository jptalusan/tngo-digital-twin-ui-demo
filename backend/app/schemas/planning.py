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
    boc_request: Optional[bool] = Field(
        default=False,
        description="If true, use BOC manual pipeline: origin -> BOC ingress -> BOC egress -> walk.",
    )


class BaseLeg(BaseModel):
    """Common leg fields shared across itineraries and manifests."""
    mode: str
    from_stop_id: Optional[str] = None
    to_stop_id: Optional[str] = None
    distance_m: Optional[float] = None
    duration_s: Optional[int] = None
    geometry: Optional[str] = None
    route_id: Optional[str] = None
    trip_id: Optional[str] = None


class Leg(BaseLeg):
    """A single leg in an itinerary."""


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
    geometry: Optional[str] = None
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
    score_weight_total_minutes: Optional[float] = None
    score_weight_wait_minutes: Optional[float] = None
    score_weight_walk_meters: Optional[float] = None


class OnDemandResponse(BaseModel):
    """On-demand planning response."""
    vehicle_id: str
    eta_minutes: int
    distance_km: float
    total_duration_s: int
    total_wait_s: int
    total_invehicle_s: int
    score: ScoreBreakdown
    note: str


class OnDemandEvaluateRequest(BaseModel):
    """Request to evaluate a vehicle's active on-demand schedule."""
    vehicle_id: str = Field(description="Vehicle identifier to evaluate.")
    score_weight_total_minutes: Optional[float] = None
    score_weight_wait_minutes: Optional[float] = None
    score_weight_walk_meters: Optional[float] = None


class OnDemandEvaluateResponse(BaseModel):
    """Evaluation metrics for an on-demand vehicle schedule."""
    vehicle_id: str
    stop_count: int
    total_duration_s: int
    total_wait_s: int
    total_invehicle_s: int
    total_distance_m: float
    score: ScoreBreakdown
    note: str


class OnDemandFulfillmentRequest(BaseModel):
    """Request to summarize fulfilled vs unfulfilled on-demand requests for a vehicle."""
    vehicle_id: str = Field(description="Vehicle identifier to summarize.")


class OnDemandFulfillmentResponse(BaseModel):
    """Fulfillment summary for on-demand requests assigned to a vehicle."""
    vehicle_id: str
    total_assigned: int
    fulfilled: int
    unfulfilled: int
    note: str


class OnDemandSummaryResponse(BaseModel):
    """Summary of all on-demand requests."""
    total_requests: int
    assigned_requests: int
    unassigned_requests: int
    fulfilled_requests: int
    unfulfilled_requests: int
    assigned_pct: float
    fulfilled_pct: float
    note: str


class OnDemandManifestRequest(BaseModel):
    """Request to generate an OSRM route for a vehicle's active schedule."""
    vehicle_id: str = Field(description="Vehicle identifier to generate a route for.")


class OnDemandManifestResponse(BaseModel):
    """OSRM route manifest for a vehicle's active schedule."""
    vehicle_id: str
    stop_count: int
    stops: list["OnDemandManifestStop"]
    legs: list["OnDemandManifestLeg"]
    geometry: Optional[str]
    distance_m: Optional[float]
    duration_s: Optional[float]
    note: str


class OnDemandManifestStop(BaseModel):
    """Stop info for on-demand manifest rendering."""
    sequence: int
    lat: float
    lon: float
    stop_type: Optional[str] = None
    request_id: Optional[str] = None
    window_start_min: Optional[int] = None
    window_end_min: Optional[int] = None
    planned_arrival_min: Optional[int] = None
    planned_departure_min: Optional[int] = None


class OnDemandManifestLeg(BaseLeg):
    """Leg geometry between consecutive on-demand stops."""
    from_sequence: int
    to_sequence: int
    from_lat: float
    from_lon: float
    to_lat: float
    to_lon: float

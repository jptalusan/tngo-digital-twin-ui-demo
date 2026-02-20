from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# State / county search
# ---------------------------------------------------------------------------


class StateSearchItem(BaseModel):
    state_fips: str
    state_name: str
    state_abbr: Optional[str] = None


class CountySearchItem(BaseModel):
    geoid: str
    name: str
    state_fips: str
    county_fips: str
    geometry: Optional[dict[str, Any]] = None


class StateSearchResponse(BaseModel):
    items: list[StateSearchItem]
    message: str


class CountySearchResponse(BaseModel):
    items: list[CountySearchItem]
    message: str


# Generic list wrapper kept for endpoints that mix types (e.g. list_counties
# with optional geometry, available-areas-named).
class SearchListResponse(BaseModel):
    items: list[Any]
    message: str


# ---------------------------------------------------------------------------
# County / state geometry
# ---------------------------------------------------------------------------


class CountyFeatureResponse(BaseModel):
    item: Optional[dict[str, Any]]
    message: str


class StateFeatureCollectionResponse(BaseModel):
    items: list[dict[str, Any]]
    message: str


# ---------------------------------------------------------------------------
# Synthetic demand
# ---------------------------------------------------------------------------


class SyntheticDemandItem(BaseModel):
    origin_geoid: str
    destination_geoid: str
    origin_state_fips: str
    origin_county_fips: str
    destination_state_fips: str
    destination_county_fips: str
    origin_location: Optional[dict[str, Any]] = None
    destination_location: Optional[dict[str, Any]] = None
    departure_time_utc: Optional[str] = None
    arrival_time_utc: Optional[str] = None
    travel_time_min: Optional[float] = None
    travel_time_bin: Optional[str] = None
    travel_distance_mi: Optional[float] = None


class SyntheticDemandResponse(BaseModel):
    items: list[SyntheticDemandItem]
    message: str


# ---------------------------------------------------------------------------
# Analysis results
# ---------------------------------------------------------------------------


class AnalysisHeatmapResponse(BaseModel):
    # Each item is [lat, lon, weight] — kept as list[float] for compact payloads.
    items: list[list[float]]
    message: str


class DepartureBinItem(BaseModel):
    bin_label: str
    count: int
    kind: str


class TravelTimeBinItem(BaseModel):
    bin_label: str
    count: int
    avg_distance_mi: Optional[float] = None


class AnalysisBinsResponse(BaseModel):
    items: list[dict[str, Any]]
    message: str


class FlowBalanceItem(BaseModel):
    geoid: str
    origin_count: int
    destination_count: int
    net_flow: int


class AnalysisFlowBalanceResponse(BaseModel):
    items: list[dict[str, Any]]
    message: str


# ---------------------------------------------------------------------------
# Analysis job
# ---------------------------------------------------------------------------


class AnalysisJobResponse(BaseModel):
    job_id: str
    status: str
    message: str


# ---------------------------------------------------------------------------
# Available demand areas
# ---------------------------------------------------------------------------


class AvailableCounty(BaseModel):
    county_fips: str
    county_name: str
    geoid: str


class AvailableDemandArea(BaseModel):
    state_fips: str
    state_name: str
    counties: list[AvailableCounty]

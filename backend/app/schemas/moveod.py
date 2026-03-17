from __future__ import annotations

from datetime import date
from typing import Any, Literal, Optional

from pydantic import BaseModel, field_validator


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


# ---------------------------------------------------------------------------
# Demand generation
# ---------------------------------------------------------------------------


class GenerateDemandRequest(BaseModel):
    # --- required ---
    state_fips: str   # "47" – 2-char zero-padded
    county_fips: str  # "157" – 3-char zero-padded

    # --- date range ---
    start_date: date
    end_date: date

    # --- data source options ---
    lodes_year: int = 2022
    tiger_year: int = 2024
    use_ms_buildings: bool = True
    od_option: Literal[
        "Origin and Destination in same County",
        "Only Origin in County",
        "Only Destination in County",
    ] = "Origin and Destination in same County"

    # --- optional auxiliary inputs ---
    inrix_path: Optional[str] = None
    inrix_conversion_path: Optional[str] = None

    @field_validator("state_fips")
    @classmethod
    def _pad_state(cls, v: str) -> str:
        return v.strip().zfill(2)

    @field_validator("county_fips")
    @classmethod
    def _pad_county(cls, v: str) -> str:
        return v.strip().zfill(3)

    @field_validator("end_date")
    @classmethod
    def _end_after_start(cls, v: date, info: Any) -> date:
        start = info.data.get("start_date")
        if start and v < start:
            raise ValueError("end_date must be >= start_date")
        return v


class GenerateDemandResponse(BaseModel):
    job_id: str
    status: str   # "queued" | "running" | "done" | "error" | "already_running"
    message: str

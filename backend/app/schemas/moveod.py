from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel


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


class SearchListResponse(BaseModel):
    items: list[Any]
    message: str


class CountyFeatureResponse(BaseModel):
    item: Optional[dict[str, Any]]
    message: str


class StateFeatureCollectionResponse(BaseModel):
    items: list[dict[str, Any]]
    message: str


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

"""Unit tests for Pydantic schemas — validation logic and serialization contracts.

These tests are pure Python (no DB required) and run fast.  They validate:
- Required vs optional fields
- Field constraints (min_length, ge, etc.)
- Default values
- Model serialization via model_dump()
- Schema inheritance / composition
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.demand import DemandListResponse, DemandPreviewPoint, DemandPreviewResponse, DemandSummary
from app.schemas.moveod import (
    AnalysisJobResponse,
    CountySearchItem,
    CountySearchResponse,
    SearchListResponse,
    StateSearchItem,
    StateSearchResponse,
    SyntheticDemandItem,
    SyntheticDemandResponse,
)
from app.schemas.nearest_stops import NearestStop, NearestStopsRequest
from app.schemas.ondemand import (
    CreateDepotRequest,
    CreateDepotResponse,
    DepotVehicleSummary,
)
from app.schemas.planning import (
    AutocompleteResult,
    BaseLeg,
    Coordinate,
    DepotSummary,
    FixedLineRequest,
    FixedLineResponse,
    GtfsFeedSummary,
    Itinerary,
    Leg,
    OnDemandEvaluateRequest,
    OnDemandManifestRequest,
    OnDemandRequest,
    OnDemandResponse,
    ReverseGeocodeRequest,
    ReverseGeocodeResponse,
    ScoreBreakdown,
    VehicleSummary,
)


# ===========================================================================
# planning.py schemas
# ===========================================================================


class TestAutocompleteResult:
    def test_valid(self):
        r = AutocompleteResult(id="stop-1", name="Main St", coordinates=[35.1, -90.0])
        assert r.id == "stop-1"
        assert len(r.coordinates) == 2

    def test_requires_id(self):
        with pytest.raises(ValidationError):
            AutocompleteResult(name="Main St", coordinates=[35.1, -90.0])


class TestReverseGeocodeRequest:
    def test_valid(self):
        r = ReverseGeocodeRequest(coordinates=[35.1, -90.0])
        assert r.coordinates == [35.1, -90.0]

    def test_too_few_coords(self):
        with pytest.raises(ValidationError):
            ReverseGeocodeRequest(coordinates=[35.1])

    def test_too_many_coords(self):
        with pytest.raises(ValidationError):
            ReverseGeocodeRequest(coordinates=[35.1, -90.0, 100.0])


class TestReverseGeocodeResponse:
    def test_valid(self):
        r = ReverseGeocodeResponse(name="Main St", address="123 Main St, Memphis, TN")
        assert r.name == "Main St"


class TestFixedLineRequest:
    def test_minimal_valid(self):
        r = FixedLineRequest(
            origin=[35.1, -90.0],
            destination=[35.2, -89.9],
        )
        assert r.depart_at_min is None
        assert r.max_walk_meters == 800
        assert r.boc_request is False
        assert r.force_taxi is False

    def test_with_all_fields(self):
        r = FixedLineRequest(
            origin=[35.1, -90.0],
            destination=[35.2, -89.9],
            depart_at_min=480,
            arrive_by_min=540,
            service_date="20250101",
            agency_timezone="America/Chicago",
            max_walk_meters=1200,
            max_wait_minutes=20,
            max_invehicle_minutes=60,
            max_total_minutes=90,
            transfer_limit=1,
            score_weight_total_minutes=1.0,
            score_weight_wait_minutes=0.5,
            score_weight_walk_meters=0.001,
            boc_request=True,
            multimodal_limit=3,
            multimodal_number=2,
            force_taxi=True,
        )
        assert r.depart_at_min == 480
        assert r.boc_request is True

    def test_origin_wrong_length(self):
        with pytest.raises(ValidationError):
            FixedLineRequest(origin=[35.1], destination=[35.2, -89.9])

    def test_destination_wrong_length(self):
        with pytest.raises(ValidationError):
            FixedLineRequest(origin=[35.1, -90.0], destination=[35.2])


class TestScoreBreakdown:
    def test_valid(self):
        s = ScoreBreakdown(
            total_minutes=45.0,
            wait_minutes=5.0,
            walk_meters=300.0,
            weight_total_minutes=1.0,
            weight_wait_minutes=0.5,
            weight_walk_meters=0.001,
            score=45.8,
        )
        assert s.score == pytest.approx(45.8)


class TestOnDemandRequest:
    def test_defaults(self):
        r = OnDemandRequest(
            origin=[35.1, -90.0],
            destination=[35.2, -89.9],
        )
        assert r.passengers == 1
        assert r.pickup_window_start_min is None

    def test_with_windows(self):
        r = OnDemandRequest(
            origin=[35.1, -90.0],
            destination=[35.2, -89.9],
            passengers=2,
            pickup_window_start_min=480,
            pickup_window_end_min=510,
            dropoff_window_end_min=570,
        )
        assert r.passengers == 2
        assert r.pickup_window_start_min == 480


class TestOnDemandEvaluateRequest:
    def test_valid(self):
        r = OnDemandEvaluateRequest(vehicle_id="veh-001")
        assert r.vehicle_id == "veh-001"
        assert r.score_weight_total_minutes is None

    def test_requires_vehicle_id(self):
        with pytest.raises(ValidationError):
            OnDemandEvaluateRequest()


class TestOnDemandManifestRequest:
    def test_valid(self):
        r = OnDemandManifestRequest(vehicle_id="veh-002")
        assert r.vehicle_id == "veh-002"


class TestDepotSummary:
    def test_defaults(self):
        d = DepotSummary(depot_id="d-1", name="Depot", lat=35.0, lon=-90.0)
        assert d.h3_ids == []
        assert d.vehicles == []

    def test_with_vehicles(self):
        d = DepotSummary(
            depot_id="d-1",
            name="Depot",
            lat=35.0,
            lon=-90.0,
            h3_ids=["hex-a"],
            vehicles=[VehicleSummary(vehicle_id="v-1", capacity=4)],
        )
        assert len(d.h3_ids) == 1
        assert d.vehicles[0].vehicle_id == "v-1"


class TestGtfsFeedSummary:
    def test_valid(self):
        g = GtfsFeedSummary(gtfs_id="feed-1", gtfs_name="My Feed")
        assert g.gtfs_id == "feed-1"


# ===========================================================================
# ondemand.py schemas
# ===========================================================================


class TestCreateDepotRequest:
    def test_valid(self):
        r = CreateDepotRequest(
            coordinates=[35.1, -90.0],
            vehicles=3,
            capacity=4,
            service_zone_hex_ids=["hex-a", "hex-b"],
        )
        assert r.vehicles == 3
        assert r.h3_resolution is None

    def test_vehicles_must_be_positive(self):
        with pytest.raises(ValidationError):
            CreateDepotRequest(
                coordinates=[35.1, -90.0],
                vehicles=0,
                capacity=4,
                service_zone_hex_ids=["hex-a"],
            )

    def test_capacity_must_be_positive(self):
        with pytest.raises(ValidationError):
            CreateDepotRequest(
                coordinates=[35.1, -90.0],
                vehicles=1,
                capacity=0,
                service_zone_hex_ids=["hex-a"],
            )

    def test_coordinates_wrong_length(self):
        with pytest.raises(ValidationError):
            CreateDepotRequest(
                coordinates=[35.1],
                vehicles=1,
                capacity=4,
                service_zone_hex_ids=["hex-a"],
            )

    def test_optional_address(self):
        r = CreateDepotRequest(
            coordinates=[35.1, -90.0],
            vehicles=1,
            capacity=4,
            service_zone_hex_ids=["hex-a"],
            address="123 Main St",
        )
        assert r.address == "123 Main St"


class TestCreateDepotResponse:
    def test_serializes_correctly(self):
        r = CreateDepotResponse(
            depot_id="d-1",
            name="Depot",
            lat=35.1,
            lon=-90.0,
            address=None,
            vehicle_count=2,
            capacity=4,
            hex_count=3,
            vehicles=[
                DepotVehicleSummary(vehicle_id="v-1", capacity=4),
                DepotVehicleSummary(vehicle_id="v-2", capacity=4),
            ],
        )
        dumped = r.model_dump()
        assert dumped["vehicle_count"] == 2
        assert len(dumped["vehicles"]) == 2
        assert dumped["address"] is None


# ===========================================================================
# nearest_stops.py schemas
# ===========================================================================


class TestNearestStopsRequest:
    def test_defaults(self):
        r = NearestStopsRequest(coordinates=[35.1, -90.0])
        assert r.max_distance_m == 2000
        assert r.limit == 10

    def test_custom_values(self):
        r = NearestStopsRequest(coordinates=[35.1, -90.0], max_distance_m=500, limit=5)
        assert r.max_distance_m == 500
        assert r.limit == 5

    def test_wrong_coordinate_count(self):
        with pytest.raises(ValidationError):
            NearestStopsRequest(coordinates=[35.1])


class TestNearestStop:
    def test_valid(self):
        s = NearestStop(stop_id="S1", name="Main St", lat=35.1, lon=-90.0, distance_m=250.0)
        assert s.stop_id == "S1"
        assert s.distance_m == pytest.approx(250.0)

    def test_name_optional(self):
        s = NearestStop(stop_id="S2", name=None, lat=35.1, lon=-90.0, distance_m=100.0)
        assert s.name is None


# ===========================================================================
# demand.py schemas
# ===========================================================================


class TestDemandSummary:
    def test_valid(self):
        d = DemandSummary(demand_name="scenario-a", row_count=1500)
        assert d.row_count == 1500


class TestDemandListResponse:
    def test_empty(self):
        r = DemandListResponse(demands=[])
        assert r.demands == []

    def test_with_items(self):
        r = DemandListResponse(
            demands=[
                DemandSummary(demand_name="a", row_count=100),
                DemandSummary(demand_name="b", row_count=200),
            ]
        )
        assert len(r.demands) == 2


class TestDemandPreviewPoint:
    def test_valid(self):
        p = DemandPreviewPoint(
            home_lat=35.1,
            home_lon=-90.0,
            work_lat=35.2,
            work_lon=-89.9,
            shift=1,
            shift_start="06:00:00",
            shift_end="14:00:00",
        )
        assert p.shift == 1
        assert p.shift_start == "06:00:00"


class TestDemandPreviewResponse:
    def test_valid(self):
        r = DemandPreviewResponse(
            demand_name="scenario-x",
            total_count=1000,
            sampled_count=100,
            points=[
                DemandPreviewPoint(
                    home_lat=35.1,
                    home_lon=-90.0,
                    work_lat=35.2,
                    work_lon=-89.9,
                    shift=2,
                    shift_start="14:00:00",
                    shift_end="22:00:00",
                )
            ],
        )
        assert r.sampled_count == 100
        assert len(r.points) == 1


# ===========================================================================
# moveod.py schemas
# ===========================================================================


class TestStateSearchItem:
    def test_valid(self):
        s = StateSearchItem(state_fips="47", state_name="Tennessee", state_abbr="TN")
        assert s.state_abbr == "TN"

    def test_abbr_optional(self):
        s = StateSearchItem(state_fips="47", state_name="Tennessee")
        assert s.state_abbr is None


class TestCountySearchItem:
    def test_valid(self):
        c = CountySearchItem(geoid="47157", name="Shelby", state_fips="47", county_fips="157")
        assert c.geoid == "47157"
        assert c.geometry is None


class TestStateSearchResponse:
    def test_typed_items(self):
        r = StateSearchResponse(
            items=[StateSearchItem(state_fips="47", state_name="Tennessee")],
            message="ok",
        )
        assert isinstance(r.items[0], StateSearchItem)


class TestCountySearchResponse:
    def test_typed_items(self):
        r = CountySearchResponse(
            items=[CountySearchItem(geoid="47157", name="Shelby", state_fips="47", county_fips="157")],
            message="ok",
        )
        assert isinstance(r.items[0], CountySearchItem)


class TestSearchListResponse:
    def test_accepts_any_items(self):
        r = SearchListResponse(items=[{"a": 1}, {"b": 2}], message="ok")
        assert len(r.items) == 2


class TestSyntheticDemandItem:
    def test_valid_minimal(self):
        item = SyntheticDemandItem(
            origin_geoid="470000001001",
            destination_geoid="470000002001",
            origin_state_fips="47",
            origin_county_fips="001",
            destination_state_fips="47",
            destination_county_fips="002",
        )
        assert item.travel_time_min is None
        assert item.departure_time_utc is None

    def test_with_all_fields(self):
        item = SyntheticDemandItem(
            origin_geoid="470000001001",
            destination_geoid="470000002001",
            origin_state_fips="47",
            origin_county_fips="001",
            destination_state_fips="47",
            destination_county_fips="002",
            departure_time_utc="2025-01-01T08:00:00+00:00",
            arrival_time_utc="2025-01-01T09:00:00+00:00",
            travel_time_min=60.0,
            travel_time_bin="45-60",
            travel_distance_mi=35.5,
        )
        assert item.travel_time_min == pytest.approx(60.0)


class TestSyntheticDemandResponse:
    def test_typed_items(self):
        r = SyntheticDemandResponse(
            items=[
                SyntheticDemandItem(
                    origin_geoid="470000001001",
                    destination_geoid="470000002001",
                    origin_state_fips="47",
                    origin_county_fips="001",
                    destination_state_fips="47",
                    destination_county_fips="002",
                )
            ],
            message="ok",
        )
        assert isinstance(r.items[0], SyntheticDemandItem)


class TestAnalysisJobResponse:
    def test_valid(self):
        r = AnalysisJobResponse(job_id="abc-123", status="queued", message="analysis queued")
        assert r.status == "queued"

    def test_empty_job_id_for_cached(self):
        """already_analyzed returns an empty job_id by convention."""
        r = AnalysisJobResponse(job_id="", status="already_analyzed", message="already analyzed")
        assert r.job_id == ""

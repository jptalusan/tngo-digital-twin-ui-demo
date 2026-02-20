"""HTTP endpoint tests for the MoveOD router.

All tests run against the test database (no synthetic demand is pre-loaded,
so we test empty-but-valid responses and input validation).
"""

from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# State search
# ---------------------------------------------------------------------------


def test_states_search_returns_200(client):
    response = client.get("/api/states/search", params={"q": "Ten"})
    assert response.status_code == 200
    body = response.json()
    assert "items" in body
    assert "message" in body
    assert isinstance(body["items"], list)


def test_states_search_empty_query_returns_400(client):
    response = client.get("/api/states/search", params={"q": ""})
    assert response.status_code == 400


def test_states_search_missing_q_returns_422(client):
    response = client.get("/api/states/search")
    assert response.status_code == 422


def test_states_search_no_results_message(client):
    response = client.get("/api/states/search", params={"q": "ZZZNOMATCH"})
    assert response.status_code == 200
    body = response.json()
    assert body["items"] == []
    assert "no matching" in body["message"]


def test_states_search_limit_respected(client):
    response = client.get("/api/states/search", params={"q": "a", "limit": 3})
    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) <= 3


def test_states_search_limit_too_large_returns_422(client):
    response = client.get("/api/states/search", params={"q": "a", "limit": 21})
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# County search
# ---------------------------------------------------------------------------


def test_counties_search_returns_200(client):
    response = client.get("/api/counties/search", params={"q": "Shelby"})
    assert response.status_code == 200
    body = response.json()
    assert "items" in body


def test_counties_search_empty_query_returns_400(client):
    response = client.get("/api/counties/search", params={"q": ""})
    assert response.status_code == 400


def test_counties_search_with_unknown_state_returns_empty(client):
    response = client.get(
        "/api/counties/search",
        params={"q": "County", "state_name": "ZZZNOMATCH"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["items"] == []
    assert "unknown state" in body["message"]


def test_counties_search_with_state_fips_filter(client):
    """Passing state_fips should not break the endpoint even with no data."""
    response = client.get(
        "/api/counties/search",
        params={"q": "Shelby", "state_fips": "47"},
    )
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# Counties in a state
# ---------------------------------------------------------------------------


def test_list_counties_unknown_state_returns_empty(client):
    response = client.get("/api/states/ZZ/counties")
    assert response.status_code == 200
    body = response.json()
    assert body["items"] == []
    assert "unknown" in body["message"]


def test_list_counties_invalid_order_returns_400(client):
    response = client.get("/api/states/47/counties", params={"order": "population"})
    assert response.status_code == 400


def test_list_counties_geometry_flag(client):
    """include_geometry=true should not crash even when no data is loaded."""
    response = client.get("/api/states/47/counties", params={"include_geometry": "true"})
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# County geometry
# ---------------------------------------------------------------------------


def test_county_geometry_missing_params_returns_400(client):
    """Neither geoid nor (state_fips + name) provided."""
    response = client.get("/api/counties/geometry")
    assert response.status_code == 400


def test_county_geometry_partial_params_returns_400(client):
    """state_fips without name is insufficient."""
    response = client.get("/api/counties/geometry", params={"state_fips": "47"})
    assert response.status_code == 400


def test_county_geometry_not_found(client):
    response = client.get("/api/counties/geometry", params={"geoid": "99999"})
    assert response.status_code == 200
    body = response.json()
    assert body["item"] is None
    assert "not found" in body["message"]


def test_county_geometry_by_geoid(client):
    response = client.get("/api/counties/geometry", params={"geoid": "47157"})
    assert response.status_code == 200
    # May or may not have data — just check shape
    body = response.json()
    assert "item" in body
    assert "message" in body


# ---------------------------------------------------------------------------
# State geometries
# ---------------------------------------------------------------------------


def test_state_geometries_returns_200(client):
    response = client.get("/api/states/geometry")
    assert response.status_code == 200
    body = response.json()
    assert "items" in body
    assert isinstance(body["items"], list)


# ---------------------------------------------------------------------------
# Synthetic demand
# ---------------------------------------------------------------------------


def test_synthetic_demand_missing_params_returns_422(client):
    response = client.get("/api/moveod/synthetic-demand")
    assert response.status_code == 422


def test_synthetic_demand_valid_params(client):
    response = client.get(
        "/api/moveod/synthetic-demand",
        params={"state_fips": "47", "county_fips": "157"},
    )
    assert response.status_code == 200
    body = response.json()
    assert "items" in body
    assert isinstance(body["items"], list)


def test_synthetic_demand_fips_too_short_returns_422(client):
    response = client.get(
        "/api/moveod/synthetic-demand",
        params={"state_fips": "4", "county_fips": "157"},
    )
    assert response.status_code == 422


def test_synthetic_demand_county_fips_too_short_returns_422(client):
    response = client.get(
        "/api/moveod/synthetic-demand",
        params={"state_fips": "47", "county_fips": "15"},
    )
    assert response.status_code == 422


def test_synthetic_demand_limit_respected(client):
    response = client.get(
        "/api/moveod/synthetic-demand",
        params={"state_fips": "47", "county_fips": "157", "limit": 10},
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) <= 10


# ---------------------------------------------------------------------------
# MoveOD analysis endpoints
# ---------------------------------------------------------------------------


def test_analyze_moveod_triggers_job(client):
    response = client.post(
        "/api/moveod/analyze",
        params={"state_fips": "47", "county_fips": "157"},
    )
    # 202 if queued, 200 if already analyzed, 200 if no data
    assert response.status_code in (200, 202)
    body = response.json()
    assert "job_id" in body
    assert "status" in body
    assert "message" in body


def test_analyze_moveod_force_recompute(client):
    response = client.post(
        "/api/moveod/analyze",
        params={"state_fips": "47", "county_fips": "157", "force": "true"},
    )
    assert response.status_code in (200, 202)


def test_analyze_moveod_missing_params_returns_422(client):
    response = client.post("/api/moveod/analyze")
    assert response.status_code == 422


def test_get_analysis_status_not_found(client):
    response = client.get("/api/moveod/analysis/status", params={"job_id": "no-such-job"})
    assert response.status_code == 404


def test_get_analysis_status_by_area_not_started(client):
    response = client.get(
        "/api/moveod/analysis/status-by-area",
        params={"state_fips": "99", "county_fips": "999"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "not_started"


def test_get_heatmap_returns_200(client):
    response = client.get(
        "/api/moveod/analysis/heatmap",
        params={"state_fips": "47", "county_fips": "157", "kind": "origin"},
    )
    assert response.status_code == 200
    body = response.json()
    assert "items" in body
    assert isinstance(body["items"], list)


def test_get_heatmap_invalid_kind_returns_422(client):
    response = client.get(
        "/api/moveod/analysis/heatmap",
        params={"state_fips": "47", "county_fips": "157", "kind": "invalid"},
    )
    assert response.status_code == 422


def test_get_departure_bins_returns_200(client):
    response = client.get(
        "/api/moveod/analysis/departure-bins",
        params={"state_fips": "47", "county_fips": "157"},
    )
    assert response.status_code == 200
    body = response.json()
    assert "items" in body


def test_get_departure_bins_invalid_kind_returns_422(client):
    response = client.get(
        "/api/moveod/analysis/departure-bins",
        params={"state_fips": "47", "county_fips": "157", "kind": "bad"},
    )
    assert response.status_code == 422


def test_get_travel_time_bins_returns_200(client):
    response = client.get(
        "/api/moveod/analysis/travel-time-bins",
        params={"state_fips": "47", "county_fips": "157"},
    )
    assert response.status_code == 200


def test_get_top_origins_returns_200(client):
    response = client.get(
        "/api/moveod/analysis/top-origins",
        params={"state_fips": "47", "county_fips": "157"},
    )
    assert response.status_code == 200
    body = response.json()
    assert "items" in body


def test_get_flow_balance_returns_200(client):
    response = client.get(
        "/api/moveod/analysis/flow-balance",
        params={"state_fips": "47", "county_fips": "157"},
    )
    assert response.status_code == 200
    body = response.json()
    assert "items" in body


def test_available_areas_returns_200(client):
    response = client.get("/api/moveod/analysis/available-areas")
    assert response.status_code == 200
    body = response.json()
    assert "items" in body
    # Each item must be a dict with state_fips and county_fips (one per pair)
    for item in body["items"]:
        assert "state_fips" in item
        assert "county_fips" in item
        # county_fips must be a string, not a list (regression for the serialization bug)
        assert isinstance(item["county_fips"], str)


def test_available_areas_named_returns_200(client):
    response = client.get("/api/moveod/analysis/available-areas-named")
    assert response.status_code == 200
    body = response.json()
    assert "items" in body

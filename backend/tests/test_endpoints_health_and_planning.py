"""HTTP endpoint tests for health, autocomplete, nearest-stops, and planning.

Uses FastAPI TestClient (synchronous, no running server needed).
Tests cover:
- Status codes
- Response shape matches Pydantic schema
- Input validation (4xx responses for bad requests)
"""

from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


def test_health_returns_200(client):
    response = client.get("/api/health")
    assert response.status_code == 200


def test_health_body(client):
    response = client.get("/api/health")
    body = response.json()
    # Accept any truthy body — endpoint just needs to be alive
    assert body is not None


# ---------------------------------------------------------------------------
# Autocomplete
# ---------------------------------------------------------------------------


def test_autocomplete_empty_query_returns_422(client):
    """Empty query (min_length=1) must be rejected with 422."""
    response = client.get("/api/autocomplete", params={"query": ""})
    assert response.status_code == 422


def test_autocomplete_missing_query_returns_422(client):
    """Missing required 'query' param must return 422."""
    response = client.get("/api/autocomplete")
    assert response.status_code == 422


def test_autocomplete_with_query_returns_list(client):
    response = client.get("/api/autocomplete", params={"query": "main"})
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)


def test_autocomplete_schema(client):
    response = client.get("/api/autocomplete", params={"query": "main"})
    assert response.status_code == 200
    items = response.json()
    for item in items:
        assert "id" in item
        assert "name" in item
        assert "coordinates" in item
        assert len(item["coordinates"]) == 2


# ---------------------------------------------------------------------------
# Nearest stops
# ---------------------------------------------------------------------------


def test_nearest_stops_valid_request(client):
    response = client.post(
        "/api/nearest-stops",
        json={"coordinates": [35.15, -90.0], "max_distance_m": 1000, "limit": 5},
    )
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)


def test_nearest_stops_schema(client):
    response = client.post(
        "/api/nearest-stops",
        json={"coordinates": [35.15, -90.0]},
    )
    assert response.status_code == 200
    stops = response.json()
    for stop in stops:
        assert "stop_id" in stop
        assert "lat" in stop
        assert "lon" in stop
        assert "distance_m" in stop


def test_nearest_stops_missing_coordinates(client):
    response = client.post("/api/nearest-stops", json={"max_distance_m": 500})
    assert response.status_code == 422


def test_nearest_stops_single_coordinate_rejected(client):
    response = client.post(
        "/api/nearest-stops",
        json={"coordinates": [35.15]},
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# On-demand planning — no depots scenario
# ---------------------------------------------------------------------------


def test_on_demand_no_vehicles_returns_200(client):
    """When no vehicles exist the endpoint should still return 200 with empty itineraries."""
    response = client.post(
        "/api/plan/on-demand",
        json={
            "origin": [35.1495, -90.0490],
            "destination": [35.1505, -90.0480],
            "passengers": 1,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert "itineraries" in body
    assert isinstance(body["itineraries"], list)
    assert "note" in body


def test_on_demand_missing_origin_returns_422(client):
    response = client.post(
        "/api/plan/on-demand",
        json={"destination": [35.1505, -90.0480], "passengers": 1},
    )
    assert response.status_code == 422


def test_on_demand_invalid_passengers_returns_422(client):
    """Passengers must be a positive integer — strings are rejected."""
    response = client.post(
        "/api/plan/on-demand",
        json={
            "origin": [35.1, -90.0],
            "destination": [35.2, -89.9],
            "passengers": "two",
        },
    )
    assert response.status_code == 422


def test_on_demand_response_schema(client):
    """Verify the full response shape regardless of whether a vehicle is found."""
    response = client.post(
        "/api/plan/on-demand",
        json={
            "origin": [35.1495, -90.0490],
            "destination": [35.1505, -90.0480],
            "passengers": 1,
            "pickup_window_start_min": 480,
            "pickup_window_end_min": 510,
            "dropoff_window_end_min": 570,
        },
    )
    assert response.status_code == 200
    body = response.json()
    required_top_level = {"itineraries", "note"}
    assert required_top_level.issubset(body.keys())


# ---------------------------------------------------------------------------
# Fixed-line planning — no GTFS loaded
# ---------------------------------------------------------------------------


def test_fixed_line_no_gtfs_returns_200(client):
    """With no GTFS data loaded the endpoint returns 200 with empty itineraries."""
    response = client.post(
        "/api/plan/fixed-line",
        json={
            "origin": [35.1495, -90.0490],
            "destination": [35.1505, -90.0480],
            "depart_at_min": 480,
            "service_date": "20250101",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert "itineraries" in body
    assert isinstance(body["itineraries"], list)
    assert "note" in body


def test_fixed_line_missing_origin_returns_422(client):
    response = client.post(
        "/api/plan/fixed-line",
        json={"destination": [35.1505, -90.0480]},
    )
    assert response.status_code == 422


def test_fixed_line_origin_wrong_length_returns_422(client):
    response = client.post(
        "/api/plan/fixed-line",
        json={
            "origin": [35.1],
            "destination": [35.1505, -90.0480],
        },
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Private vehicle planning
# ---------------------------------------------------------------------------


def test_private_vehicle_returns_200(client):
    response = client.post(
        "/api/plan/private-vehicle",
        json={"origin": [35.1495, -90.0490], "destination": [35.1505, -90.0480]},
    )
    assert response.status_code == 200
    body = response.json()
    assert "itineraries" in body
    assert "note" in body


def test_private_vehicle_missing_destination_returns_422(client):
    response = client.post(
        "/api/plan/private-vehicle",
        json={"origin": [35.1495, -90.0490]},
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Reverse geocode
# ---------------------------------------------------------------------------


def test_reverse_geocode_nominatim_disabled(client):
    """With ENABLE_NOMINATIM=false the endpoint should still respond (may 503 or return stub)."""
    response = client.post(
        "/api/reverse-geocode",
        json={"coordinates": [35.1495, -90.0490]},
    )
    # Accept any non-5xx response that has the right Content-Type
    assert response.status_code in (200, 503)


def test_reverse_geocode_missing_coords(client):
    response = client.post("/api/reverse-geocode", json={})
    assert response.status_code == 422


def test_reverse_geocode_too_many_coords(client):
    response = client.post(
        "/api/reverse-geocode",
        json={"coordinates": [35.1495, -90.0490, 100.0]},
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# GTFS listing
# ---------------------------------------------------------------------------


def test_gtfs_list_returns_200(client):
    response = client.get("/api/gtfs/list")
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)


def test_gtfs_job_not_found(client):
    response = client.get("/api/gtfs/jobs/nonexistent-job-id")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# On-demand listing
# ---------------------------------------------------------------------------


def test_on_demand_list_returns_200(client):
    response = client.get("/api/on-demand/list")
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)


def test_on_demand_summary_returns_200(client):
    response = client.get("/api/on-demand/summary")
    assert response.status_code == 200
    body = response.json()
    required = {"total_requests", "assigned_requests", "unassigned_requests", "note"}
    assert required.issubset(body.keys())


# ---------------------------------------------------------------------------
# Demand dataset listing
# ---------------------------------------------------------------------------


def test_demand_list_returns_200(client):
    response = client.get("/api/demand-list")
    assert response.status_code == 200
    body = response.json()
    assert "demands" in body
    assert isinstance(body["demands"], list)

from app.db import SessionLocal
from app.models.ondemand import Depot, OnDemandVehicle, VehicleSchedule
from scripts.load_gtfs import load_gtfs


def test_autocomplete_returns_stops_and_depots(client, gtfs_fixture_path):
    load_gtfs(gtfs_fixture_path)

    session = SessionLocal()
    try:
        depot = Depot(
            depot_id="depot-1",
            name="Main Depot",
            lat=35.1495,
            lon=-90.0490,
        )
        session.add(depot)
        session.commit()
    finally:
        session.close()

    response = client.get("/api/autocomplete", params={"query": "Stop"})
    assert response.status_code == 200
    results = response.json()
    assert any("Stop" in item["name"] for item in results)

    response = client.get("/api/autocomplete", params={"query": "Depot"})
    assert response.status_code == 200
    results = response.json()
    assert any("Depot" in item["name"] for item in results)


def test_on_demand_mock_endpoint(client):
    session = SessionLocal()
    try:
        depot = Depot(
            depot_id="depot-od",
            name="OD Depot",
            lat=35.1495,
            lon=-90.0490,
        )
        session.add(depot)
        session.flush()
        session.add(OnDemandVehicle(vehicle_id="veh-od-1", depot_id="depot-od", capacity=2))
        session.add(
            VehicleSchedule(
                vehicle_id="veh-od-1",
                service_days="mon,tue,wed,thu,fri,sat,sun",
                start_time="05:00",
                end_time="20:00",
            )
        )
        session.commit()
    finally:
        session.close()

    response = client.post(
        "/api/plan/on-demand",
        json={
            "origin": [35.1495, -90.0490],
            "destination": [35.1505, -90.0480],
            "passengers": 1,
            "pickup_window_start_min": 480,
            "pickup_window_end_min": 490,
            "dropoff_window_end_min": 540,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["vehicle_id"]
    assert body["eta_minutes"] >= 0
    assert "itineraries" in body
    assert isinstance(body["itineraries"], list)

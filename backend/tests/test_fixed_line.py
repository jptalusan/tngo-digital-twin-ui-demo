from app.schemas import planning as schemas
from app.services import planning as planning_service
from app.db import SessionLocal
from scripts.load_gtfs import load_gtfs


def test_fixed_line_itinerary(client, gtfs_fixture_path):
    load_gtfs(gtfs_fixture_path)

    payload = schemas.FixedLineRequest(
        origin=[35.1495, -90.0490],
        destination=[35.1505, -90.0480],
        depart_at_min=480,
        service_date="20250101",
        max_walk_meters=1500,
        max_wait_minutes=30,
        max_invehicle_minutes=60,
        max_total_minutes=90,
        score_weight_total_minutes=1.0,
        score_weight_wait_minutes=0.5,
        score_weight_walk_meters=0.001,
    )

    response = client.post("/api/plan/fixed-line", json=payload.model_dump())
    assert response.status_code == 200
    body = response.json()
    assert body["itineraries"], "Expected at least one itinerary"

    itinerary = body["itineraries"][0]
    assert itinerary["total_wait_s"] >= 0
    assert itinerary["total_invehicle_s"] > 0
    assert itinerary["score"]["score"] > 0
    assert itinerary["score"]["weight_total_minutes"] == 1.0


def test_timezone_mismatch_returns_400(client, gtfs_fixture_path):
    load_gtfs(gtfs_fixture_path)
    payload = schemas.FixedLineRequest(
        origin=[35.1495, -90.0490],
        destination=[35.1505, -90.0480],
        depart_at_min=480,
        service_date="20250101",
        agency_timezone="UTC",
    )
    response = client.post("/api/plan/fixed-line", json=payload.model_dump())
    assert response.status_code == 400


def test_service_date_filters_out_inactive(client, gtfs_fixture_path):
    load_gtfs(gtfs_fixture_path)
    payload = schemas.FixedLineRequest(
        origin=[35.1495, -90.0490],
        destination=[35.1505, -90.0480],
        depart_at_min=480,
        service_date="19990101",
    )
    response = client.post("/api/plan/fixed-line", json=payload.model_dump())
    assert response.status_code == 200
    assert response.json()["itineraries"] == []


def test_transfer_itinerary(client, gtfs_transfer_fixture_path):
    load_gtfs(gtfs_transfer_fixture_path)
    payload = schemas.FixedLineRequest(
        origin=[35.1495, -90.0490],
        destination=[35.1505, -90.0480],
        depart_at_min=480,
        service_date="20250101",
        transfer_limit=1,
    )
    response = client.post("/api/plan/fixed-line", json=payload.model_dump())
    assert response.status_code == 200
    itineraries = response.json()["itineraries"]
    assert itineraries
    legs = itineraries[0]["legs"]
    assert any(leg["mode"] == "transfer" for leg in legs)


def test_time_parsing_consistency():
    assert planning_service._parse_time_min("08:10:00") == 490
    assert planning_service._parse_time_min("00:15:30") == 16

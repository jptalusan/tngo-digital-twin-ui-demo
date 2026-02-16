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


def test_time_parsing_consistency():
    assert planning_service._parse_time_min("08:10:00") == 490
    assert planning_service._parse_time_min("00:15:30") == 16

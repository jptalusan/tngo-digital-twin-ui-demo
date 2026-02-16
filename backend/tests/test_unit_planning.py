from app.services import planning as planning_service
from app.db import SessionLocal
from scripts.load_gtfs import load_gtfs


def test_find_nearby_stops(gtfs_fixture_path):
    load_gtfs(gtfs_fixture_path)

    session = SessionLocal()
    try:
        candidates = planning_service.find_nearby_stops(
            session, 35.1495, -90.0490, max_distance_m=500
        )
        assert candidates
        assert any(c.stop.stop_id == "S1" for c in candidates)
    finally:
        session.close()


def test_find_transit_candidates(gtfs_fixture_path):
    load_gtfs(gtfs_fixture_path)

    session = SessionLocal()
    try:
        access = planning_service.find_nearby_stops(
            session, 35.1495, -90.0490, max_distance_m=1500
        )
        egress = planning_service.find_nearby_stops(
            session, 35.1505, -90.0480, max_distance_m=1500
        )
        candidates = planning_service.find_transit_candidates(
            session, access, egress, depart_at_min=480, max_wait_minutes=30, max_invehicle_minutes=60
        )
        assert candidates
        assert any(c.trip_id == "T1" for c in candidates)
    finally:
        session.close()


def test_build_fixed_line_itineraries_scoring(gtfs_fixture_path):
    load_gtfs(gtfs_fixture_path)

    session = SessionLocal()
    try:
        constraints = planning_service.FixedLineConstraints(
            max_walk_meters=1500,
            max_wait_minutes=30,
            max_invehicle_minutes=60,
            max_total_minutes=90,
            score_weight_total_minutes=1.0,
            score_weight_wait_minutes=0.5,
            score_weight_walk_meters=0.001,
        )
        inputs = planning_service.FixedLineInputs(
            origin_lat=35.1495,
            origin_lon=-90.0490,
            destination_lat=35.1505,
            destination_lon=-90.0480,
            depart_at_min=480,
            constraints=constraints,
        )
        itineraries = planning_service.build_fixed_line_itineraries(session, inputs)
        assert itineraries
        candidate = itineraries[0]
        assert candidate.score > 0
        assert candidate.total_invehicle_s > 0
        assert candidate.score_breakdown["weight_total_minutes"] == 1.0
    finally:
        session.close()

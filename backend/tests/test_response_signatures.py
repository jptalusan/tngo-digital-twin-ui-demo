from scripts.load_gtfs import load_gtfs


def test_fixed_line_signature(client, gtfs_fixture_path):
    load_gtfs(gtfs_fixture_path)
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
    if body["itineraries"]:
        itinerary = body["itineraries"][0]
        assert "itinerary_id" in itinerary
        assert "legs" in itinerary
        assert "geometry" in itinerary
        assert "total_transit_distance_m" in itinerary
        assert "total_vehicle_distance_m" in itinerary
        assert "metrics" in body
        assert "overall" in body["metrics"]
        assert "geometry" in body["metrics"]["overall"]
        assert isinstance(itinerary["legs"], list)
        if itinerary["legs"]:
            assert "geometry" in itinerary["legs"][0]


def test_on_demand_signature(client):
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
    assert "itineraries" in body
    assert isinstance(body["itineraries"], list)
    if body["itineraries"] and body.get("metrics"):
        itinerary = body["itineraries"][0]
        assert "itinerary_id" in itinerary
        assert "legs" in itinerary
        assert "total_transit_distance_m" in itinerary
        assert "total_vehicle_distance_m" in itinerary
        assert "overall" in body["metrics"]
        assert "geometry" in body["metrics"]["overall"]
        assert "geometry" in itinerary
        if itinerary["legs"]:
            assert "geometry" in itinerary["legs"][0]


def test_multimodal_signature(client, gtfs_fixture_path):
    load_gtfs(gtfs_fixture_path)
    response = client.post(
        "/api/plan/multimodal",
        json={
            "origin": [35.1495, -90.0490],
            "destination": [35.1505, -90.0480],
            "depart_at_min": 480,
            "service_date": "20250101",
        },
    )
    assert response.status_code == 200
    body = response.json()
    if body["itineraries"]:
        itinerary = body["itineraries"][0]
        assert "itinerary_id" in itinerary
        assert "legs" in itinerary
        assert "metrics" in itinerary
        assert "overall" in itinerary["metrics"]
        assert "total_transit_distance_m" in itinerary["metrics"]["overall"]
        assert "total_vehicle_distance_m" in itinerary["metrics"]["overall"]
        assert "metrics" in body
        assert "overall" in body["metrics"]
        assert "geometry" in body["metrics"]["overall"]
        assert body["best_itinerary"] in {item["itinerary_id"] for item in body["itineraries"]}

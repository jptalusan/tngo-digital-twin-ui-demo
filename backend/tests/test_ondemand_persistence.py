from geoalchemy2 import WKTElement

from app.db import SessionLocal
from app.models.ondemand import Depot, Vehicle, VehicleSchedule, VehicleRoute, VehicleRouteStop


def test_on_demand_persists_route(client):
    session = SessionLocal()
    try:
        depot = Depot(
            depot_id="depot-od",
            name="OD Depot",
            lat=35.1495,
            lon=-90.0490,
            service_zone=WKTElement(
                "POLYGON((-90.06 35.14, -90.06 35.16, -90.03 35.16, -90.03 35.14, -90.06 35.14))",
                srid=4326,
            ),
        )
        session.add(depot)
        session.add(Vehicle(vehicle_id="veh-od-1", depot_id="depot-od", capacity=4))
        session.add(
            VehicleSchedule(
                vehicle_id="veh-od-1",
                service_days="mon,tue,wed,thu,fri",
                start_time="06:00",
                end_time="22:00",
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
            "pickup_window_end_min": 520,
            "dropoff_window_end_min": 600,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["vehicle_id"] == "veh-od-1"

    session = SessionLocal()
    try:
        route = (
            session.query(VehicleRoute)
            .filter(VehicleRoute.vehicle_id == "veh-od-1", VehicleRoute.status == "active")
            .first()
        )
        assert route is not None
        stops = (
            session.query(VehicleRouteStop)
            .filter(VehicleRouteStop.route_id == route.route_id)
            .order_by(VehicleRouteStop.sequence)
            .all()
        )
        assert len(stops) == 2
        assert stops[0].stop_type == "pickup"
        assert stops[1].stop_type == "dropoff"
        assert stops[0].request_id is not None
    finally:
        session.close()

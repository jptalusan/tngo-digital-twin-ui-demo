from geoalchemy2 import WKTElement

from app.db import SessionLocal
from app.models.ondemand import Depot, Vehicle, VehicleSchedule


def test_depot_vehicle_relationships():
    session = SessionLocal()
    try:
        depot = Depot(
            depot_id="depot-unit",
            name="Depot Unit",
            lat=35.0,
            lon=-90.0,
            service_zone=WKTElement(
                "POLYGON((-90.02 34.99, -90.02 35.01, -89.98 35.01, -89.98 34.99, -90.02 34.99))",
                srid=4326,
            ),
        )
        session.add(depot)
        session.add_all(
            [
                Vehicle(vehicle_id="veh-001", depot_id="depot-unit", capacity=4),
                Vehicle(vehicle_id="veh-002", depot_id="depot-unit", capacity=4),
            ]
        )
        session.add(
            VehicleSchedule(
                vehicle_id="veh-001",
                service_days="mon,tue",
                start_time="06:00",
                end_time="10:00",
            )
        )
        session.commit()

        refreshed = session.get(Depot, depot.id)
        assert refreshed is not None
        assert len(refreshed.vehicles) == 2
        assert any(v.vehicle_id == "veh-001" for v in refreshed.vehicles)
    finally:
        session.close()

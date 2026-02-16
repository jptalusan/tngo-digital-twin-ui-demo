from __future__ import annotations

import os
import uuid
from datetime import datetime
from pathlib import Path
import sys

from dotenv import load_dotenv
from geoalchemy2 import WKTElement

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.db import SessionLocal
from app.models.ondemand import Depot, Vehicle, VehicleSchedule

load_dotenv()


def _prompt(message: str, default: str | None = None) -> str:
    suffix = f" [{default}]" if default else ""
    value = input(f"{message}{suffix}: ").strip()
    return value or (default or "")


def _prompt_float(message: str, default: str | None = None) -> float:
    while True:
        value = _prompt(message, default)
        try:
            return float(value)
        except ValueError:
            print("Enter a number")


def _prompt_int(message: str, default: str | None = None) -> int:
    while True:
        value = _prompt(message, default)
        try:
            return int(value)
        except ValueError:
            print("Enter an integer")


def _buffer_polygon_wkt(lat: float, lon: float, meters: float) -> str:
    meters_per_deg_lat = 111_320
    meters_per_deg_lon = 111_320 * max(0.1, abs(__import__("math").cos(lat * __import__("math").pi / 180)))
    dlat = meters / meters_per_deg_lat
    dlon = meters / meters_per_deg_lon

    north = lat + dlat
    south = lat - dlat
    east = lon + dlon
    west = lon - dlon

    return (
        f"POLYGON(({west} {south}, {west} {north}, {east} {north}, {east} {south}, {west} {south}))"
    )


def main() -> None:
    depot_name = _prompt("Depot name", os.getenv("DEFAULT_DEPOT_NAME", "Main Depot"))
    depot_lat = _prompt_float("Depot latitude", os.getenv("DEFAULT_DEPOT_LAT", "35.1495"))
    depot_lng = _prompt_float("Depot longitude", os.getenv("DEFAULT_DEPOT_LNG", "-90.0490"))
    vehicle_count = _prompt_int("Vehicle count", os.getenv("DEFAULT_VEHICLE_COUNT", "10"))
    capacity = _prompt_int("Vehicle capacity", os.getenv("DEFAULT_VEHICLE_CAPACITY", "4"))
    service_days = _prompt("Service days (comma-separated)", os.getenv("DEFAULT_SERVICE_DAYS", "mon,tue,wed,thu,fri"))
    service_start = _prompt("Service start time (HH:MM)", os.getenv("DEFAULT_SERVICE_START", "06:00"))
    service_end = _prompt("Service end time (HH:MM)", os.getenv("DEFAULT_SERVICE_END", "22:00"))
    service_zone_m = _prompt_float("Service zone radius (meters)", os.getenv("DEFAULT_SERVICE_ZONE_METERS", "3000"))

    depot_id = f"depot-{uuid.uuid4().hex[:8]}"
    zone_wkt = _buffer_polygon_wkt(depot_lat, depot_lng, service_zone_m)

    session = SessionLocal()
    try:
        depot = Depot(
            depot_id=depot_id,
            name=depot_name,
            lat=depot_lat,
            lon=depot_lng,
            service_zone=WKTElement(zone_wkt, srid=4326),
        )
        session.add(depot)

        vehicles = []
        schedules = []
        for i in range(vehicle_count):
            vehicle_id = f"veh-{i + 1:03d}"
            vehicles.append(
                Vehicle(
                    vehicle_id=vehicle_id,
                    depot_id=depot_id,
                    capacity=capacity,
                    status="available",
                )
            )
            schedules.append(
                VehicleSchedule(
                    vehicle_id=vehicle_id,
                    service_days=service_days,
                    start_time=service_start,
                    end_time=service_end,
                )
            )

        session.add_all(vehicles + schedules)
        session.commit()
    finally:
        session.close()

    print(
        f"Loaded depot {depot_name} with {vehicle_count} vehicles at {datetime.now().isoformat()}"
    )


if __name__ == "__main__":
    main()

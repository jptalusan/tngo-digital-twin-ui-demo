from __future__ import annotations

import csv
from pathlib import Path
import sys

from geoalchemy2 import WKTElement

sys.path.append(str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text

from app.db import SessionLocal
from app.models.ondemand import Depot, Vehicle, VehicleSchedule


def _read_csv(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def main() -> None:
    base = Path(__file__).resolve().parent / "data" / "on-demand"
    depots_path = base / "depots.csv"
    vehicles_path = base / "vehicles.csv"
    schedules_path = base / "vehicle_schedules.csv"

    depots = _read_csv(depots_path)
    vehicles = _read_csv(vehicles_path)
    schedules = _read_csv(schedules_path)

    session = SessionLocal()
    try:
        for table in [
            "vehicle_route_stop",
            "vehicle_route",
            "ondemand_trip",
            "ondemand_request",
            "vehicle_schedule",
            "vehicle",
            "depot",
        ]:
            session.execute(text(f"TRUNCATE TABLE {table} RESTART IDENTITY CASCADE"))
        session.commit()

        for row in depots:
            session.add(
                Depot(
                    depot_id=row["depot_id"],
                    name=row["name"],
                    lat=float(row["lat"]),
                    lon=float(row["lon"]),
                    service_zone=WKTElement(row["service_zone_wkt"], srid=4326)
                    if row.get("service_zone_wkt")
                    else None,
                )
            )

        for row in vehicles:
            session.add(
                Vehicle(
                    vehicle_id=row["vehicle_id"],
                    depot_id=row["depot_id"],
                    capacity=int(row["capacity"]),
                    status=row.get("status"),
                )
            )

        for row in schedules:
            session.add(
                VehicleSchedule(
                    vehicle_id=row["vehicle_id"],
                    service_days=row["service_days"],
                    start_time=row["start_time"],
                    end_time=row["end_time"],
                )
            )

        session.commit()
        print("Loaded on-demand CSV data")
    finally:
        session.close()


if __name__ == "__main__":
    main()

from __future__ import annotations

import argparse
import csv
import io
import zipfile
from pathlib import Path
from typing import Iterable
import sys

from sqlalchemy.orm import Session
from sqlalchemy import text

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.db import SessionLocal
from app.models.gtfs import (
    Agency,
    Route,
    Stop,
    StopTime,
    Trip,
    Calendar,
    CalendarDate,
    Shape,
    ShapePoint,
)


def _iter_rows(path: Path, filename: str) -> Iterable[dict]:
    file_path = path / filename
    if path.is_file() and zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as zf:
            if filename not in zf.namelist():
                return
            with zf.open(filename) as f:
                text = io.TextIOWrapper(f, encoding="utf-8-sig")
                yield from csv.DictReader(text)
        return

    if file_path.exists():
        with file_path.open("r", encoding="utf-8-sig") as f:
            yield from csv.DictReader(f)


def _bulk_insert(session: Session, rows: list) -> None:
    if rows:
        session.add_all(rows)
        session.flush()


def load_gtfs(path: Path, truncate: bool = False) -> None:
    session = SessionLocal()
    try:
        if truncate:
            for table in [
                "stop_time",
                "trip",
                "route",
                "stop",
                "calendar",
                "calendar_date",
                "shape_point",
                "shape",
                "agency",
            ]:
                session.execute(text(f"TRUNCATE TABLE {table} RESTART IDENTITY CASCADE"))
            session.commit()

        agencies_by_id = {}
        for row in _iter_rows(path, "agency.txt"):
            agency_id = row.get("agency_id") or "default"
            if agency_id in agencies_by_id:
                continue
            agencies_by_id[agency_id] = Agency(
                agency_id=agency_id,
                name=row.get("agency_name") or "",
                url=row.get("agency_url"),
                timezone=row.get("agency_timezone"),
                lang=row.get("agency_lang"),
                phone=row.get("agency_phone"),
            )
        agencies = list(agencies_by_id.values())
        routes = [
            Route(
                route_id=row.get("route_id") or "",
                agency_id=row.get("agency_id"),
                short_name=row.get("route_short_name"),
                long_name=row.get("route_long_name"),
                route_type=int(row["route_type"]) if row.get("route_type") else None,
            )
            for row in _iter_rows(path, "routes.txt")
        ]
        stops = [
            Stop(
                stop_id=row.get("stop_id") or "",
                name=row.get("stop_name"),
                lat=float(row["stop_lat"]) if row.get("stop_lat") else None,
                lon=float(row["stop_lon"]) if row.get("stop_lon") else None,
            )
            for row in _iter_rows(path, "stops.txt")
        ]
        trips = [
            Trip(
                trip_id=row.get("trip_id") or "",
                route_id=row.get("route_id") or "",
                service_id=row.get("service_id"),
                shape_id=row.get("shape_id"),
                headsign=row.get("trip_headsign"),
                direction_id=int(row["direction_id"]) if row.get("direction_id") else None,
            )
            for row in _iter_rows(path, "trips.txt")
        ]
        stop_times = [
            StopTime(
                trip_id=row.get("trip_id") or "",
                stop_id=row.get("stop_id") or "",
                arrival_time=row.get("arrival_time"),
                departure_time=row.get("departure_time"),
                stop_sequence=int(row["stop_sequence"]) if row.get("stop_sequence") else None,
            )
            for row in _iter_rows(path, "stop_times.txt")
        ]
        calendars = [
            Calendar(
                service_id=row.get("service_id") or "",
                monday=int(row["monday"]) if row.get("monday") else None,
                tuesday=int(row["tuesday"]) if row.get("tuesday") else None,
                wednesday=int(row["wednesday"]) if row.get("wednesday") else None,
                thursday=int(row["thursday"]) if row.get("thursday") else None,
                friday=int(row["friday"]) if row.get("friday") else None,
                saturday=int(row["saturday"]) if row.get("saturday") else None,
                sunday=int(row["sunday"]) if row.get("sunday") else None,
                start_date=row.get("start_date"),
                end_date=row.get("end_date"),
            )
            for row in _iter_rows(path, "calendar.txt")
        ]
        calendar_dates = [
            CalendarDate(
                service_id=row.get("service_id") or "",
                date=row.get("date") or "",
                exception_type=int(row["exception_type"]) if row.get("exception_type") else 1,
            )
            for row in _iter_rows(path, "calendar_dates.txt")
        ]

        shape_rows = list(_iter_rows(path, "shapes.txt"))
        seen_shapes = set()
        shapes = []
        for row in shape_rows:
            shape_id = row.get("shape_id") or ""
            if shape_id and shape_id not in seen_shapes:
                shapes.append(Shape(shape_id=shape_id))
                seen_shapes.add(shape_id)

        shape_points = [
            ShapePoint(
                shape_id=row.get("shape_id") or "",
                sequence=int(row["shape_pt_sequence"]) if row.get("shape_pt_sequence") else 0,
                lat=float(row["shape_pt_lat"]) if row.get("shape_pt_lat") else 0.0,
                lon=float(row["shape_pt_lon"]) if row.get("shape_pt_lon") else 0.0,
                dist_traveled=float(row["shape_dist_traveled"]) if row.get("shape_dist_traveled") else None,
            )
            for row in shape_rows
        ]

        _bulk_insert(session, agencies)
        _bulk_insert(session, routes)
        _bulk_insert(session, stops)
        _bulk_insert(session, trips)
        _bulk_insert(session, stop_times)
        _bulk_insert(session, calendars)
        _bulk_insert(session, calendar_dates)
        _bulk_insert(session, shapes)
        _bulk_insert(session, shape_points)

        session.commit()
    finally:
        session.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--path", required=True, help="Path to GTFS directory or zip")
    parser.add_argument("--truncate", action="store_true", help="Truncate GTFS tables before load")
    args = parser.parse_args()

    load_gtfs(Path(args.path), truncate=args.truncate)
    print("GTFS loaded")


if __name__ == "__main__":
    main()

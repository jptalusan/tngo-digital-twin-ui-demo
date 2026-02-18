"""
GTFS loading service.

Accepts raw zip bytes plus a gtfs_id (MD5 hex) and gtfs_name, and bulk-inserts
all GTFS data into the gtfs_* tables. Designed to be called from the async
upload endpoint (runs in a thread pool) or from the CLI script.
"""
from __future__ import annotations

import csv
import io
import zipfile
from typing import Iterable

from geoalchemy2 import WKTElement
from sqlalchemy.orm import Session

from app.models.gtfs import (
    Agency,
    Calendar,
    CalendarDate,
    Route,
    Shape,
    ShapePoint,
    Stop,
    StopTime,
    Trip,
)


def _iter_rows(zf: zipfile.ZipFile, filename: str) -> Iterable[dict]:
    if filename not in zf.namelist():
        return
    with zf.open(filename) as f:
        text = io.TextIOWrapper(f, encoding="utf-8-sig")
        yield from csv.DictReader(text)


def load_gtfs_from_bytes(
    session: Session,
    zip_bytes: bytes,
    gtfs_id: str,
) -> dict[str, int]:
    """
    Parse zip_bytes and insert all rows tagged with gtfs_id.
    Returns a dict of table → row count.
    """
    counts: dict[str, int] = {}

    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        # --- agency ---
        agencies_by_id: dict[str, Agency] = {}
        for row in _iter_rows(zf, "agency.txt"):
            aid = row.get("agency_id") or "default"
            if aid in agencies_by_id:
                continue
            agencies_by_id[aid] = Agency(
                gtfs_id=gtfs_id,
                agency_id=aid,
                name=row.get("agency_name") or "",
                url=row.get("agency_url"),
                timezone=row.get("agency_timezone"),
                lang=row.get("agency_lang"),
                phone=row.get("agency_phone"),
            )
        session.add_all(list(agencies_by_id.values()))
        session.flush()
        counts["agency"] = len(agencies_by_id)

        # --- routes ---
        routes = [
            Route(
                gtfs_id=gtfs_id,
                route_id=row.get("route_id") or "",
                agency_id=row.get("agency_id"),
                short_name=row.get("route_short_name"),
                long_name=row.get("route_long_name"),
                route_type=int(row["route_type"]) if row.get("route_type") else None,
            )
            for row in _iter_rows(zf, "routes.txt")
        ]
        session.add_all(routes)
        session.flush()
        counts["route"] = len(routes)

        # --- stops ---
        def _stop_geom(row: dict) -> WKTElement | None:
            lat_s, lon_s = row.get("stop_lat"), row.get("stop_lon")
            if lat_s and lon_s:
                return WKTElement(f"POINT({float(lon_s)} {float(lat_s)})", srid=4326)
            return None

        stops = [
            Stop(
                gtfs_id=gtfs_id,
                stop_id=row.get("stop_id") or "",
                name=row.get("stop_name"),
                location=_stop_geom(row),
            )
            for row in _iter_rows(zf, "stops.txt")
        ]
        session.add_all(stops)
        session.flush()
        counts["stop"] = len(stops)

        # --- calendar ---
        calendars = [
            Calendar(
                gtfs_id=gtfs_id,
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
            for row in _iter_rows(zf, "calendar.txt")
        ]
        session.add_all(calendars)
        session.flush()
        counts["calendar"] = len(calendars)

        # --- calendar_dates ---
        calendar_dates = [
            CalendarDate(
                gtfs_id=gtfs_id,
                service_id=row.get("service_id") or "",
                date=row.get("date") or "",
                exception_type=int(row["exception_type"]) if row.get("exception_type") else 1,
            )
            for row in _iter_rows(zf, "calendar_dates.txt")
        ]
        session.add_all(calendar_dates)
        session.flush()
        counts["calendar_date"] = len(calendar_dates)

        # --- shapes ---
        shape_rows = list(_iter_rows(zf, "shapes.txt"))
        seen_shapes: set[str] = set()
        shapes: list[Shape] = []
        for row in shape_rows:
            sid = row.get("shape_id") or ""
            if sid and sid not in seen_shapes:
                shapes.append(Shape(gtfs_id=gtfs_id, shape_id=sid))
                seen_shapes.add(sid)
        session.add_all(shapes)
        session.flush()
        counts["shape"] = len(shapes)

        def _shape_geom(row: dict) -> WKTElement | None:
            lat_s = row.get("shape_pt_lat")
            lon_s = row.get("shape_pt_lon")
            if lat_s and lon_s:
                return WKTElement(f"POINT({float(lon_s)} {float(lat_s)})", srid=4326)
            return None

        shape_points = [
            ShapePoint(
                gtfs_id=gtfs_id,
                shape_id=row.get("shape_id") or "",
                sequence=int(row["shape_pt_sequence"]) if row.get("shape_pt_sequence") else 0,
                geom=_shape_geom(row),
                dist_traveled=float(row["shape_dist_traveled"]) if row.get("shape_dist_traveled") else None,
            )
            for row in shape_rows
        ]
        session.add_all(shape_points)
        session.flush()
        counts["shape_point"] = len(shape_points)

        # --- trips ---
        trips = [
            Trip(
                gtfs_id=gtfs_id,
                trip_id=row.get("trip_id") or "",
                route_id=row.get("route_id") or "",
                service_id=row.get("service_id"),
                shape_id=row.get("shape_id"),
                headsign=row.get("trip_headsign"),
                direction_id=int(row["direction_id"]) if row.get("direction_id") else None,
            )
            for row in _iter_rows(zf, "trips.txt")
        ]
        session.add_all(trips)
        session.flush()
        counts["trip"] = len(trips)

        # --- stop_times ---
        stop_times = [
            StopTime(
                gtfs_id=gtfs_id,
                trip_id=row.get("trip_id") or "",
                stop_id=row.get("stop_id") or "",
                arrival_time=row.get("arrival_time"),
                departure_time=row.get("departure_time"),
                stop_sequence=int(row["stop_sequence"]) if row.get("stop_sequence") else None,
            )
            for row in _iter_rows(zf, "stop_times.txt")
        ]
        session.add_all(stop_times)
        session.flush()
        counts["stop_time"] = len(stop_times)

    session.commit()
    return counts

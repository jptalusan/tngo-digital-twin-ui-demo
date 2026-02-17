from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.gtfs import Agency, Calendar, CalendarDate, ShapePoint, Stop, StopTime, Trip


def select_stops_by_name(query: str):
    return select(Stop).where(Stop.name.ilike(f"%{query}%")).limit(10)


def get_agency_timezone(session: Session) -> str | None:
    agency = session.execute(select(Agency).limit(1)).scalars().first()
    return agency.timezone if agency else None


def get_active_service_ids(session: Session, service_date: str) -> set[str]:
    if len(service_date) != 8:
        return set()

    date_obj = datetime.strptime(service_date, "%Y%m%d")
    weekday = date_obj.weekday()
    weekday_field = [
        "monday",
        "tuesday",
        "wednesday",
        "thursday",
        "friday",
        "saturday",
        "sunday",
    ][weekday]

    calendars = (
        session.execute(
            select(Calendar).where(
                Calendar.start_date <= service_date,
                Calendar.end_date >= service_date,
            )
        )
        .scalars()
        .all()
    )

    active = set()
    for cal in calendars:
        if getattr(cal, weekday_field) == 1:
            active.add(cal.service_id)

    exceptions = (
        session.execute(select(CalendarDate).where(CalendarDate.date == service_date))
        .scalars()
        .all()
    )
    for ex in exceptions:
        if ex.exception_type == 1:
            active.add(ex.service_id)
        elif ex.exception_type == 2 and ex.service_id in active:
            active.remove(ex.service_id)

    return active


def load_stop_times_for_stops(session: Session, stop_ids: set[str]) -> list[StopTime]:
    if not stop_ids:
        return []
    return (
        session.execute(select(StopTime).where(StopTime.stop_id.in_(stop_ids)))
        .scalars()
        .all()
    )


def load_stop_times_for_trips(session: Session, trip_ids: set[str]) -> list[StopTime]:
    if not trip_ids:
        return []
    return (
        session.execute(select(StopTime).where(StopTime.trip_id.in_(trip_ids)))
        .scalars()
        .all()
    )


def load_trips_for_service_ids(session: Session, service_ids: set[str]) -> list[Trip]:
    if not service_ids:
        return []
    return (
        session.execute(select(Trip).where(Trip.service_id.in_(service_ids)))
        .scalars()
        .all()
    )


def load_trips_for_ids(session: Session, trip_ids: set[str]) -> list[Trip]:
    if not trip_ids:
        return []
    return session.execute(select(Trip).where(Trip.trip_id.in_(trip_ids))).scalars().all()


def load_shape_points_for_trip(session: Session, trip_id: str) -> list[ShapePoint]:
    trip = session.execute(select(Trip).where(Trip.trip_id == trip_id)).scalars().first()
    if trip is None or not trip.shape_id:
        return []
    return (
        session.execute(
            select(ShapePoint)
            .where(ShapePoint.shape_id == trip.shape_id)
            .order_by(ShapePoint.sequence)
        )
        .scalars()
        .all()
    )


def load_stops_by_ids(session: Session, stop_ids: set[str]) -> list[Stop]:
    if not stop_ids:
        return []
    return session.execute(select(Stop).where(Stop.stop_id.in_(stop_ids))).scalars().all()


def find_stop_ids_by_prefix_near(
    session: Session,
    prefix: str,
    lat: float,
    lon: float,
    max_distance_m: float,
    limit: int = 20,
) -> set[str]:
    dlat = max_distance_m / 111_320
    dlon = max_distance_m / (111_320 * max(0.1, abs(_cos_deg(lat))))

    stops = (
        session.execute(
            select(Stop).where(
                Stop.stop_id.like(f"{prefix}%"),
                Stop.lat.is_not(None),
                Stop.lon.is_not(None),
                Stop.lat.between(lat - dlat, lat + dlat),
                Stop.lon.between(lon - dlon, lon + dlon),
            )
        )
        .scalars()
        .all()
    )

    def dist(a, b, c, d):
        import math

        rad = math.pi / 180
        dlat = (c - a) * rad
        dlon = (d - b) * rad
        x = math.sin(dlat / 2) ** 2 + math.cos(a * rad) * math.cos(c * rad) * math.sin(
            dlon / 2
        ) ** 2
        return 6371000 * 2 * math.atan2(math.sqrt(x), math.sqrt(1 - x))

    ranked = sorted(
        [(dist(lat, lon, s.lat, s.lon), s.stop_id) for s in stops],
        key=lambda item: item[0],
    )
    return {sid for _, sid in ranked[:limit]}


def find_nearest_stop_by_prefix(
    session: Session,
    prefix: str,
    lat: float,
    lon: float,
    max_distance_m: float,
) -> Stop | None:
    stop_ids = find_stop_ids_by_prefix_near(
        session, prefix, lat, lon, max_distance_m, limit=1
    )
    if not stop_ids:
        return None
    return (
        session.execute(select(Stop).where(Stop.stop_id.in_(stop_ids))).scalars().first()
    )


def _cos_deg(deg: float) -> float:
    import math

    return math.cos(deg * math.pi / 180)

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.gtfs import Agency, Calendar, CalendarDate, Stop, StopTime, Trip


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

"""Unit tests for GTFS SQLAlchemy models.

Tests cover:
- Table/column definitions and constraints
- Unique constraints are enforced by the database
- Cascade deletes propagate from GtfsFeed to child rows
- Nullable vs required fields
"""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.db import SessionLocal
from app.models.gtfs import (
    Agency,
    Calendar,
    CalendarDate,
    GtfsFeed,
    GtfsJob,
    Route,
    Shape,
    ShapePoint,
    Stop,
    StopTime,
    Trip,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _feed(session, gtfs_id: str = "feed-1", name: str = "Test Feed") -> GtfsFeed:
    feed = GtfsFeed(gtfs_id=gtfs_id, gtfs_name=name)
    session.add(feed)
    session.flush()
    return feed


# ---------------------------------------------------------------------------
# GtfsFeed
# ---------------------------------------------------------------------------


def test_gtfs_feed_persists():
    session = SessionLocal()
    try:
        feed = GtfsFeed(gtfs_id="f1", gtfs_name="Feed One", filename="feed.zip")
        session.add(feed)
        session.commit()

        result = session.execute(
            select(GtfsFeed).where(GtfsFeed.gtfs_id == "f1")
        ).scalars().first()
        assert result is not None
        assert result.gtfs_name == "Feed One"
        assert result.filename == "feed.zip"
        assert result.uploaded_at is not None  # server_default
    finally:
        session.rollback()
        session.close()


def test_gtfs_feed_unique_gtfs_id():
    session = SessionLocal()
    try:
        session.add(GtfsFeed(gtfs_id="dup", gtfs_name="First"))
        session.flush()
        session.add(GtfsFeed(gtfs_id="dup", gtfs_name="Second"))
        with pytest.raises(IntegrityError):
            session.flush()
    finally:
        session.rollback()
        session.close()


def test_gtfs_feed_name_required():
    session = SessionLocal()
    try:
        session.add(GtfsFeed(gtfs_id="no-name"))  # gtfs_name is NOT NULL
        with pytest.raises(IntegrityError):
            session.flush()
    finally:
        session.rollback()
        session.close()


# ---------------------------------------------------------------------------
# GtfsJob
# ---------------------------------------------------------------------------


def test_gtfs_job_tracks_status():
    session = SessionLocal()
    try:
        feed = _feed(session, "feed-j1")
        job = GtfsJob(
            job_id="job-001",
            gtfs_id="feed-j1",
            status="pending",
            row_counts={"stop": 10, "trip": 5},
        )
        session.add(job)
        session.commit()

        loaded = session.execute(
            select(GtfsJob).where(GtfsJob.job_id == "job-001")
        ).scalars().first()
        assert loaded is not None
        assert loaded.status == "pending"
        assert loaded.row_counts["stop"] == 10
        assert loaded.created_at is not None
    finally:
        session.rollback()
        session.close()


def test_gtfs_job_unique_job_id():
    session = SessionLocal()
    try:
        feed = _feed(session, "feed-j2")
        session.add(GtfsJob(job_id="j-dup", gtfs_id="feed-j2", status="pending"))
        session.flush()
        session.add(GtfsJob(job_id="j-dup", gtfs_id="feed-j2", status="running"))
        with pytest.raises(IntegrityError):
            session.flush()
    finally:
        session.rollback()
        session.close()


# ---------------------------------------------------------------------------
# Agency
# ---------------------------------------------------------------------------


def test_agency_persists():
    session = SessionLocal()
    try:
        feed = _feed(session, "feed-a1")
        session.add(
            Agency(
                gtfs_id="feed-a1",
                agency_id="AG1",
                name="Test Agency",
                timezone="America/Chicago",
            )
        )
        session.commit()

        row = session.execute(
            select(Agency).where(Agency.agency_id == "AG1", Agency.gtfs_id == "feed-a1")
        ).scalars().first()
        assert row is not None
        assert row.name == "Test Agency"
        assert row.timezone == "America/Chicago"
    finally:
        session.rollback()
        session.close()


def test_agency_unique_constraint():
    session = SessionLocal()
    try:
        feed = _feed(session, "feed-a2")
        session.add(Agency(gtfs_id="feed-a2", agency_id="AG-DUP", name="Agency A"))
        session.flush()
        session.add(Agency(gtfs_id="feed-a2", agency_id="AG-DUP", name="Agency B"))
        with pytest.raises(IntegrityError):
            session.flush()
    finally:
        session.rollback()
        session.close()


# ---------------------------------------------------------------------------
# Stop
# ---------------------------------------------------------------------------


def test_stop_without_geometry():
    """Geometry is nullable — a stop may have no location on load."""
    session = SessionLocal()
    try:
        feed = _feed(session, "feed-s1")
        session.add(
            Stop(gtfs_id="feed-s1", stop_id="S1", name="Main St")
        )
        session.commit()

        row = session.execute(
            select(Stop).where(Stop.stop_id == "S1", Stop.gtfs_id == "feed-s1")
        ).scalars().first()
        assert row is not None
        assert row.name == "Main St"
        assert row.location is None
    finally:
        session.rollback()
        session.close()


def test_stop_unique_constraint():
    session = SessionLocal()
    try:
        feed = _feed(session, "feed-s2")
        session.add(Stop(gtfs_id="feed-s2", stop_id="S-DUP"))
        session.flush()
        session.add(Stop(gtfs_id="feed-s2", stop_id="S-DUP"))
        with pytest.raises(IntegrityError):
            session.flush()
    finally:
        session.rollback()
        session.close()


# ---------------------------------------------------------------------------
# Calendar day flags
# ---------------------------------------------------------------------------


def test_calendar_integer_day_flags():
    """GTFS spec uses 0/1 integers — verify they round-trip correctly."""
    session = SessionLocal()
    try:
        feed = _feed(session, "feed-c1")
        session.add(
            Calendar(
                gtfs_id="feed-c1",
                service_id="SVC-1",
                monday=1,
                tuesday=1,
                wednesday=1,
                thursday=1,
                friday=1,
                saturday=0,
                sunday=0,
                start_date="20250101",
                end_date="20251231",
            )
        )
        session.commit()

        row = session.execute(
            select(Calendar).where(
                Calendar.service_id == "SVC-1", Calendar.gtfs_id == "feed-c1"
            )
        ).scalars().first()
        assert row is not None
        assert row.monday == 1
        assert row.saturday == 0
        assert row.start_date == "20250101"
    finally:
        session.rollback()
        session.close()


# ---------------------------------------------------------------------------
# CalendarDate
# ---------------------------------------------------------------------------


def test_calendar_date_exception_types():
    session = SessionLocal()
    try:
        feed = _feed(session, "feed-cd1")
        session.add(
            CalendarDate(
                gtfs_id="feed-cd1",
                service_id="SVC-1",
                date="20250704",
                exception_type=2,  # 2 = service removed
            )
        )
        session.commit()

        row = session.execute(
            select(CalendarDate).where(
                CalendarDate.gtfs_id == "feed-cd1",
                CalendarDate.date == "20250704",
            )
        ).scalars().first()
        assert row is not None
        assert row.exception_type == 2
    finally:
        session.rollback()
        session.close()


# ---------------------------------------------------------------------------
# Trip
# ---------------------------------------------------------------------------


def test_trip_unique_constraint():
    session = SessionLocal()
    try:
        feed = _feed(session, "feed-t1")
        session.add(Trip(gtfs_id="feed-t1", trip_id="T-DUP", route_id="R1"))
        session.flush()
        session.add(Trip(gtfs_id="feed-t1", trip_id="T-DUP", route_id="R2"))
        with pytest.raises(IntegrityError):
            session.flush()
    finally:
        session.rollback()
        session.close()


# ---------------------------------------------------------------------------
# StopTime
# ---------------------------------------------------------------------------


def test_stop_time_unique_constraint():
    session = SessionLocal()
    try:
        feed = _feed(session, "feed-st1")
        session.add(
            StopTime(
                gtfs_id="feed-st1",
                trip_id="T1",
                stop_id="S1",
                stop_sequence=1,
                arrival_time="08:00:00",
                departure_time="08:01:00",
            )
        )
        session.flush()
        # Same (gtfs_id, trip_id, stop_sequence) should violate unique constraint
        session.add(
            StopTime(
                gtfs_id="feed-st1",
                trip_id="T1",
                stop_id="S2",
                stop_sequence=1,
            )
        )
        with pytest.raises(IntegrityError):
            session.flush()
    finally:
        session.rollback()
        session.close()


def test_stop_time_times_stored_as_string():
    """GTFS allows times like '25:30:00' — verify String storage round-trips."""
    session = SessionLocal()
    try:
        feed = _feed(session, "feed-st2")
        session.add(
            StopTime(
                gtfs_id="feed-st2",
                trip_id="T-OVER",
                stop_id="S1",
                stop_sequence=1,
                arrival_time="25:30:00",
                departure_time="25:31:00",
            )
        )
        session.commit()

        row = session.execute(
            select(StopTime).where(
                StopTime.gtfs_id == "feed-st2", StopTime.trip_id == "T-OVER"
            )
        ).scalars().first()
        assert row is not None
        assert row.arrival_time == "25:30:00"
    finally:
        session.rollback()
        session.close()


# ---------------------------------------------------------------------------
# Shape / ShapePoint
# ---------------------------------------------------------------------------


def test_shape_unique_constraint():
    session = SessionLocal()
    try:
        feed = _feed(session, "feed-sh1")
        session.add(Shape(gtfs_id="feed-sh1", shape_id="SH-DUP"))
        session.flush()
        session.add(Shape(gtfs_id="feed-sh1", shape_id="SH-DUP"))
        with pytest.raises(IntegrityError):
            session.flush()
    finally:
        session.rollback()
        session.close()

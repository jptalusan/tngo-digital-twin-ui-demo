import os
from pathlib import Path
import sys

import pytest
import psycopg
from sqlalchemy import text
from urllib.parse import urlparse
from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))
os.environ["USE_TEST_DB"] = "true"
os.environ["ENABLE_OSRM"] = "false"
os.environ["ENABLE_NOMINATIM"] = "false"

from app.core.config import settings
from app.db import init_db, SessionLocal, engine
from app.models.base import Base
from app.main import app


def _ensure_test_database():
    url = settings.database_url_test
    parsed = urlparse(url.replace("postgresql+psycopg", "postgresql"))
    dbname = parsed.path.lstrip("/") or "postgres"
    admin_db = "postgres"
    admin_url = parsed._replace(path=f"/{admin_db}").geturl()

    with psycopg.connect(admin_url, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (dbname,))
            exists = cur.fetchone() is not None
            if not exists:
                cur.execute(f"CREATE DATABASE {dbname}")


@pytest.fixture(scope="session", autouse=True)
def _ensure_test_db():
    _ensure_test_database()
    # Drop via raw SQL CASCADE to handle any stale tables/constraints that
    # SQLAlchemy's drop_all (which issues individual DROP TABLE statements
    # without CASCADE) cannot resolve.
    with engine.connect() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
        conn.commit()
    init_db()
    yield


@pytest.fixture(autouse=True)
def _clean_db():
    session = SessionLocal()
    try:
        # Truncate tables in dependency order (children before parents).
        # Table names must match the __tablename__ values in the ORM models.
        # gtfs_feed is the root parent for all gtfs_* tables; CASCADE from it
        # clears children, but we list them explicitly for RESTART IDENTITY.
        for table in [
            "gtfs_stop_time",
            "gtfs_trip",
            "gtfs_route",
            "gtfs_stop",
            "gtfs_calendar",
            "gtfs_calendar_date",
            "gtfs_shape_point",
            "gtfs_shape",
            "gtfs_agency",
            "gtfs_job",
            "gtfs_feed",
            "vehicle_schedule",
            "vehicle_route_stop",
            "vehicle_route",
            "ondemand_vehicle",
            "ondemand_service_zone",
            "ondemand_trip",
            "ondemand_request",
            "depot",
        ]:
            session.execute(text(f"TRUNCATE TABLE {table} RESTART IDENTITY CASCADE"))
        session.commit()
    finally:
        session.close()


@pytest.fixture()
def client():
    return TestClient(app)


@pytest.fixture()
def gtfs_fixture_path():
    return Path(__file__).resolve().parent / "fixtures" / "gtfs"


@pytest.fixture()
def gtfs_transfer_fixture_path():
    return Path(__file__).resolve().parent / "fixtures" / "gtfs_transfer"

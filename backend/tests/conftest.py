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

from app.core.config import settings
from app.db import init_db, SessionLocal
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
    init_db()
    yield


@pytest.fixture(autouse=True)
def _clean_db():
    session = SessionLocal()
    try:
        # Truncate tables in dependency order
        for table in [
            "stop_time",
            "trip",
            "route",
            "stop",
            "calendar",
            "calendar_date",
            "shape_point",
            "shape",
            "vehicle_schedule",
            "vehicle",
            "depot",
            "vehicle_route_stop",
            "vehicle_route",
            "ondemand_trip",
            "ondemand_request",
            "agency",
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

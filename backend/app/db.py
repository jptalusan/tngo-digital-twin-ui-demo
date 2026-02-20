from __future__ import annotations

from collections.abc import Generator

import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session

from app.core.config import settings
from app.models.base import Base

database_url = settings.database_url
if os.getenv("USE_TEST_DB", "false").lower() == "true" or "PYTEST_CURRENT_TEST" in os.environ:
    database_url = settings.database_url_test

engine = create_engine(database_url, echo=False, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def init_db(drop: bool = False) -> None:
    if settings.database_url.startswith("postgresql"):
        with engine.connect() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS unaccent"))
            conn.commit()

    if drop:
        Base.metadata.drop_all(engine)

    Base.metadata.create_all(engine)


def get_session() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()

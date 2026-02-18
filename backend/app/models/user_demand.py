from __future__ import annotations

from typing import Optional

from geoalchemy2 import Geometry
from sqlalchemy import BigInteger, Boolean, Integer, String, Float, Time, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class UserDemand(Base):
    """One row per user per demand scenario (CSV file)."""

    __tablename__ = "user_demand"
    __table_args__ = (
        UniqueConstraint("demand_name", "user_id", name="uq_user_demand_name_user"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    # Scenario identifier — derived from CSV filename (sans extension)
    demand_name: Mapped[str] = mapped_column(String, nullable=False, index=True)

    # User / building references
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    building_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    # Survey / forecast count
    count_fyp: Mapped[int] = mapped_column(Integer, nullable=False)

    # Home location — POINT(lon lat) SRID 4326
    home_location: Mapped[object] = mapped_column(
        Geometry("POINT", srid=4326), nullable=False
    )

    # Work / office location — POINT(lon lat) SRID 4326
    work_location: Mapped[object] = mapped_column(
        Geometry("POINT", srid=4326), nullable=False
    )

    # Optional commute metrics
    travel_time_s: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    distance_m: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Commute behaviour flag
    transit_taker: Mapped[bool] = mapped_column(Boolean, nullable=False)

    # Shift schedule — stored as TIME (HH:MM:SS)
    shift_start: Mapped[str] = mapped_column(Time, nullable=False)
    shift_end: Mapped[str] = mapped_column(Time, nullable=False)

    # Shift identifier (e.g. 1, 2, 3)
    shift: Mapped[int] = mapped_column(Integer, nullable=False)

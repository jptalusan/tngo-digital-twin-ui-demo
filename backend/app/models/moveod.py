from __future__ import annotations

from datetime import datetime
from typing import Optional

from geoalchemy2 import Geometry, WKBElement
from sqlalchemy import BigInteger, ForeignKey, String, Float, Index, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class StateFips(Base):
    __tablename__ = "moveod_state_fips"

    state_fips: Mapped[str] = mapped_column(String(2), primary_key=True)
    state_name: Mapped[str] = mapped_column(String, nullable=False)
    state_abbr: Mapped[Optional[str]] = mapped_column(String(2), nullable=True)

    counties: Mapped[list["CountyGeo"]] = relationship(back_populates="state")


class CountyGeo(Base):
    __tablename__ = "moveod_county_geo"
    __table_args__ = (Index("idx_moveod_county_state_name", "state_fips", "name"),)

    geoid: Mapped[str] = mapped_column(String(5), primary_key=True)
    state_fips: Mapped[str] = mapped_column(
        String(2), ForeignKey("moveod_state_fips.state_fips"), index=True
    )
    county_fips: Mapped[str] = mapped_column(String(3), nullable=False, index=True)
    county_ns: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    aff_geoid: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    lsad: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    aland: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    awater: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    geometry: Mapped[Optional[WKBElement]] = mapped_column(
        Geometry("MULTIPOLYGON", srid=4326, spatial_index=True), nullable=True
    )

    state: Mapped[Optional[StateFips]] = relationship(back_populates="counties")


class StateGeo(Base):
    __tablename__ = "moveod_state_geo"

    state_fips: Mapped[str] = mapped_column(
        String(2), ForeignKey("moveod_state_fips.state_fips"), primary_key=True
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    density: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    geometry: Mapped[Optional[WKBElement]] = mapped_column(
        Geometry("MULTIPOLYGON", srid=4326, spatial_index=True), nullable=True
    )

    state: Mapped[Optional[StateFips]] = relationship()


class CountyFips(Base):
    __tablename__ = "moveod_county_fips"

    geoid: Mapped[str] = mapped_column(String(5), primary_key=True)
    state_fips: Mapped[str] = mapped_column(
        String(2), ForeignKey("moveod_state_fips.state_fips"), index=True
    )
    county_fips: Mapped[str] = mapped_column(String(3), nullable=False, index=True)
    county_name: Mapped[str] = mapped_column(String, nullable=False)
    county_full: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    state_id: Mapped[Optional[str]] = mapped_column(String(2), nullable=True)
    state_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    lat: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    lon: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    population: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)

    state: Mapped[Optional[StateFips]] = relationship()


class SyntheticDemand(Base):
    __tablename__ = "moveod_synthetic_demand"
    __table_args__ = (
        Index("idx_moveod_synth_origin_state_county", "origin_state_fips", "origin_county_fips"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    origin_geoid: Mapped[str] = mapped_column(String(12), index=True)
    origin_state_fips: Mapped[str] = mapped_column(String(2), index=True)
    origin_county_fips: Mapped[str] = mapped_column(String(3), index=True)
    origin_census_tract_fips: Mapped[str] = mapped_column(String(6))
    origin_block_fips: Mapped[str] = mapped_column(String(1))
    origin_location: Mapped[Optional[WKBElement]] = mapped_column(
        Geometry("POINT", srid=4326, spatial_index=True), nullable=True
    )
    origin_node: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    destination_geoid: Mapped[str] = mapped_column(String(12), index=True)
    destination_state_fips: Mapped[str] = mapped_column(String(2), index=True)
    destination_county_fips: Mapped[str] = mapped_column(String(3), index=True)
    destination_census_tract_fips: Mapped[str] = mapped_column(String(6))
    destination_block_fips: Mapped[str] = mapped_column(String(1))
    destination_location: Mapped[Optional[WKBElement]] = mapped_column(
        Geometry("POINT", srid=4326, spatial_index=True), nullable=True
    )
    destination_node: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    departure_time_utc: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    departure_time_bin: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    arrival_time_utc: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    travel_time_min: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    travel_time_bin: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    travel_distance_mi: Mapped[Optional[float]] = mapped_column(Float, nullable=True)


class AnalysisHeatmap(Base):
    __tablename__ = "moveod_analysis_heatmap"
    __table_args__ = (
        Index("idx_moveod_analysis_heatmap_state_county_kind", "state_fips", "county_fips", "kind"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    state_fips: Mapped[str] = mapped_column(String(2), index=True)
    county_fips: Mapped[str] = mapped_column(String(3), index=True)
    kind: Mapped[str] = mapped_column(String(12))
    lat: Mapped[float] = mapped_column(Float)
    lon: Mapped[float] = mapped_column(Float)
    weight: Mapped[float] = mapped_column(Float, default=1.0)


class AnalysisDepartureBin(Base):
    __tablename__ = "moveod_analysis_departure_bins"
    __table_args__ = (
        Index("idx_moveod_analysis_departure_bins_state_county", "state_fips", "county_fips"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    state_fips: Mapped[str] = mapped_column(String(2), index=True)
    county_fips: Mapped[str] = mapped_column(String(3), index=True)
    kind: Mapped[str] = mapped_column(String(12), index=True)
    bin_label: Mapped[str] = mapped_column(String, index=True)
    count: Mapped[int] = mapped_column(BigInteger)


class AnalysisTravelTimeBin(Base):
    __tablename__ = "moveod_analysis_travel_time_bins"
    __table_args__ = (
        Index("idx_moveod_analysis_travel_time_bins_state_county", "state_fips", "county_fips"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    state_fips: Mapped[str] = mapped_column(String(2), index=True)
    county_fips: Mapped[str] = mapped_column(String(3), index=True)
    bin_label: Mapped[str] = mapped_column(String, index=True)
    count: Mapped[int] = mapped_column(BigInteger)
    avg_distance_mi: Mapped[Optional[float]] = mapped_column(Float, nullable=True)


class AnalysisTopOrigin(Base):
    __tablename__ = "moveod_analysis_top_origins"
    __table_args__ = (
        Index("idx_moveod_analysis_top_origins_state_county", "state_fips", "county_fips"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    state_fips: Mapped[str] = mapped_column(String(2), index=True)
    county_fips: Mapped[str] = mapped_column(String(3), index=True)
    origin_geoid: Mapped[str] = mapped_column(String(12), index=True)
    trip_count: Mapped[int] = mapped_column(BigInteger)




class AnalysisFlowBalance(Base):
    __tablename__ = "moveod_analysis_flow_balance"
    __table_args__ = (
        Index("idx_moveod_analysis_flow_balance_state_county", "state_fips", "county_fips"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    state_fips: Mapped[str] = mapped_column(String(2), index=True)
    county_fips: Mapped[str] = mapped_column(String(3), index=True)
    geoid: Mapped[str] = mapped_column(String(12), index=True)
    origin_count: Mapped[int] = mapped_column(BigInteger)
    destination_count: Mapped[int] = mapped_column(BigInteger)
    net_flow: Mapped[int] = mapped_column(BigInteger)


class AnalysisJob(Base):
    __tablename__ = "moveod_analysis_jobs"
    __table_args__ = (
        Index("idx_moveod_analysis_jobs_state_county", "state_fips", "county_fips"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[str] = mapped_column(String(36), unique=True, index=True)
    state_fips: Mapped[str] = mapped_column(String(2), index=True)
    county_fips: Mapped[str] = mapped_column(String(3), index=True)
    status: Mapped[str] = mapped_column(String, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    message: Mapped[Optional[str]] = mapped_column(String, nullable=True)

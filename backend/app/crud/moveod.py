from __future__ import annotations

import csv
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Optional

from geoalchemy2 import WKTElement
from sqlalchemy import case, func, literal, select, text
from sqlalchemy.orm import Session

from app.models.moveod import (
    CountyGeo,
    StateFips,
    StateGeo,
    SyntheticDemand,
    AnalysisHeatmap,
    AnalysisJob,
)

_UNACCENT_AVAILABLE: Optional[bool] = None


def _normalized(expr, use_unaccent: bool):
    lowered = func.lower(expr)
    return func.unaccent(lowered) if use_unaccent else lowered


def _normalized_value_expr(value: str, use_unaccent: bool):
    lowered = func.lower(literal(value.strip()))
    return func.unaccent(lowered) if use_unaccent else lowered


def is_unaccent_available(session: Session) -> bool:
    global _UNACCENT_AVAILABLE
    if _UNACCENT_AVAILABLE is not None:
        return _UNACCENT_AVAILABLE
    exists = session.execute(
        text("SELECT 1 FROM pg_extension WHERE extname = 'unaccent'")
    ).scalar_one_or_none()
    _UNACCENT_AVAILABLE = bool(exists)
    return _UNACCENT_AVAILABLE


def _county_geometry(row: Any) -> Optional[dict[str, Any]]:
    if row is None or row.geojson is None:
        return None
    return json.loads(row.geojson)


def search_states(session: Session, q: str, limit: int, use_unaccent: bool) -> list[StateFips]:
    q_clean = q.strip()
    q_norm = _normalized_value_expr(q_clean, use_unaccent)
    name_norm = _normalized(StateFips.state_name, use_unaccent)

    starts_name = name_norm.like(func.concat(q_norm, "%"))
    contains_name = name_norm.like(func.concat("%", q_norm, "%"))
    starts_abbr = func.lower(StateFips.state_abbr).like(
        func.concat(func.lower(literal(q_clean)), "%")
    )
    starts_fips = StateFips.state_fips.like(f"{q_clean}%")

    order_rank = case(
        (starts_name, 1),
        (contains_name, 2),
        (starts_abbr, 3),
        (starts_fips, 4),
        else_=5,
    )

    return (
        session.execute(
            select(StateFips)
            .where(
                contains_name | starts_abbr | starts_fips
            )
            .order_by(order_rank, StateFips.state_name)
            .limit(limit)
        )
        .scalars()
        .all()
    )


def resolve_state_fips(
    session: Session, state_name: str, use_unaccent: bool
) -> Optional[str]:
    name_norm = _normalized(StateFips.state_name, use_unaccent)
    target_norm = _normalized_value_expr(state_name, use_unaccent)
    return session.execute(
        select(StateFips.state_fips).where(name_norm == target_norm)
    ).scalar_one_or_none()


def search_counties(
    session: Session,
    q: str,
    limit: int,
    state_fips: Optional[str] = None,
    use_unaccent: bool = True,
) -> list[CountyGeo]:
    q_norm = _normalized_value_expr(q, use_unaccent)
    name_norm = _normalized(CountyGeo.name, use_unaccent)
    starts_name = name_norm.like(func.concat(q_norm, "%"))
    contains_name = name_norm.like(func.concat("%", q_norm, "%"))

    order_rank = case(
        (starts_name, 1),
        (contains_name, 2),
        else_=3,
    )

    query = select(CountyGeo).where(contains_name)
    if state_fips:
        query = query.where(CountyGeo.state_fips == state_fips)

    return (
        session.execute(
            query.order_by(order_rank, CountyGeo.name).limit(limit)
        )
        .scalars()
        .all()
    )


def list_counties(
    session: Session, state_fips: str, include_geometry: bool
) -> list[dict[str, Any]]:
    if include_geometry:
        rows = session.execute(
            select(
                CountyGeo.geoid,
                CountyGeo.name,
                CountyGeo.state_fips,
                CountyGeo.county_fips,
                func.ST_AsGeoJSON(CountyGeo.geometry).label("geojson"),
            )
            .where(CountyGeo.state_fips == state_fips)
            .order_by(CountyGeo.name)
        ).all()
        return [
            {
                "geoid": row.geoid,
                "name": row.name,
                "state_fips": row.state_fips,
                "county_fips": row.county_fips,
                "geometry": _county_geometry(row),
            }
            for row in rows
        ]

    rows = session.execute(
        select(
            CountyGeo.geoid,
            CountyGeo.name,
            CountyGeo.state_fips,
            CountyGeo.county_fips,
        )
        .where(CountyGeo.state_fips == state_fips)
        .order_by(CountyGeo.name)
    ).all()
    return [
        {
            "geoid": row.geoid,
            "name": row.name,
            "state_fips": row.state_fips,
            "county_fips": row.county_fips,
        }
        for row in rows
    ]


def get_county_feature(
    session: Session,
    geoid: Optional[str],
    state_fips: Optional[str],
    name: Optional[str],
    use_unaccent: bool,
) -> Optional[dict[str, Any]]:
    if geoid:
        row = session.execute(
            select(
                CountyGeo.geoid,
                CountyGeo.name,
                CountyGeo.state_fips,
                CountyGeo.county_fips,
                func.ST_AsGeoJSON(CountyGeo.geometry).label("geojson"),
            ).where(CountyGeo.geoid == geoid)
        ).one_or_none()
    else:
        name_norm = _normalized(CountyGeo.name, use_unaccent)
        target_norm = _normalized_value_expr(name or "", use_unaccent)
        row = session.execute(
            select(
                CountyGeo.geoid,
                CountyGeo.name,
                CountyGeo.state_fips,
                CountyGeo.county_fips,
                func.ST_AsGeoJSON(CountyGeo.geometry).label("geojson"),
            )
            .where(
                CountyGeo.state_fips == state_fips,
                name_norm == target_norm,
            )
        ).one_or_none()

    if row is None or row.geojson is None:
        return None

    geometry = json.loads(row.geojson)
    return {
        "type": "Feature",
        "geometry": geometry,
        "properties": {
            "geoid": row.geoid,
            "name": row.name,
            "state_fips": row.state_fips,
            "county_fips": row.county_fips,
        },
    }


def list_state_features(session: Session) -> list[dict[str, Any]]:
    rows = session.execute(
        select(
            StateGeo.state_fips,
            StateGeo.name,
            func.ST_AsGeoJSON(StateGeo.geometry).label("geojson"),
        ).order_by(StateGeo.name)
    ).all()
    features = []
    for row in rows:
        if row.geojson is None:
            continue
        features.append(
            {
                "type": "Feature",
                "geometry": json.loads(row.geojson),
                "properties": {
                    "state_fips": row.state_fips,
                    "name": row.name,
                },
            }
        )
    return features


def list_synthetic_demand(
    session: Session,
    state_fips: str,
    county_fips: str,
    limit: int,
) -> list[dict[str, Any]]:
    rows = session.execute(
        select(
            SyntheticDemand.origin_geoid,
            SyntheticDemand.destination_geoid,
            SyntheticDemand.origin_state_fips,
            SyntheticDemand.origin_county_fips,
            SyntheticDemand.destination_state_fips,
            SyntheticDemand.destination_county_fips,
            SyntheticDemand.departure_time_utc,
            SyntheticDemand.arrival_time_utc,
            SyntheticDemand.travel_time_min,
            SyntheticDemand.travel_time_bin,
            SyntheticDemand.travel_distance_mi,
            func.ST_AsGeoJSON(SyntheticDemand.origin_location).label("origin_geojson"),
            func.ST_AsGeoJSON(SyntheticDemand.destination_location).label("destination_geojson"),
        )
        .where(
            SyntheticDemand.origin_state_fips == state_fips,
            SyntheticDemand.origin_county_fips == county_fips,
        )
        .order_by(SyntheticDemand.departure_time_utc.asc().nullslast())
        .limit(limit)
    ).all()
    items = []
    for row in rows:
        items.append(
            {
                "origin_geoid": row.origin_geoid,
                "destination_geoid": row.destination_geoid,
                "origin_state_fips": row.origin_state_fips,
                "origin_county_fips": row.origin_county_fips,
                "destination_state_fips": row.destination_state_fips,
                "destination_county_fips": row.destination_county_fips,
                "origin_location": json.loads(row.origin_geojson)
                if row.origin_geojson
                else None,
                "destination_location": json.loads(row.destination_geojson)
                if row.destination_geojson
                else None,
                "departure_time_utc": row.departure_time_utc.isoformat()
                if row.departure_time_utc
                else None,
                "arrival_time_utc": row.arrival_time_utc.isoformat()
                if row.arrival_time_utc
                else None,
                "travel_time_min": row.travel_time_min,
                "travel_time_bin": row.travel_time_bin,
                "travel_distance_mi": row.travel_distance_mi,
            }
        )
    return items


def has_analysis(session: Session, state_fips: str, county_fips: str) -> bool:
    exists = session.execute(
        select(AnalysisHeatmap.id)
        .where(
            AnalysisHeatmap.state_fips == state_fips,
            AnalysisHeatmap.county_fips == county_fips,
        )
        .limit(1)
    ).first()
    return bool(exists)


def get_active_job(
    session: Session,
    state_fips: str,
    county_fips: str,
    job_type: str = "analyze",
) -> AnalysisJob | None:
    return (
        session.execute(
            select(AnalysisJob)
            .where(
                AnalysisJob.state_fips == state_fips,
                AnalysisJob.county_fips == county_fips,
                AnalysisJob.job_type == job_type,
                AnalysisJob.status.in_(["queued", "running"]),
            )
            .order_by(AnalysisJob.created_at.desc())
            .limit(1)
        )
        .scalars()
        .first()
    )


def create_job(
    session: Session,
    job_id: str,
    state_fips: str,
    county_fips: str,
    job_type: str = "analyze",
) -> AnalysisJob:
    job = AnalysisJob(
        job_id=job_id,
        state_fips=state_fips,
        county_fips=county_fips,
        job_type=job_type,
        status="queued",
    )
    session.add(job)
    session.commit()
    session.refresh(job)
    return job


def get_job(session: Session, job_id: str) -> AnalysisJob | None:
    return (
        session.execute(select(AnalysisJob).where(AnalysisJob.job_id == job_id))
        .scalars()
        .first()
    )


def update_job_status(
    session: Session, job_id: str, status: str, message: str | None = None
) -> None:
    session.execute(
        text(
            "UPDATE moveod_analysis_jobs SET status = :status, message = :message, updated_at = NOW() "
            "WHERE job_id = :job_id"
        ),
        {"status": status, "message": message, "job_id": job_id},
    )
    session.commit()




def list_available_demand_areas(session: Session) -> dict[str, list[str]]:
    rows = session.execute(
        select(
            SyntheticDemand.origin_state_fips,
            SyntheticDemand.origin_county_fips,
        )
        .where(
            SyntheticDemand.origin_state_fips.is_not(None),
            SyntheticDemand.origin_county_fips.is_not(None),
        )
        .distinct()
        .order_by(SyntheticDemand.origin_state_fips, SyntheticDemand.origin_county_fips)
    ).all()
    mapping: dict[str, list[str]] = {}
    for row in rows:
        mapping.setdefault(row.origin_state_fips, []).append(row.origin_county_fips)
    return mapping


def list_available_demand_areas_named(session: Session) -> list[dict[str, Any]]:
    rows = session.execute(
        select(
            SyntheticDemand.origin_state_fips.label("state_fips"),
            SyntheticDemand.origin_county_fips.label("county_fips"),
            StateFips.state_name.label("state_name"),
            CountyGeo.name.label("county_name"),
            CountyGeo.geoid.label("geoid"),
        )
        .select_from(SyntheticDemand)
        .join(
            StateFips,
            StateFips.state_fips == SyntheticDemand.origin_state_fips,
        )
        .join(
            CountyGeo,
            (CountyGeo.state_fips == SyntheticDemand.origin_state_fips)
            & (CountyGeo.county_fips == SyntheticDemand.origin_county_fips),
        )
        .distinct()
        .order_by(SyntheticDemand.origin_state_fips, CountyGeo.name)
    ).all()

    grouped: dict[str, dict[str, Any]] = {}
    for row in rows:
        entry = grouped.setdefault(
            row.state_fips,
            {"state_fips": row.state_fips, "state_name": row.state_name, "counties": []},
        )
        entry["counties"].append(
            {
                "county_fips": row.county_fips,
                "county_name": row.county_name,
                "geoid": row.geoid,
            }
        )
    return list(grouped.values())


# ---------------------------------------------------------------------------
# Synthetic demand — existence / insert / delete
# ---------------------------------------------------------------------------


def has_synthetic_demand(
    session: Session,
    state_fips: str,
    county_fips: str,
) -> bool:
    exists = session.execute(
        text(
            "SELECT 1 FROM moveod_synthetic_demand "
            "WHERE origin_state_fips = :sf AND origin_county_fips = :cf LIMIT 1"
        ),
        {"sf": state_fips, "cf": county_fips},
    ).scalar_one_or_none()
    return bool(exists)


def delete_synthetic_demand(
    session: Session,
    state_fips: str,
    county_fips: str,
) -> int:
    deleted: int = session.execute(
        text(
            "DELETE FROM moveod_synthetic_demand "
            "WHERE origin_state_fips = :sf AND origin_county_fips = :cf "
            "RETURNING 1"
        ),
        {"sf": state_fips, "cf": county_fips},
    ).rowcount  # type: ignore[attr-defined]
    session.commit()
    return deleted


def insert_synthetic_demand(
    session: Session,
    records: list[SyntheticDemand],
    batch_size: int = 1000,
) -> int:
    total = 0
    for i in range(0, len(records), batch_size):
        batch = records[i : i + batch_size]
        session.add_all(batch)
        session.commit()
        total += len(batch)
    return total


# ---------------------------------------------------------------------------
# CSV parse helpers (shared with scripts/load_moveod_demand.py)
# ---------------------------------------------------------------------------


def _read_csv(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8-sig") as f:
        rows = []
        for row in csv.DictReader(f):
            clean = {
                key.strip(): (value.strip() if value is not None else "")
                for key, value in row.items()
            }
            rows.append(clean)
        return rows


def _parse_geoid(value: str) -> dict:
    geoid = (value or "").strip()
    if not geoid:
        return {
            "geoid": "",
            "state_fips": "",
            "county_fips": "",
            "census_tract_fips": "",
            "block_fips": "",
        }
    geoid = geoid.zfill(12)
    return {
        "geoid": geoid,
        "state_fips": geoid[0:2],
        "county_fips": geoid[2:5],
        "census_tract_fips": geoid[5:11],
        "block_fips": geoid[11:12],
    }


def _parse_datetime(value: str) -> datetime | None:
    raw = (value or "").strip()
    if not raw:
        return None
    if "." in raw:
        base, frac = raw.split(".", 1)
        frac = "".join(ch for ch in frac if ch.isdigit())
        if len(frac) > 6:
            frac = frac[:6]
        raw = f"{base}.{frac}"
    dt = datetime.fromisoformat(raw)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _point_wkt(lat: str, lon: str) -> WKTElement | None:
    if not lat or not lon:
        return None
    try:
        lat_f = float(lat)
        lon_f = float(lon)
    except ValueError:
        return None
    return WKTElement(f"POINT({lon_f} {lat_f})", srid=4326)


def _rows_to_orm(rows: list[dict]) -> list[SyntheticDemand]:
    records: list[SyntheticDemand] = []
    for row in rows:
        origin = _parse_geoid(row.get("origin_geoid", ""))
        destination = _parse_geoid(row.get("destination_geoid", ""))
        records.append(
            SyntheticDemand(
                origin_geoid=origin["geoid"],
                origin_state_fips=origin["state_fips"],
                origin_county_fips=origin["county_fips"],
                origin_census_tract_fips=origin["census_tract_fips"],
                origin_block_fips=origin["block_fips"],
                origin_location=_point_wkt(row.get("origin_lat", ""), row.get("origin_lon", "")),
                origin_node=row.get("origin_node") or None,
                destination_geoid=destination["geoid"],
                destination_state_fips=destination["state_fips"],
                destination_county_fips=destination["county_fips"],
                destination_census_tract_fips=destination["census_tract_fips"],
                destination_block_fips=destination["block_fips"],
                destination_location=_point_wkt(row.get("dest_lat", ""), row.get("dest_lon", "")),
                destination_node=row.get("destination_node") or None,
                departure_time_utc=_parse_datetime(row.get("departure_time", "")),
                departure_time_bin=row.get("departure_time_bin") or None,
                arrival_time_utc=_parse_datetime(row.get("arrival_time", "")),
                travel_time_min=float(row["travel_time_min"]) if row.get("travel_time_min") else None,
                travel_time_bin=row.get("travel_time_bin") or None,
                travel_distance_mi=float(row["travel_distance_mi"]) if row.get("travel_distance_mi") else None,
            )
        )
    return records

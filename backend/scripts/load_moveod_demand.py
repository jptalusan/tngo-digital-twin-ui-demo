from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path
import sys

from geoalchemy2 import WKTElement
from sqlalchemy import text

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.db import SessionLocal
from app.logging.config import get_logger
from app.models.moveod import SyntheticDemand

logger = get_logger("moveod-demand-loader")

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
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _point_wkt(lat: str, lon: str) -> WKTElement | None:
    if not lat or not lon:
        return None
    try:
        lat_f = float(lat)
        lon_f = float(lon)
    except ValueError:
        return None
    return WKTElement(f"POINT({lon_f} {lat_f})", srid=4326)


def main() -> None:
    base = Path(__file__).resolve().parent / "data" / "moveod" / "demand"
    csv_paths = sorted(base.glob("*.csv"))

    session = SessionLocal()
    try:
        batch = 0
        for path in csv_paths:
            rows = _read_csv(path)
            if not rows:
                continue
            first_origin = _parse_geoid(rows[0].get("origin_geoid", ""))
            if first_origin["state_fips"] and first_origin["county_fips"]:
                exists = session.execute(
                    text(
                        "SELECT 1 FROM moveod_synthetic_demand "
                        "WHERE origin_state_fips = :sf AND origin_county_fips = :cf LIMIT 1"
                    ),
                    {"sf": first_origin["state_fips"], "cf": first_origin["county_fips"]},
                ).scalar_one_or_none()
                if exists:
                    logger.warning(
                        "Skipping %s: data already exists for state_fips=%s county_fips=%s",
                        path.name,
                        first_origin["state_fips"],
                        first_origin["county_fips"],
                    )
                    continue

            for row in rows:
                origin = _parse_geoid(row.get("origin_geoid", ""))
                destination = _parse_geoid(row.get("destination_geoid", ""))
                session.add(
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
                        travel_distance_mi=float(row["travel_distance_mi"])
                        if row.get("travel_distance_mi")
                        else None,
                    )
                )
                batch += 1
                if batch >= 1000:
                    session.commit()
                    batch = 0

            logger.info("Loaded %s (%s rows)", path.name, len(rows))

        if batch:
            session.commit()

        logger.info("Loaded MoveOD synthetic demand data")
    finally:
        session.close()


if __name__ == "__main__":
    main()

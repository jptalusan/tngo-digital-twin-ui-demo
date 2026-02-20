from __future__ import annotations

import csv
import json
from pathlib import Path
import sys

from geoalchemy2 import WKTElement
from sqlalchemy import text

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.db import SessionLocal
from app.models.moveod import CountyGeo, CountyFips, StateFips, StateGeo


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


def _ensure_ring_closed(ring: list[list[float]]) -> list[list[float]]:
    if not ring:
        return ring
    if ring[0] != ring[-1]:
        return ring + [ring[0]]
    return ring


def _format_ring(ring: list[list[float]]) -> str:
    ring = _ensure_ring_closed(ring)
    return ", ".join(f"{lon} {lat}" for lon, lat in ring)


def _polygon_wkt(rings: list[list[list[float]]]) -> str:
    return "(" + ", ".join(f"({_format_ring(ring)})" for ring in rings) + ")"


def _geom_to_multipolygon_wkt(geom: dict) -> str:
    geom_type = geom.get("type")
    coords = geom.get("coordinates")
    if geom_type == "Polygon":
        return f"MULTIPOLYGON({_polygon_wkt(coords)})"
    if geom_type == "MultiPolygon":
        polys = ", ".join(_polygon_wkt(poly) for poly in coords)
        return f"MULTIPOLYGON({polys})"
    raise ValueError(f"Unsupported geometry type: {geom_type}")


def main() -> None:
    base = Path(__file__).resolve().parent / "data" / "moveod"
    states_path = base / "state-ansi-fips.csv"
    counties_path = base / "counties.geojson"
    states_geo_path = base / "us-states.json"
    county_fips_path = base / "uscounties.csv"

    states = _read_csv(states_path)
    with counties_path.open("r", encoding="utf-8") as f:
        counties_geo = json.load(f)

    session = SessionLocal()
    try:
        session.execute(
            text(
                "TRUNCATE TABLE moveod_county_geo, moveod_county_fips, "
                "moveod_state_geo, moveod_state_fips RESTART IDENTITY CASCADE"
            )
        )
        session.commit()

        state_fips_seen = set()
        state_name_to_fips = {}
        for row in states:
            state_fips = row.get("st", "")
            state_name = row.get("stname", "")
            if not state_fips:
                continue
            state_fips_seen.add(state_fips)
            if state_name:
                state_name_to_fips[state_name.strip().lower()] = state_fips
            session.add(
                StateFips(
                    state_fips=state_fips,
                    state_name=state_name,
                    state_abbr=row.get("stusps") or None,
                )
            )
        session.commit()

        county_state_fips = {
            str(feature.get("properties", {}).get("STATEFP", "")).strip()
            for feature in counties_geo.get("features", [])
        }
        missing_state_fips = sorted(
            fips for fips in county_state_fips if fips and fips not in state_fips_seen
        )
        if missing_state_fips:
            for fips in missing_state_fips:
                session.add(
                    StateFips(
                        state_fips=fips,
                        state_name=f"State {fips}",
                        state_abbr=None,
                    )
                )
            session.commit()

        with states_geo_path.open("r", encoding="utf-8") as f:
            states_geo = json.load(f)

        for feature in states_geo.get("features", []):
            props = feature.get("properties", {})
            geom = feature.get("geometry") or {}
            name = str(props.get("name", "")).strip()
            if not name:
                continue
            state_fips = state_name_to_fips.get(name.lower())
            if not state_fips:
                continue

            wkt = _geom_to_multipolygon_wkt(geom) if geom else None
            geometry = WKTElement(wkt, srid=4326) if wkt else None

            session.add(
                StateGeo(
                    state_fips=state_fips,
                    name=name,
                    density=props.get("density"),
                    geometry=geometry,
                )
            )
        session.commit()

        county_fips_rows = _read_csv(county_fips_path)
        for row in county_fips_rows:
            geoid = row.get("county_fips", "")
            if len(geoid) != 5 or not geoid.isdigit():
                continue
            state_fips = geoid[:2]
            county_fips = geoid[2:]
            session.add(
                CountyFips(
                    geoid=geoid,
                    state_fips=state_fips,
                    county_fips=county_fips,
                    county_name=row.get("county", ""),
                    county_full=row.get("county_full") or None,
                    state_id=row.get("state_id") or None,
                    state_name=row.get("state_name") or None,
                    lat=float(row["lat"]) if row.get("lat") else None,
                    lon=float(row["lng"]) if row.get("lng") else None,
                    population=int(row["population"]) if row.get("population") else None,
                )
            )
        session.commit()

        batch = 0
        for feature in counties_geo.get("features", []):
            props = feature.get("properties", {})
            geom = feature.get("geometry") or {}
            state_fips = str(props.get("STATEFP", "")).strip()
            county_fips = str(props.get("COUNTYFP", "")).strip()
            geoid = str(props.get("GEOID", "")).strip()
            if not (state_fips and county_fips and geoid):
                continue

            wkt = _geom_to_multipolygon_wkt(geom) if geom else None
            geometry = WKTElement(wkt, srid=4326) if wkt else None

            session.add(
                CountyGeo(
                    geoid=geoid,
                    state_fips=state_fips,
                    county_fips=county_fips,
                    county_ns=props.get("COUNTYNS"),
                    aff_geoid=props.get("AFFGEOID"),
                    name=props.get("NAME", ""),
                    lsad=props.get("LSAD"),
                    aland=props.get("ALAND"),
                    awater=props.get("AWATER"),
                    geometry=geometry,
                )
            )
            batch += 1
            if batch >= 1000:
                session.commit()
                batch = 0

        if batch:
            session.commit()

        print("Loaded MoveOD state FIPS and county geometries")
    finally:
        session.close()


if __name__ == "__main__":
    main()

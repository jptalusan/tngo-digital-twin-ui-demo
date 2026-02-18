"""
Load user-demand CSV files into the user_demand table.

Usage
-----
    python scripts/load_user_requests.py [--dir <path>]

Behaviour
---------
- Scans every *.csv file in <dir> (default: scripts/data/requests/).
- The demand_name is the filename stem (e.g. "week_2024_01" from "week_2024_01.csv").
- If a demand_name already exists in the DB the file is skipped with a warning.
- New files are loaded via PostgreSQL COPY for maximum throughput on large files.

Expected CSV columns (case-sensitive)
--------------------------------------
    user_id, building_id, COUNTYFP,
    h_lat, h_lon, w_lat, w_lon,
    travel_time_s, distance_m,
    transit_taker, shift_start, shift_end, shift
"""

from __future__ import annotations

import argparse
import csv
import io
import sys
import warnings
from pathlib import Path

# Allow imports from the backend root
sys.path.append(str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select, text

from app.db import SessionLocal, engine
from app.models.user_demand import UserDemand  # ensures table is registered

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_DEFAULT_DIR = Path(__file__).resolve().parent / "data" / "requests"

_REQUIRED_COLUMNS = {
    "user_id",
    "building_id",
    "COUNTYFP",
    "h_lat",
    "h_lon",
    "w_lat",
    "w_lon",
    "shift_start",
    "shift_end",
}
# Optional columns and their defaults
_DEFAULTS = {
    "shift": "0",
    "transit_taker": "true",
}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Load user-demand CSV files into PostgreSQL.")
    parser.add_argument(
        "--dir",
        type=Path,
        default=_DEFAULT_DIR,
        help=f"Directory containing CSV files (default: {_DEFAULT_DIR})",
    )
    return parser.parse_args()


def _demand_name_exists(session, demand_name: str) -> bool:
    row = session.execute(
        select(UserDemand.id).where(UserDemand.demand_name == demand_name).limit(1)
    ).first()
    return row is not None


def _validate_headers(headers: list[str], path: Path) -> bool:
    missing = _REQUIRED_COLUMNS - set(headers)
    if missing:
        warnings.warn(
            f"[SKIP] {path.name}: missing required columns: {sorted(missing)}",
            stacklevel=2,
        )
        return False
    return True


def _coerce_bool(value: str) -> bool:
    """Accept 1/0, true/false, yes/no (case-insensitive)."""
    return value.strip().lower() in {"1", "true", "yes", "t", "y"}


def _coerce_optional_float(value: str) -> str:
    """Return empty string (NULL) for missing/blank values, otherwise the raw string."""
    stripped = value.strip()
    return "" if stripped in {"", "none", "null", "na", "n/a"} else stripped


def _make_point(lat_str: str, lon_str: str) -> str | None:
    """
    Parse lat/lon strings and return an EWKT POINT or None if invalid.

    Valid ranges: lat in [-90, 90], lon in [-180, 180].
    Returns None (which becomes NULL / skipped row) for blanks, non-numeric,
    or out-of-range values.
    """
    try:
        lat = float(lat_str.strip())
        lon = float(lon_str.strip())
    except (ValueError, AttributeError):
        return None
    if not (-90.0 <= lat <= 90.0) or not (-180.0 <= lon <= 180.0):
        return None
    return f"SRID=4326;POINT({lon} {lat})"


def _coerce_time(value: str) -> str:
    """
    Extract HH:MM:SS from whatever the CSV contains.

    Handles:
      - Plain time:           "08:00:00"      -> "08:00:00"
      - ISO 8601 datetime:    "2024-10-28T17:00:00Z"  -> "17:00:00"
      - ISO with offset:      "2024-10-28T17:00:00+00:00" -> "17:00:00"
    """
    stripped = value.strip()
    if "T" in stripped:
        # "2024-10-28T17:00:00Z" or "...+00:00"
        time_part = stripped.split("T", 1)[1]
        # drop trailing Z / timezone offset
        time_part = time_part.rstrip("Z").split("+")[0].split("-")[0]
        return time_part[:8]  # take HH:MM:SS
    return stripped[:8]


# ---------------------------------------------------------------------------
# Core loader — uses PostgreSQL COPY for bulk performance
# ---------------------------------------------------------------------------

COPY_SQL = """
COPY user_demand (
    demand_name, user_id, building_id, count_fyp,
    home_location, work_location,
    travel_time_s, distance_m,
    transit_taker, shift_start, shift_end, shift
)
FROM STDIN
WITH (FORMAT csv, NULL '')
"""


def _load_file_via_copy(raw_conn, demand_name: str, path: Path) -> int:
    """
    Stream CSV rows through a PostgreSQL COPY command.

    Returns the number of rows inserted.
    """
    with path.open("r", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        headers = reader.fieldnames or []

        if not _validate_headers(list(headers), path):
            return 0

        # Build an in-memory buffer of transformed CSV for COPY
        buf = io.StringIO()
        writer = csv.writer(buf, lineterminator="\n")

        count = 0
        skipped = 0
        for row in reader:
            home = _make_point(row["h_lat"], row["h_lon"])
            work = _make_point(row["w_lat"], row["w_lon"])
            if home is None or work is None:
                skipped += 1
                continue
            writer.writerow(
                [
                    demand_name,
                    row["user_id"].strip(),
                    row["building_id"].strip(),
                    row["COUNTYFP"].strip(),
                    home,
                    work,
                    _coerce_optional_float(row.get("travel_time_s", "")),
                    _coerce_optional_float(row.get("distance_m", "")),
                    "true" if _coerce_bool(row.get("transit_taker", _DEFAULTS["transit_taker"])) else "false",
                    _coerce_time(row["shift_start"]),
                    _coerce_time(row["shift_end"]),
                    row.get("shift", _DEFAULTS["shift"]).strip(),
                ]
            )
            count += 1

        if skipped:
            print(f"  [WARN] {skipped:,} row(s) skipped due to invalid/out-of-range coordinates.")
        if count == 0:
            print(f"  [SKIP] {path.name}: no valid rows to insert.")
            return 0

        buf.seek(0)

        # psycopg3 exposes copy() on the raw connection cursor
        with raw_conn.cursor() as cur:
            with cur.copy(COPY_SQL) as copy:
                copy.write(buf.read())

        return count


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    args = _parse_args()
    directory: Path = args.dir

    if not directory.exists():
        sys.exit(f"Directory not found: {directory}")

    csv_files = sorted(directory.glob("*.csv"))
    if not csv_files:
        print(f"No CSV files found in {directory}")
        return

    print(f"Found {len(csv_files)} CSV file(s) in {directory}\n")

    session = SessionLocal()
    try:
        loaded_total = 0

        for path in csv_files:
            demand_name = path.stem

            # ---- Check if already loaded ----
            if _demand_name_exists(session, demand_name):
                print(f"  [WARN] '{demand_name}' already exists in the DB — skipping {path.name}")
                continue

            print(f"  Loading '{demand_name}' from {path.name} …", end=" ", flush=True)

            # Get a raw psycopg3 connection from the SQLAlchemy engine
            with engine.connect() as conn:
                raw_conn = conn.connection  # underlying psycopg3 Connection
                count = _load_file_via_copy(raw_conn, demand_name, path)
                if count > 0:
                    raw_conn.commit()
                    loaded_total += count
                    print(f"{count:,} rows inserted.")

        print(f"\nDone. Total rows inserted: {loaded_total:,}")
    finally:
        session.close()


if __name__ == "__main__":
    main()

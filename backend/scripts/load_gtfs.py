"""
CLI wrapper for GTFS loading.

Usage:
    uv run python scripts/load_gtfs.py --path scripts/data/gtfs/MERGED_gtfs.zip \
        --name "MERGED GTFS 2024"

The gtfs_id is derived from the MD5 hash of the zip file. Re-uploading the same
file is rejected with an error (same behaviour as the API's 409 response).
"""
from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app.db import SessionLocal
from app.models.gtfs import GtfsFeed
from app.services.gtfs_loader import load_gtfs_from_bytes


def main() -> None:
    parser = argparse.ArgumentParser(description="Load a GTFS zip into the database.")
    parser.add_argument("--path", required=True, help="Path to GTFS zip file.")
    parser.add_argument("--name", default="Test", help="Human-readable name for this GTFS feed (defaults to filename).")
    args = parser.parse_args()

    zip_path = Path(args.path)
    if not zip_path.exists():
        print(f"Error: file not found: {zip_path}", file=sys.stderr)
        sys.exit(1)

    gtfs_name = args.name or zip_path.stem
    zip_bytes = zip_path.read_bytes()
    gtfs_id = hashlib.md5(zip_bytes).hexdigest()

    session = SessionLocal()
    try:
        existing = session.execute(
            select(GtfsFeed).where(GtfsFeed.gtfs_id == gtfs_id)
        ).scalars().first()
        if existing is not None:
            print(
                f"Error: a GTFS feed with the same content already exists "
                f"(gtfs_id={gtfs_id}, name='{existing.gtfs_name}').",
                file=sys.stderr,
            )
            sys.exit(1)

        feed = GtfsFeed(gtfs_id=gtfs_id, gtfs_name=gtfs_name, filename=zip_path.name)
        session.add(feed)
        session.flush()

        print(f"Loading GTFS '{gtfs_name}' (gtfs_id={gtfs_id}) ...")
        counts = load_gtfs_from_bytes(session, zip_bytes, gtfs_id)

        print("Done. Row counts:")
        for table, n in counts.items():
            print(f"  {table}: {n:,}")

    finally:
        session.close()


if __name__ == "__main__":
    main()

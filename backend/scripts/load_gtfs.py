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
import io
import sys
import zipfile
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app.db import SessionLocal
from app.models.gtfs import GtfsFeed
from app.services.gtfs_loader import load_gtfs_from_bytes


def _path_to_zip_bytes(path: Path) -> bytes:
    """Return zip bytes for path, which may be a .zip file or a directory of GTFS .txt files."""
    if path.is_dir():
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for txt in sorted(path.glob("*.txt")):
                zf.write(txt, txt.name)
        return buf.getvalue()
    return path.read_bytes()


def load_gtfs(zip_path: Path, gtfs_name: str = "Test") -> None:
    """Load a GTFS zip (or directory of .txt files) into the database.

    Silently skips if a feed with the same MD5 already exists, so tests that
    call this multiple times (e.g. across fixtures) don't fail on re-upload.
    """
    zip_path = Path(zip_path)
    zip_bytes = _path_to_zip_bytes(zip_path)
    gtfs_id = hashlib.md5(zip_bytes).hexdigest()
    name = gtfs_name or zip_path.stem

    session = SessionLocal()
    try:
        existing = session.execute(
            select(GtfsFeed).where(GtfsFeed.gtfs_id == gtfs_id)
        ).scalars().first()
        if existing is not None:
            return  # already loaded — idempotent

        feed = GtfsFeed(gtfs_id=gtfs_id, gtfs_name=name, filename=zip_path.name)
        session.add(feed)
        session.flush()
        load_gtfs_from_bytes(session, zip_bytes, gtfs_id)
    finally:
        session.close()


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

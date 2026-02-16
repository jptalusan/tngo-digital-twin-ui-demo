from __future__ import annotations

from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))

from scripts.load_gtfs import load_gtfs


def main() -> None:
    gtfs_zip = Path(__file__).resolve().parent / "data" / "gtfs" / "MERGED_gtfs.zip"
    if not gtfs_zip.exists():
        raise FileNotFoundError(f"GTFS zip not found at {gtfs_zip}")

    load_gtfs(gtfs_zip, truncate=True)
    print(f"Loaded GTFS from {gtfs_zip}")


if __name__ == "__main__":
    main()

from __future__ import annotations

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.crud import moveod as moveod_crud
from app.db import SessionLocal
from app.logging.config import get_logger

logger = get_logger("moveod-demand-loader")


def main() -> None:
    base = Path(__file__).resolve().parent / "data" / "moveod" / "demand"
    csv_paths = sorted(base.glob("*.csv"))

    if not csv_paths:
        logger.warning("No CSV files found in %s", base)
        return

    session = SessionLocal()
    try:
        for path in csv_paths:
            rows = moveod_crud._read_csv(path)
            if not rows:
                logger.warning("Skipping empty file: %s", path.name)
                continue

            # Check for existing data before inserting
            first_origin = moveod_crud._parse_geoid(rows[0].get("origin_geoid", ""))
            sf = first_origin["state_fips"]
            cf = first_origin["county_fips"]

            if sf and cf and moveod_crud.has_synthetic_demand(session, sf, cf):
                logger.warning(
                    "Skipping %s: data already exists for state_fips=%s county_fips=%s",
                    path.name, sf, cf,
                )
                continue

            records = moveod_crud._rows_to_orm(rows)
            inserted = moveod_crud.insert_synthetic_demand(session, records)
            logger.info("Loaded %s (%d rows inserted)", path.name, inserted)

        logger.info("Finished loading MoveOD synthetic demand data")
    finally:
        session.close()


if __name__ == "__main__":
    main()

from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))

import app.models  # noqa: F401 — registers all ORM models with Base.metadata
from app.db import init_db, drop_moveod_analysis_tables


def main() -> None:
    drop = "--drop" in sys.argv
    drop_analysis = "--drop-analysis" in sys.argv
    if drop_analysis and not drop:
        drop_moveod_analysis_tables()
    init_db(drop=drop)
    print("Database initialized")


if __name__ == "__main__":
    main()

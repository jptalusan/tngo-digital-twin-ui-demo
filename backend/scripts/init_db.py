from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.db import init_db


def main() -> None:
    drop = "--drop" in sys.argv
    init_db(drop=drop)
    print("Database initialized")


if __name__ == "__main__":
    main()

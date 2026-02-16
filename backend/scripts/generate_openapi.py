import json
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.main import app


def main() -> None:
    schema = app.openapi()
    output_path = Path(__file__).resolve().parents[1] / "openapi.json"
    output_path.write_text(json.dumps(schema, indent=2))
    print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()

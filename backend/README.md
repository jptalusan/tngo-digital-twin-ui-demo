# Backend

## Quick start

1. Copy `.env.example` to `.env` and update values.
2. Install deps with uv (from `backend/`):

```bash
uv sync
```

3. Initialize the database:

```bash
uv run python scripts/init_db.py
```

To drop and recreate all tables:

```bash
uv run python scripts/init_db.py --drop
```

4. Start the API:

```bash
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## Scripts

- Generate OpenAPI schema:

```bash
uv run python scripts/generate_openapi.py
```

- Load GTFS data:

```bash
uv run python scripts/load_gtfs.py --path /path/to/gtfs.zip
```

- Load on-demand fleet data:

```bash
uv run python scripts/load_ondemand.py
```

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

To drop MoveOD analysis tables only:

```bash
uv run python scripts/init_db.py --drop-analysis
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
uv run python scripts/load_ondemand.py --dir scripts/data/requests
```

- Load MoveOD reference data (states/counties/FIPS):

```bash
uv run python scripts/load_moveod.py
```

- Load MoveOD synthetic demand CSVs:

```bash
uv run python scripts/load_moveod_demand.py
```

- Load user-demand request CSVs:

Place `*.csv` files in `scripts/data/requests/` (one file per demand scenario, filename becomes the `demand_name`). Each CSV must contain the columns: `user_id`, `building_id`, `COUNTFYP`, `h_lat`, `h_lon`, `w_lat`, `w_lon`, `transit_taker`, `shift_start`, `shift_end`, `shift`. The columns `travel_time_s` and `distance_m` are optional (nullable).

```bash
# default directory: scripts/data/requests/
uv run python scripts/load_user_requests.py

# or point at a custom directory
uv run python scripts/load_user_requests.py --dir /path/to/csvs
```

Files whose `demand_name` already exists in the DB are skipped with a warning. New files are inserted via PostgreSQL `COPY` for efficient handling of large files (10k+ rows).

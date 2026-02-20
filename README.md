# TNGO Digital Twin Monorepo

This repo contains a FastAPI backend and a React frontend for GTFS + on-demand planning.

## Docker (Postgres + PostGIS + pgAdmin + optional OSRM)

1. Create a root `.env` based on `.env.example`.
2. Start services:

```bash
cd docker

docker compose --env-file ../.env up -d
```

3. Stop services:

```bash
docker compose --env-file ../.env down
```

Notes:
- Postgres data persists in the `postgres_data` volume.
- pgAdmin runs at `http://localhost:${PGADMIN_PORT}`.
- OSRM is optional. Set `COMPOSE_PROFILES=osrm` in `.env` to enable.

## Backend

```bash
cd backend

uv sync
uv run python scripts/init_db.py
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Generate OpenAPI:

```bash
uv run python scripts/generate_openapi.py
```

Load GTFS:

```bash
uv run python scripts/load_gtfs.py --path /path/to/gtfs.zip
```

Load on-demand fleet: (optional)

```bash
uv run python scripts/load_ondemand.py
```

MoveOD utilities:

```bash
uv run python scripts/init_db.py --drop-analysis
uv run python scripts/load_moveod.py
# Optional (should be replaced by actual generation)
uv run python scripts/load_moveod_demand.py
```

## Frontend

```bash
cd frontend

npm install
npm run generate
npm run dev
```

## Tests

Tests use a separate database defined by `DATABASE_URL_TEST`. See `.env.example`.

```bash
cd backend

uv run pytest
```

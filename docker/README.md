# Docker setup

This folder contains a Postgres + PostGIS + pgAdmin stack with optional OSRM.

## Prereqs
- Docker and Docker Compose installed
- Root `.env` file present (see `.env.example` at repo root)

## Start services
From repo root:

```bash
cd docker

docker compose --env-file ../.env up -d
```

### Enable OSRM
Set `COMPOSE_PROFILES=osrm` in `.env` before running `docker compose`.

## Stop services

```bash
docker compose --env-file ../.env down
```

## Notes
- Postgres data is persisted in the `postgres_data` volume.
- pgAdmin runs at `http://localhost:${PGADMIN_PORT}`.
- Database connection string example:
  `postgresql+psycopg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@localhost:${POSTGRES_PORT}/${POSTGRES_DB}`
- OSRM runs at `http://localhost:${OSRM_PORT}` when enabled.

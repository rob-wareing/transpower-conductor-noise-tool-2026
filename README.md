# Transpower Conductor Noise Tool 2026

This repository is the refactored successor to the original conductor noise tool. The goal is to keep the original application available as a reference while rebuilding the system around clear boundaries:

- `backend/` owns ingestion, processing, database access, and API routes.
- `frontend/` owns Dash layout, callbacks, and presentation.
- `shared/` owns contracts and small data-transfer utilities.
- `alembic/` stays with the persistence boundary.

## Current status

This repository starts as a clean scaffold. The next implementation steps are to move one use case at a time from the original project into the new layered structure, beginning with a small backend health endpoint and a minimal frontend shell.

## Layout

```text
src/transpower_conductor_noise_tool_2026/
  backend/
    api/
    domain/
    ingestion/
    persistence/
  frontend/
    layout/
    callbacks/
  shared/
```

## Working principle

The frontend should never import ORM models or ingestion code directly. It should talk to backend endpoints or a narrow client wrapper that returns DTOs suitable for rendering.

## Docker compose deployment-like testing

This repository includes a Docker setup similar to the original project so the new architecture can be tested in an environment closer to deployment.

### Services

- `db`: MySQL 8.0 database
- `db-migrate`: dedicated schema migration + seed service
- `web`: Flask + Dash app served by Gunicorn
- `nginx` (optional): reverse proxy for production-like routing

### Start database, migration, and web

```bash
docker compose up --build db db-migrate web
```

### Access points

- App direct: `http://localhost:5001`
- Backend health: `http://localhost:5001/health`
- API health: `http://localhost:5001/api/health`
- Sites endpoint: `http://localhost:5001/api/sites`
- Login page: `http://localhost:5001/login`

### Demo login (dev-only)

Seeded via `data/user.csv` when `AUTO_SEED_DATA` is enabled:

- Email: `demo@transpower.example`
- Password: `demo-password`

### Start with optional reverse proxy

```bash
docker compose --profile prodlike up --build
```

Proxy entrypoint:

- `http://localhost:8080`

### Stop and remove containers

```bash
docker compose down
```

### Run migrations only

```bash
docker compose run --rm db-migrate
```

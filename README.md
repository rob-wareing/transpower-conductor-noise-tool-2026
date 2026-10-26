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

## Adding a user

The app has no admin screen for user accounts. Create them with `scripts/create_external_test_user.py`. Despite its name, this is the standard way to add any login-capable user, in production as well as for testing. It hashes the password the way the app's login expects, and it only ever adds the one row you ask for.

Run it through the `db-migrate` image, which includes `scripts/`. The `web` image doesn't.

**Production**: from the repo root on the server (where `.env` supplies `DATABASE_URL`):

```bash
docker compose -f docker-compose.prod.yml run --rm db-migrate \
  python scripts/create_external_test_user.py \
  --email someone@transpower.co.nz \
  --password '<their-password>' \
  --name "Their Name"
```

**Local dev stack**: the same command without `-f docker-compose.prod.yml`. It then targets the local `db` service's `development` database.

Options:

| Option | Required | Meaning |
| --- | --- | --- |
| `--email` | yes | Login email. Must be unique. |
| `--password` | yes | Initial password. |
| `--name` | no | Display name shown in the app header (default `External Test User`). |
| `--write-access` | no | Allows saving edits. Leave it off for a read-only user. |

If it worked, the script prints `Created user '<email>' (id=..., write_access=...)`. If the email already exists, it says so and changes nothing.

**Read-only vs write access**

- Every logged-in user can view all tabs and export CSVs.
- Only users created with `--write-access` can save changes to sites, outages, reconductoring events, historical results and the Charts tab's processed-readings table. For anyone else the backend refuses the save with `write access required` (HTTP 403). The edit controls are still visible to them.

**Notes**

- **Password on the command line:** it is saved in your shell history. Put a space before the command (works when `HISTCONTROL` includes `ignorespace`, as on Ubuntu by default), or remove the history entry afterwards.
- **Changing a user later:** the script can't change a password or grant or remove write access for an existing user. Do that directly in the database's `user` table, using the `write_access` column.
- **Old accounts:** accounts carried over from the original app's database can't log in, because their password hashes use an incompatible format. Create them again with this script.

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

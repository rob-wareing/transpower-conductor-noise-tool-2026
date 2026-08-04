# Project Context for Claude Code

This file gives persistent context for Claude Code sessions in this repository. Read this before making changes.

## What this repo is

`transpower-conductor-noise-tool-2026` is a from-scratch rebuild of the sibling repo `transpower-conductor-noise-tool` (one level up, at `../transpower-conductor-noise-tool`). The original app is a Flask + Dash monolith that:
- ingests noise/tonality readings from a third-party API (Noise and Weather API)
- processes and stores them in a database (MySQL in prod, SQLite for local dev)
- serves a Dash UI with tabs (Charts, Sites, Outages, Reconductoring, Historical, Trends, Locations) that queries and displays that data

The original repo is kept untouched as a reference. It is NOT a dependency of this repo — do not import from it. Read it only to port logic/behavior.

This repo has real git history and a GitHub remote (`origin`). Claude Code has not made any commits itself and shouldn't start doing so unprompted — only commit when explicitly asked, and always run `git status` before anything destructive. Verify the current branch/commit state with `git status`/`git log` rather than trusting any specific commit noted historically in this file.

## Why this repo exists (goal)

Separate the system into clear layers so ingestion/processing/persistence can evolve independently from the UI:
- `backend/`: ingestion, processing, persistence (SQLAlchemy models + repositories), domain services, API routes
- `frontend/`: Dash layout + callbacks only — must depend on API contracts, never on ORM models or ingestion code directly
- `shared/`: Pydantic contracts (DTOs) used by both sides
- `alembic/`: schema migrations, tied to the backend persistence boundary

Working principle: frontend code should never import ORM models or ingestion modules. It talks to backend HTTP endpoints via a thin client wrapper (`frontend/client.py`), which returns shared contract objects.

## Repo layout

```text
src/transpower_conductor_noise_tool_2026/
  backend/
    api/            # Flask blueprint(s) + routes; auth_guard.py (require_write_access decorator); processed_reading_routes.py (PATCH is_wet/include); trends_routes.py (POST /api/trends/conductor-summary, POST /api/trends/rain-rate-vs-level)
    domain/         # site_service.py, auth_service.py, chart_service.py (fully feature-complete vs. the old app - outage exclusion, bucketing, historical overlay, conductor/treatment/grease filtering, days-since-conductoring mode, raw table rows), processing_service.py (pure Reading -> ProcessedReading pandas transform, "original" detection logic, real leq_rmse calculation from Leq900 data), processing_service_updated_2026.py ("Updated 2026" detection logic - new filter rules, run alongside the original), historical_service.py, processed_reading_service.py, trends_service.py (get_rain_rate_vs_level and get_conductor_summary are real; get_age_effects is still a placeholder; compute_rain_rate_fits is the pure log-fit function behind rain_rate_fit)
    ingestion/      # nw_client.py (Noise and Weather API connector), ingestion_job.py (orchestrator), ingest_cli.py (entrypoint)
    persistence/
      models/       # SQLAlchemy ORM models: Site, User, ProcessedReading, Reading, Outage, OutageType, Reconductoring, HistoricalResult, ConductorSummary, RainRateFit
      repositories/ # repository-pattern data access - one per model, plus find_by_id/save/add/delete method shapes as each tab needed them; conductor_summary_repository.py and rain_rate_fit_repository.py are both delete-all-then-bulk-insert only (the whole table is always fully regenerated)
      seed.py       # CSV-based demo data seeding
      seed_cli.py   # entrypoint used by db-migrate container
    app.py          # Flask app factory
    config.py       # Settings incl. AUTO_INIT_DB / AUTO_SEED_DATA / SECRET_KEY / SESSION_COOKIE_SECURE / *_FIXTURE_PATH / NW_* flags
    extensions.py   # db = SQLAlchemy(); also enables SQLite FK enforcement (off by default in SQLite, on in the real MySQL deployment)
  frontend/
    app.py          # Dash app factory (create_dashboard) + plain /login, /logout routes + dcc.Location auth gate + dbc.Tabs(Charts, Sites, Outages, Reconductoring, Historical, Trends, Locations) - all 7 old-app tabs; explicit assets_folder= (Dash's default inference would otherwise resolve to backend/assets, not frontend/assets); header is title (H1.display-6, "Conductor Noise Tool") + right-aligned username/Log-out block
    client.py       # BackendClient - HTTP wrapper the frontend uses instead of ORM
    assets/
      app_styles.css  # ported from the old app's application/static/css/app_styles.css - table/card styling, zebra stripes, editable-cell highlight CSS, fixed column widths, Dash auto-loads this via assets_folder
    callbacks/      # sites.py, outages.py, reconductoring.py, historical.py (add/edit/delete via diff-against-server-truth on Save; all four also have a CSV export callback via dcc.Download, same in-memory pattern as Charts - no on-disk files); charts.py (conductor/grease option population, chart refresh, raw-table refresh/save/PATCH, CSV export via dcc.Download); locations.py (builds the Scattermapbox figure client-side from GET /api/sites/detail); trends.py (Conductor summary's metric/detection_logic/duration/site dropdowns and Rain rate vs level's detection_logic/metric/site/include-dry dropdowns each refresh a server-built figure via their own POST /api/trends/... route, same server-builds-the-figure pattern as Charts; Age effects sub-tab has nothing interactive)
    layout/         # sites.py, outages.py (dropdown-backed outage_type), reconductoring.py, historical.py, locations.py (dcc.Graph map + click-to-inspect info div), trends.py (3 sub-tabs: Rain rate vs level and Conductor summary are real filter-panel + dcc.Graph panels, Age effects is still a "Coming Soon" placeholder); charts.py (site+date range / condition+parameter+aggregation+duration / conductor+grease / detection-logic+plot-by filter rows, collapsible raw-data table, two dcc.Download components); table_styles.py (shared EDITABLE_CELL_HIGHLIGHT style_data_conditional) - every tab's buttons use dbc.Button with the old app's role-based color convention (secondary/success/primary)
  shared/
    contracts.py    # Pydantic DTOs - Site*, ChartFilters/ChartsResponse/ChartTableRow/ChartTableResponse, ConductorSummaryFilters, RainRateVsLevelFilters, UserSummary, Outage*, Reconductoring*, HistoricalResult*, ProcessedReadingUpdate
alembic/
  env.py            # wired to real SQLAlchemy metadata, online mode works
  versions/         # 0001-0007: create site/user/processed_reading/reading/outage/reconductoring/historical_result tables
                     # 0008: site.latitude/longitude  |  0009: measurement_duration_minutes on reading+processed_reading
                     # 0010: processed_reading.detection_logic + reading.leq_rmse  |  0011: processed_reading.leq_rmse
                     # 0012: create conductor_summary table  |  0013: conductor_summary gains measurement_duration_minutes in its key
                     # 0014: create rain_rate_fit table (precomputed per-site/detection_logic/metric logarithmic best-fit)
tests/
  test_health.py, test_sites.py, test_auth.py, test_charts.py, test_site_updates.py, test_outages.py,
  test_reconductoring.py, test_historical.py         # full-Flask-app API-level tests
  test_processing_service.py, test_processing_service_updated_2026.py, test_nw_client.py  # pure-function / mocked-HTTP tests, no Flask app needed
  test_ingestion_job.py, test_trends.py              # full-Flask-app tests for ingestion and the Trends API routes
  test_processed_reading_repository.py, test_conductor_summary_repository.py, test_rain_rate_fit_repository.py  # repository-level tests (new filter params)
  test_trends_service.py                             # trends_service.py pure-function tests (fake repositories, no DB)
  dash_callback_utils.py       # shared harness for driving Dash callbacks via /_dash-update-component in tests (no browser)
  test_charts_callbacks.py, test_sites_callbacks.py, test_outages_callbacks.py, test_reconductoring_callbacks.py,
  test_historical_callbacks.py, test_locations_callbacks.py, test_trends_callbacks.py  # Dash-callback tests, all 7 tabs
docker-compose.yml   # db, db-migrate, web, ingest (profile: ingestion), optional nginx (profile: prodlike) - LOCAL DEV ONLY
docker-compose.external-test.yml  # gitignored, local-only - points web/ingest at an external MySQL fork via -f
docker-compose.prod.yml  # PRODUCTION: db-migrate/web/ingest pointed at DATABASE_URL from .env (the managed MySQL DB, no local `db` service) - see DEPLOY.md
.env.example         # placeholder env var reference for both local dev and DEPLOY.md's production setup - copy to .env and fill in real values (.env itself is gitignored)
DEPLOY.md             # step-by-step Digital Ocean Droplet (Ubuntu 24.04) production setup guide: server prep, TLS via host nginx+certbot, docker-compose.prod.yml, daily cron jobs for ingest/generate_conductor_summary/generate_rain_rate_fits
scripts/
  create_external_test_user.py                    # one-off: add a login-capable user to whatever DATABASE_URL points at
  backfill_reconductoring_grease_and_treatment.py  # one-off: backfill reconductoring.grease/conductor_and_treatment from a CSV (--dry-run)
  backfill_site_coordinates.py                     # repeatable: backfill site.latitude/longitude from data/site_locations.csv, matched by noise_site_id (--dry-run)
  backfill_updated_2026_processed_readings.py      # re-run the "Updated 2026" detection logic over each site's raw Reading history (--dry-run, --force; auto-regenerates sites whose rows predate real leq_rmse data)
  import_leq_rmse_from_sqlite.py                   # bulk-load real leq_rmse values from a local SQLite export into reading.leq_rmse (temp-table + set-based UPDATE, not per-row; --dry-run)
  generate_conductor_summary.py                    # repeatable: fully regenerates the conductor_summary table from current processed_reading data (--dry-run)
  generate_rain_rate_fits.py                       # repeatable: fully regenerates the rain_rate_fit table (per site/detection_logic/metric logarithmic best-fit) from current processed_reading data (--dry-run)
Dockerfile           # web image (gunicorn)
docker/Dockerfile.migrate  # migration-only image, also reused (different command) for the `ingest` service
data/site.csv                # trimmed demo fixture (20 rows), used for seeding - carries NO latitude/longitude columns (that claim here was previously stale); coordinates come from data/site_locations.csv instead, via scripts/backfill_site_coordinates.py
data/user.csv                 # demo user fixture (1 row) - dev-only credentials, see README
data/processed_reading.csv    # synthetic demo fixture (829 rows) - real ingestion exists but isn't wired to run automatically; this still populates the demo/dev DB
data/outage_type.csv          # fixed lookup values (monitoring, line) - matches old repo's real seed exactly
data/outage.csv               # a few demo outage rows
data/reconductoring.csv       # a few demo reconductoring-event rows (sites 51, 115 - neither's conductor_and_treatment matches the 6 known colour-coded types, see "Known gotchas")
data/reconductoring_2026.csv  # real Grease/"SC proposed renaming" values, used once against the external fork, not part of the local demo seed
data/historical_result.csv    # 154 rows ported from the old repo's real data, filtered to the sites in this repo's trimmed data/site.csv
data/site_locations.csv       # real, manually-curated site coordinates ("Site ID,lon,lat" - a different shape from site.csv, which carries no coordinate columns), growing over time; source of truth for scripts/backfill_site_coordinates.py
```
Local-only, gitignored files used for testing against the external MySQL fork: `.env` (`DATABASE_URL`/`NW_USERNAME`/`NW_PASSWORD`/`NW_BASE_URL`/`INGEST_SITE_IDS`), `docker-compose.external-test.yml`, `ca-certificate.crt` (TLS CA cert). See "How to run against the external MySQL fork" below.

Also machine-local, entirely outside this repo (one level up, provided by you): `../local_data/db_3.sqlite` (14GB, `noise_weather_exported` table) — the real RMSE data source for `scripts/import_leq_rmse_from_sqlite.py`. `../local_data/example_leq900.txt` — a real example of the NW API's `Leq900` field, used to confirm the parsing format for `processing_service.calculate_leq_rmse`.

## Current status (as of 2026-08-03)

The migration is functionally complete: all 7 of the old app's tabs exist and are feature-complete or intentionally scoped versus the old app, real ingestion has been verified against the live NW API and a real forked production database, and 240 automated tests pass (155 backend, 85 frontend-callback).

### What's built, by area

**Auth** — Flask session-based login (`werkzeug.security` hashing, not the old app's hand-rolled cookie scheme). `write_access` enforced **server-side** on every write endpoint via `@require_write_access` — a real security fix over the old app, whose gating was client-side only.

**Charts tab** — fully feature-complete vs. the old app: per-site line chart + data-availability timeline, weekly-aggregation bucketing, historical-data overlay (splices in `HistoricalResult` up to each site's survey cutover date), conductor/treatment/grease filters, days-since-conductoring plot mode, `append_outages()` window exclusion, collapsible editable raw-data table (`is_wet`/`include`), in-memory CSV export (`dcc.Download`, no on-disk files — the old app's download mechanism had a confirmed path-mismatch bug). `measurement_duration_minutes` (1 or 15 min) and `detection_logic` (`original`/`updated_2026`) filters are both wired to real filtering.

**Sites / Outages / Reconductoring / Historical tabs** — Sites is edit-only (matches the old app; no add/delete flow, new sites only arrive via `data/site.csv`). Outages/Reconductoring/Historical are genuinely add/edit/delete-capable via per-row REST endpoints, with the **frontend** diffing the submitted table against server state to decide what to call (a deliberate divergence from the old app's single generic bulk-sync callback). All 5 tabs with tabular data have in-memory CSV export.

**Locations tab** — real per-site map (`Site.latitude`/`longitude`), built from `GET /api/sites/detail`; a deliberate improvement over the old app's 5-hardcoded-dummy-point stub. Read-only, no write callback (matches old app).

**Ingestion + processing** — `NoiseAndWeatherClient` → `processing_service.py` (pure pandas transform) → `ingestion_job.py::collect_new_readings` (orchestrator). Two detection-logic pipelines run side by side per ingested reading, each writing its own tagged `ProcessedReading` rows (never blended): `original` (the initial port) and `updated_2026` (`processing_service_updated_2026.py` — 22:00–05:00 window, `wind < 1.5`, current-period-only `is_wet`, no Leq−L90 filter, a valid-sensor-data check, an `leq_rmse` threshold check). `leq_rmse` is a real calculation (`processing_service.calculate_leq_rmse`): an OLS straight-line fit against the NW API's `Leq900` 1-second-per-period field, RMSE of the residuals, `NULL` if `Leq900` is missing or <50% populated. Historical `reading.leq_rmse` values (predating this calculation) were separately backfilled from an external SQLite export.

**Trends tab** — 3 sub-tabs:
- **Conductor summary** — real, populated. A materialized `conductor_summary` table (one row per site × detection_logic × measurement_duration_minutes, regenerated from `processed_reading` by `scripts/generate_conductor_summary.py`) displayed as a single horizontal box plot, one box per site, coloured by each site's *current* conductor type (from `reconductoring`'s most recent event per site, limited to Zebra/Goat/Curlew/Sulphur/Pheasant/Chukar with an "Unknown" fallback for no-match/no-event sites). Filters: metric, detection_logic, measurement_duration_minutes, site multi-select.
- **Rain rate vs level** — real, populated. Scatter of the selected metric against `rain1`, one coloured trace per site, reading raw `processed_reading` rows directly (no materialized table). Filters: detection_logic, metric, site multi-select (default all), "Include dry" toggle (default `False` — dry/`is_wet=0` points excluded by default). Each site with a stored `rain_rate_fit` row also gets a dashed logarithmic best-fit line (`metric = slope*ln(rain1) + intercept`) in the same colour as that site's markers — the fit itself is **precomputed** (`trends_service.compute_rain_rate_fits` + `scripts/generate_rain_rate_fits.py`, one row per site × detection_logic × metric in the `rain_rate_fit` table, fit over wet/included/`rain1>0` rows, skipped if <3 qualifying points) and only looked up at request time, never refit per chart request/filter change.
- **Age effects** — still a placeholder. No table, no pipeline, `trends_service.get_age_effects()` returns `[]`.

**External MySQL fork** — the app has been proven end-to-end against a real forked production database (not just local demo fixtures) and the real NW API. Schema is fully in sync through migration `0014` (every column/table applied there via direct `ALTER TABLE`/`CREATE TABLE`, run by you — see "How to run against the external fork" for why). Real data loaded: ~1.64M real `leq_rmse` values, a 137,044-row `updated_2026` backfill, a 54-row `conductor_summary`, a 162-row `rain_rate_fit` (60 sites × both detection_logics × 3 metrics, generated 2026-08-03 via `scripts/generate_rain_rate_fits.py`).

**Tests** — 240 passing: 155 backend (full-Flask-app tests, pure-function tests, a mocked-HTTP-boundary test, a handful of repository-level tests), 85 Dash-callback tests (all 7 tabs, via `tests/dash_callback_utils.py` driving the real `/app/_dash-update-component` endpoint — Dash callbacks are closures with no importable name, so this is the only way to exercise the actual registered callback rather than a hand-copied stand-in).

**Production deployment** — `DEPLOY.md` is a full step-by-step guide for a Digital Ocean Droplet (Ubuntu 24.04): host setup (ufw, Docker, nginx, certbot), `docker-compose.prod.yml` (points `db-migrate`/`web`/`ingest` at the existing managed MySQL DB via `DATABASE_URL` in `.env` — no local `db` container in prod), TLS via host nginx + Let's Encrypt (not a dockerized nginx — simpler cert renewal via certbot's own systemd timer), and 3 staggered daily cron jobs (`ingest`, then `generate_conductor_summary.py`, then `generate_rain_rate_fits.py`, each wrapped in a `flock`-guarded logging script). Not yet actually run against a real Droplet — the guide is written and locally verified (`docker-compose.prod.yml config` validates, `docker/Dockerfile.migrate` builds and now contains `scripts/`), but no Droplet has been provisioned yet.

### Outstanding issues
- **Trends / Age effects sub-tab** — fully unstarted. No table, no offline pre-processing pipeline, no backend function beyond a `[]`-returning placeholder.
- **Locations tab** — `go.Scattermapbox` is deprecated by the installed Plotly version (cosmetic warning only); a swap to `go.Scattermap` hasn't been done.
- **Site coordinates on the external fork** — 29 of 35 real sites now have real `latitude`/`longitude` (backfilled 2026-08-03 from `data/site_locations.csv` via `scripts/backfill_site_coordinates.py`, replacing the previous 12 sites' rougher approximate values too). 6 real sites still have no entry in `data/site_locations.csv` and remain uncoordinated; add them there and re-run the script (safe/idempotent) as more real coordinates become available. The local demo DB's 12 overlapping sites were also backfilled with the same real values (previously `NULL` — `data/site.csv` itself carries no coordinate columns, so nothing populated them at seed time).
- **No scheduling for the `ingest` service locally** — `docker-compose.yml` (local dev) only supports a manually-triggered one-shot, matching the old app. `DEPLOY.md`'s production Droplet setup adds real daily cron scheduling for `ingest` (host crontab + `docker-compose.prod.yml`, not APScheduler/Celery/an in-repo scheduler) — but that's Droplet-only, not something a local `docker compose up` gets.
- **Ingestion doesn't auto-create `Site` rows** for sites the NW API knows about but the local DB doesn't (deliberately not ported — the old app's field mapping for this was never confirmed, so it was skipped rather than guessed). Any real site must exist in `data/site.csv`/the `site` table first.
- **Repository-level unit tests are still sparse** below the full-Flask-app-context level — most backend testing goes through a full Flask app; only `test_processing_service.py`/`test_nw_client.py` and a few repository-only test files are Flask-app-free. Not a blocker, a coverage nice-to-have.
- **`generate_conductor_summary.py`/`generate_rain_rate_fits.py` are manually-run locally**, same as the fork (confirmed via `AskUserQuestion` that a manually-run script, not new scheduling infra, is what's wanted there). On the production Droplet (`DEPLOY.md`) both run daily via cron instead, staggered after `ingest`.

## Known gotchas already hit — don't repeat them
- `.dockerignore` must not exclude `alembic/versions/` — it did originally, which silently made `alembic upgrade head` a no-op in the migrate container (no error, just nothing to apply).
- `backend/config.py`'s `ROOT_DIR` must be `Path(__file__).resolve().parents[3]` (was `[4]`, one level too high — broke default fallback paths for bare/local `pytest`). If you add a new `*_FIXTURE_PATH`-style setting, add its env var override to **both** the `db-migrate` and `web` service blocks in `docker-compose.yml` — easy to forget one.
- No local venv/Poetry install is available in this dev environment — run tests and one-off scripts inside ad hoc `python:3.11-slim` containers (`docker run --rm -v "$(pwd):/app" -w /app python:3.11-slim bash -c "pip install -e . pytest && python -m pytest tests/ -v"`), not bare `pytest` on the host. See "How to run / verify locally" below.
- MySQL's `alembic_version.version_num` column is `VARCHAR(32)` — a revision id longer than that lets the migration's DDL succeed (MySQL DDL auto-commits) but then fails the version-stamp `UPDATE`, leaving a half-migrated state. Keep revision ids short. Recovery for the disposable local dev volume: `docker compose down -v`.
- A fresh (empty) `mysql_2026_data` volume can make `db-migrate`'s very first connection attempt fail with `Connection refused` even though `db`'s healthcheck already reports healthy (MySQL restarts internally after first-time data-dir init). Only happens on a brand-new volume — just re-run `docker compose up db-migrate` a few seconds later.
- The Dash `/app/_dash-update-component` endpoint needs `"outputs"` as a single `{"id":..., "property":...}` **dict**, not a list, for a single-`Output` callback (Dash 2.18.2) — a list is interpreted as multi-output/wildcard and raises `InvalidCallbackReturnValue`.
- `Settings.SQLALCHEMY_DATABASE_URI` is read fresh from the environment inside `create_app()`, not from a stale class attribute evaluated once at import time — needed so `monkeypatch.setenv("DATABASE_URL", ...)` actually takes effect per-test. Any new `Settings` attribute a test needs to override the same way needs the same treatment.
- `pandas.DataFrame.between_time`'s `include_start`/`include_end` kwargs don't exist in this repo's resolved pandas (2.3.x) — use `inclusive="both"/"neither"/"left"/"right"` instead.
- A Pydantic v2 `ValidationError` from a custom `@field_validator` that raises a plain `ValueError` isn't directly JSON-serializable via bare `exc.errors()` (the `ctx` key holds the raw exception object) — use `exc.errors(include_context=False)` before `jsonify()`-ing it. Check any *new* validator anywhere in the API layer for this.
- Don't wire two Dash callbacks to the same `Input` when one's result must happen strictly after the other (e.g. "refresh" and "save" both listening to a button's `n_clicks`) — Dash doesn't guarantee execution order. Chain them: make the refresh's `Input` the *save callback's own Output* instead. See `frontend/callbacks/sites.py`.
- SQLite does **not** enforce `FOREIGN KEY` constraints by default (unlike the real MySQL deployment) — enabled globally via a SQLAlchemy `Engine, "connect"` event listener (`PRAGMA foreign_keys=ON`) in `backend/extensions.py`. Any new FK-constrained model relies on this already being wired up.
- Flask's `jsonify()` serializes raw `datetime`/`date` objects as HTTP-date, not ISO 8601 — a client-side Pydantic model expecting ISO will fail to parse it back. Call `.model_dump(mode="json")` (not bare `.model_dump()`) on any Pydantic model with date/datetime/Decimal fields before `jsonify()`-ing it.
- `db.create_all()` never `ALTER`s an existing table, only creates missing ones — a stale local dev SQLite file (`data/transpower_conductor_noise_tool_2026.db`, the fallback DB when no `DATABASE_URL` is set) or a persisted `mysql_2026_data` Docker volume will silently keep an old schema after a migration adds columns. Delete the SQLite file, or `docker compose down -v` the volume, to force a clean rebuild — required if you need the new columns' *seeded* values, not just `NULL`s on already-seeded rows.
- **Large-scale writes against the external MySQL fork must be set-based/bulk, not a per-row ORM loop.** Per-row `db.session.add()` at real scale (tens of thousands of rows) hit repeated `pymysql.err.OperationalError: (2013, 'Lost connection to MySQL server during query')` — a managed-MySQL connection/session age limit, not a transaction-size one. Standing fix: (1) `sa.insert(table)` Core bulk inserts in ~5,000-row chunks instead of `session.add()` in a loop; (2) for genuinely cross-database loads, bulk-load into a session-scoped `TEMPORARY TABLE` and finish with one set-based `UPDATE ... JOIN`, never per-row `UPDATE`s.
- **A pandas float64 column with some real values and some missing ones stores the missing ones as `NaN`, not `None`** — PyMySQL has no representation for `NaN` and raises `ProgrammingError: nan can not be used with MySQL` rather than converting it (an all-`None` column is unaffected). Any DataFrame-derived value written to the DB that can be legitimately missing needs `None if pd.isna(value) else value` applied at the DB-write boundary (see `processing_service.clean_leq_rmse`).
- **A MySQL `ALTER TABLE` that both drops and re-adds a `PRIMARY KEY` must be one statement, not two separate ones.** Splitting `DROP PRIMARY KEY` and `ADD PRIMARY KEY` into two Alembic operations (`op.drop_constraint` then `op.create_primary_key`) fails with `OperationalError: (1553, "Cannot drop index 'PRIMARY': needed in a foreign key constraint")` — MySQL validates the FK column still has a covering index against the state *between* the two statements, not just the final state. Fix: one raw `op.execute("ALTER TABLE t DROP PRIMARY KEY, ADD PRIMARY KEY (...)")`.
- **`AUTO_SEED_DATA` seeds 829 demo `ProcessedReading` rows (all `detection_logic="original"`, `include=True`, plus a couple of real `reconductoring` rows for sites 51/115) into every test database** — an "empty data"/"no baseline" test scoped to the default `detection_logic="original"` isn't actually empty, and a test seeding its own row can silently lose to (or collide with) this baseline data. Hit repeatedly (`test_ingestion_job.py`, the Trends API tests, the conductor-colour test). Fix: scope such tests to `detection_logic="updated_2026"` (zero seeded rows) or otherwise date/id your test data outside what the baseline CSVs contain — don't assume a fresh test DB has *no* data in it.
- **Plotly 6.x's JSON encoder switches numeric trace arrays to a compact base64 `{"dtype":..., "bdata":...}` format when the array passed to a trace constructor (e.g. `go.Scatter(x=..., y=...)`) is a numpy-backed pandas Series rather than a plain Python list** — renders fine in a real browser, but breaks any code that reads the figure's own JSON expecting plain numbers (e.g. a CSV-export callback). Fix: call `.tolist()` on the Series before passing it into the trace constructor.
- **`go.Box` in Plotly's "precomputed statistics" mode has no per-box colour array within a single trace — only a per-*trace* colour.** To colour individual boxes differently (e.g. by category), split into one trace per colour group, each covering only its own subset of the shared categorical axis, then pin the full axis order explicitly (`categoryorder="array", categoryarray=[...]`) so the split doesn't scramble the ordering.
- **Plotly's default per-trace colour cycling breaks once you interleave more than one trace per category** (e.g. a marker trace + a fit-line trace per site) — the two traces for the same site drift out of sync with each other's colour. Fix: assign colours explicitly from a fixed palette (`plotly.colors.qualitative.Plotly`), cycling by category index yourself, applied to both traces; use `legendgroup` + `showlegend=False` on the secondary trace so the legend doesn't double up. See `trends_service.get_rain_rate_vs_level`'s `SITE_COLOR_PALETTE`.
- **`.env` files created in a Windows editor may have CRLF line endings** — Bash's `source .env` doesn't strip the trailing `\r`, so a value like a file path (`ssl_ca=/app/ca-certificate.crt\r`) silently fails to resolve. Normalize to LF if a value "mysteriously doesn't exist."
- **This repo's own Alembic must never be run against the external MySQL fork** — its `alembic_version` table holds the *old app's* real migration bookkeeping (unrelated to this repo's `0001...0013` revision-id namespace despite the identical table name). Every fork schema change is a plain direct `ALTER TABLE`/`CREATE TABLE`, run by you, never through this repo's migration tooling.
- Auto-mode's write-action classifier unpredictably blocks some direct external-DB write attempts (e.g. an inline `ALTER TABLE` via `python -c`) but not others (a proper `scripts/*.py` invocation, or `docker compose run`) — prefer a real script over an inline one-liner when touching the fork; if blocked, explain the command and get direct execution or explicit approval.
- Dev environment quirks (Windows host, Git Bash tool): prefix any `docker run`/`docker compose` command containing a bind-mount path with `MSYS_NO_PATHCONV=1` (Git Bash mangles POSIX paths otherwise); `/tmp` is not reliably writable/readable from this Bash tool — use the session's scratchpad directory instead.
- **A bare `__pycache__/` line in `.dockerignore` does NOT reliably exclude nested `__pycache__` dirs at every depth** (confirmed by building `docker/Dockerfile.migrate` after adding `COPY scripts /app/scripts` — `scripts/__pycache__/*.pyc` still landed in the image). Use `**/__pycache__/` instead. `.gitignore`'s bare `__pycache__/` is unaffected (git's own matching does apply at any depth) — this is a Docker-build-context-specific gotcha, not a general one.

## Key decisions already made (don't relitigate without reason)
- Keep the original `transpower-conductor-noise-tool` untouched as a reference copy — never import from it.
- Modular-monolith-to-two-apps migration, not a microservices split.
- Frontend/backend separation is the primary boundary; don't split ingestion/API/persistence into separate deployables yet.
- Preserve current user-facing behavior first, refine internals second.
- Shared DTOs live inside this repo (`shared/contracts.py`), not a separate installable package.
- Frontend calls backend via a thin client wrapper (`frontend/client.py`), not raw HTTP calls scattered through callbacks.
- Follow the layered vertical-slice pattern for any new feature (model → repository → domain service → API route → shared contract → frontend client → callback/page), and apply `@require_write_access` to any new write endpoint.
- For any tab/feature where the old app has little or no real behavior to port, treat that as a scope question for the user via `AskUserQuestion` rather than silently inventing or silently faithfully-porting a stub.

## Migration history (condensed)

The original 7-phase migration plan (skeleton → layering → repositories/services → API endpoints → frontend → deployment boundaries → test coverage) is complete. Sequencing was **A (auth) → C (Charts MVP) → B (ingestion) → D (remaining tabs) → E (test coverage)** — chosen over the plan's implied backend-first order so the app was demoable behind auth as early as possible, and the highest-value/hardest UI (Charts) got fast feedback before ingestion was built around a still-changing schema. All phases and slices are done; see "What's built, by area" above for current state rather than the historical slice-by-slice record.

## How to run / verify locally

```bash
# Full deployment-like stack (db -> db-migrate -> web)
docker compose up --build db db-migrate web

# Endpoints once web is up (published on host port 5001)
curl http://localhost:5001/api/health
curl http://localhost:5001/api/sites

# Auth (demo credentials in README.md)
curl -X POST http://localhost:5001/api/auth/login -H "Content-Type: application/json" \
  -d '{"email":"demo@transpower.example","password":"demo-password"}'
# Browser-facing login page (sets the session cookie, redirects to /app/ - all 7 tabs):
# http://localhost:5001/login

# Chart data (site multi-select optional - omit/empty noise_site_id for all sites;
# interval_weeks controls bucketing width, 1-4, default 2; site 115 has HistoricalResult
# data so its trace includes pre-2020 historical points spliced in automatically)
curl -X POST http://localhost:5001/api/charts -H "Content-Type: application/json" \
  -d '{"noise_site_id":[51],"condition":"all","parameter":"tone_100hz","interval_weeks":2}'

# Conductor/treatment/grease filters + days-since-conductoring mode (requires one of
# these filters, otherwise returns an empty chart with an explanatory title)
curl -X POST http://localhost:5001/api/charts -H "Content-Type: application/json" \
  -d '{"noise_site_id":[51],"conductor_and_treatment":["Standard conductor (standard grease)"],"plot_by":"days_since_conductoring"}'

# Raw per-reading table backing the Charts tab's collapsible table
curl -X POST http://localhost:5001/api/charts/table -H "Content-Type: application/json" -d '{"noise_site_id":[51]}'

# Trends tab: conductor summary box plot / rain-rate-vs-level scatter
curl -X POST http://localhost:5001/api/trends/conductor-summary -H "Content-Type: application/json" \
  -d '{"metric":"l90","detection_logic":"original","measurement_duration_minutes":15}'
curl -X POST http://localhost:5001/api/trends/rain-rate-vs-level -H "Content-Type: application/json" \
  -d '{"metric":"l90","detection_logic":"original","include_dry":false}'

# Site detail (incl. latitude/longitude) and update (requires write_access=True - demo user has it)
curl http://localhost:5001/api/sites/detail
curl -b /tmp/cookies.txt -X PATCH http://localhost:5001/api/sites/51 \
  -H "Content-Type: application/json" -d '{"site_code":"NEW","plot_color":"#aabbcc","latitude":-40.35,"longitude":175.61}'

# Outages / Reconductoring / Historical (same shape, full add/edit/delete, requires write_access)
curl http://localhost:5001/api/outages
curl -b /tmp/cookies.txt -X POST http://localhost:5001/api/outages -H "Content-Type: application/json" \
  -d '{"noise_site_id":51,"outage_type":"monitoring","start_datetime":"2025-01-01T00:00:00","end_datetime":"2025-01-01T01:00:00"}'

# Ingestion (opt-in, needs real NW_USERNAME/NW_PASSWORD - never run automatically):
NW_USERNAME=... NW_PASSWORD=... docker compose --profile ingestion run --rm ingest

# Backend tests - no local venv/poetry available, run inside a throwaway container.
# Delete any stale local dev sqlite file first if a migration added columns
# (data/transpower_conductor_noise_tool_2026.db) - db.create_all() won't ALTER it:
docker run --rm -v "$(pwd):/app" -w /app python:3.11-slim \
  bash -c "pip install -e . pytest && python -m pytest tests/ -v"

# If verifying a schema change and you need the NEW columns' seeded values (not just
# NULLs on already-seeded rows), wipe the disposable dev volume first:
docker compose down -v
docker compose up --build db db-migrate web
```

Compose services: `db` (MySQL 8, healthcheck-gated), `db-migrate` (one-shot: `alembic upgrade head` then seed CLI, must exit 0), `web` (gunicorn, depends on db healthy + db-migrate completed), `nginx` (optional, profile `prodlike`).

## How to run against the external MySQL fork (real production-shaped data)

Points the app at a real forked copy of the old app's live database (real sites/readings/outages/reconductoring/historical data) instead of the local demo stack. Requires a local, gitignored `.env` at the repo root (`DATABASE_URL`/`NW_USERNAME`/`NW_PASSWORD`/`NW_BASE_URL`/`INGEST_SITE_IDS` — ask if it needs recreating) and `ca-certificate.crt` at the repo root.

```bash
# Bring up just web against the external DB (no local db/db-migrate containers)
docker compose -f docker-compose.yml -f docker-compose.external-test.yml up --build web
# -> http://localhost:5001/app/ ; log in as external-test@transpower.example / ExtTest2026Pass
# (the 3 real accounts in that DB's user table can't log in - incompatible old password hashes)

# Real NW API ingestion test, scoped to specific sites via INGEST_SITE_IDS in .env
# (optional - omit/empty to run unscoped against every locally-known, non-IGNORE_SITES site)
docker compose -f docker-compose.yml -f docker-compose.external-test.yml --profile ingestion run --rm ingest

# One-off data scripts against the fork (see "Repo layout" above for what each does).
# create_external_test_user.py / backfill_site_coordinates.py / backfill_reconductoring_grease_and_treatment.py /
# backfill_updated_2026_processed_readings.py / generate_conductor_summary.py / generate_rain_rate_fits.py all reuse
# the app's own repositories (ORM-based) and support --dry-run. import_leq_rmse_from_sqlite.py is Core/bulk-SQL
# instead, not repository-based, because of the row counts involved (millions, not thousands) - see "Known gotchas".
set -a; source .env; set +a
python scripts/create_external_test_user.py --email you@example.com --password <pw> [--write-access]
python scripts/backfill_site_coordinates.py --dry-run   # then without --dry-run to apply; safe/idempotent to re-run as data/site_locations.csv grows
python scripts/generate_conductor_summary.py --dry-run  # re-run any time processed_reading changes materially
python scripts/generate_rain_rate_fits.py --dry-run      # re-run any time processed_reading changes materially

# Tear down when done
docker compose -f docker-compose.yml -f docker-compose.external-test.yml down
```

**Fork schema is fully in sync through migration `0013`** — every column/table this repo's migrations have added is applied there too, via direct SQL (never this repo's own Alembic — see "Known gotchas" for why), run by you:
```sql
ALTER TABLE reading ADD COLUMN measurement_duration_minutes INT NOT NULL DEFAULT 15;
ALTER TABLE processed_reading ADD COLUMN measurement_duration_minutes INT NOT NULL DEFAULT 15;
ALTER TABLE processed_reading ADD COLUMN detection_logic VARCHAR(20) NOT NULL DEFAULT 'original';
ALTER TABLE reading ADD COLUMN leq_rmse DECIMAL(5,2) NULL;
ALTER TABLE processed_reading ADD COLUMN leq_rmse DECIMAL(5,2) NULL;
CREATE TABLE conductor_summary ( ... );  -- full DDL: alembic/versions/0012_create_conductor_summary.py
ALTER TABLE conductor_summary
    ADD COLUMN measurement_duration_minutes INT NOT NULL DEFAULT 15 AFTER detection_logic,
    DROP PRIMARY KEY,
    ADD PRIMARY KEY (noise_site_id, detection_logic, measurement_duration_minutes);

-- migration 0014, already applied to the fork (full DDL: alembic/versions/0014_create_rain_rate_fit.py):
CREATE TABLE rain_rate_fit (
    noise_site_id INT NOT NULL,
    detection_logic VARCHAR(20) NOT NULL,
    metric VARCHAR(20) NOT NULL,
    slope DECIMAL(10,4) NOT NULL,
    intercept DECIMAL(10,4) NOT NULL,
    r_squared DECIMAL(5,4) NULL,
    sample_count INT NOT NULL,
    computed_at DATETIME NOT NULL,
    PRIMARY KEY (noise_site_id, detection_logic, metric),
    CONSTRAINT fk_rain_rate_fit_site FOREIGN KEY (noise_site_id)
        REFERENCES site (noise_site_id) ON UPDATE CASCADE ON DELETE CASCADE
);
-- after creating the table, populate it: python scripts/generate_rain_rate_fits.py --dry-run, then for real

-- migration 0015, NOT YET applied to the fork (full DDL: alembic/versions/0015_add_processed_reading_site_datetime_index.py):
CREATE INDEX ix_processed_reading_site_datetime ON processed_reading (noise_site_id, datetime);

-- migration 0016, NOT YET applied to the fork (full DDL: alembic/versions/0016_add_site_is_ignored.py):
ALTER TABLE site ADD COLUMN is_ignored TINYINT(1) NOT NULL DEFAULT 0;
```
If a future migration adds another column/table, add its equivalent statement here and run it the same way (single multi-clause `ALTER TABLE` for any PK change — see "Known gotchas").

**Real data on the fork, not just schema**: `reading.leq_rmse` has ~1.64M real values (of ~2.38M rows), loaded via `scripts/import_leq_rmse_from_sqlite.py`. `scripts/backfill_updated_2026_processed_readings.py` has regenerated all sites' `updated_2026` rows (137,044 total, most with a real `leq_rmse` copied through). `scripts/generate_conductor_summary.py` has populated `conductor_summary` (54 rows). `scripts/generate_rain_rate_fits.py` has populated `rain_rate_fit` (162 rows — 60 sites × both detection_logics × 3 metrics, run 2026-08-03). Re-running any of these is only needed if the underlying source data changes again — each is safe/idempotent to re-run (see each script's own `--dry-run` output before doing so).

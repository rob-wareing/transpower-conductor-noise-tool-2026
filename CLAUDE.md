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
    api/            # Flask blueprint(s) + routes; auth_guard.py (require_write_access decorator); processed_reading_routes.py (PATCH is_wet/include); trends_routes.py (POST /api/trends/conductor-summary, /rain-rate-vs-level, /age-effects); site_climate_routes.py (GET /api/sites/<id>/wind-rose, /monthly-rainfall)
    domain/         # site_service.py, auth_service.py, chart_service.py (fully feature-complete vs. the old app - outage exclusion, bucketing, historical overlay (opt-in via ChartFilters.show_historical), conductor/treatment/grease filtering, days-since-conductoring mode, raw table rows), processing_service.py (pure Reading -> ProcessedReading pandas transform, "original" detection logic, real leq_rmse calculation from Leq900 data), processing_service_updated_2026.py ("Updated 2026" detection logic - new filter rules, run alongside the original), historical_service.py, processed_reading_service.py, site_climate_service.py (thin wind-rose/monthly-rainfall lookups for the Locations tab), trends_service.py (get_rain_rate_vs_level, get_conductor_summary, and get_age_effects are all real; compute_rain_rate_fits and compute_conductor_age_fits are the pure log-fit functions behind rain_rate_fit/conductor_age_fit)
    ingestion/      # nw_client.py (Noise and Weather API connector), ingestion_job.py (orchestrator), ingest_cli.py (entrypoint)
    persistence/
      models/       # SQLAlchemy ORM models: Site (incl. is_ignored - excluded from queries/display everywhere except the Sites management tab), User, ProcessedReading (incl. reconductoring_age), Reading, Outage, OutageType, Reconductoring, HistoricalResult, ConductorSummary, RainRateFit, WindRose, MonthlyRainfall, ConductorAgeFit
      repositories/ # repository-pattern data access - one per model, plus find_by_id/save/add/delete method shapes as each tab needed them; conductor_summary_repository.py, rain_rate_fit_repository.py, wind_rose_repository.py, monthly_rainfall_repository.py, and conductor_age_fit_repository.py are all delete-all-then-bulk-insert only (replace_all - the whole table is always fully regenerated, never patched incrementally); processed_reading_repository.py's list_readings uses a per-site window-function cap (per_site_limit, default 3,000 - see "Known gotchas" for why a flat LIMIT is wrong here) plus recalculate_reconductoring_ages (bulk, chunked); reading_repository.py has aggregate_wind_rose/aggregate_monthly_rainfall (set-based SQL GROUP BY, not pandas - reading is ~2.4M rows); reconductoring_repository.py has latest_by_site() (global, not scoped - see "Known gotchas")
      seed.py       # CSV-based demo data seeding
      seed_cli.py   # entrypoint used by db-migrate container
    app.py          # Flask app factory
    config.py       # Settings incl. AUTO_INIT_DB / AUTO_SEED_DATA / SECRET_KEY / SESSION_COOKIE_SECURE / *_FIXTURE_PATH / NW_* flags; SQLALCHEMY_ENGINE_OPTIONS (pool_pre_ping, pool_recycle=280 - added after the OOM incident, see "Current status")
    extensions.py   # db = SQLAlchemy(); also enables SQLite FK enforcement (off by default in SQLite, on in the real MySQL deployment)
  frontend/
    app.py          # Dash app factory (create_dashboard) + plain /login, /logout routes + dcc.Location auth gate + dbc.Tabs(Charts, Sites, Outages, Reconductoring, Historical, Trends, Locations) - all 7 old-app tabs; explicit assets_folder= (Dash's default inference would otherwise resolve to backend/assets, not frontend/assets); header is title (H1.display-6, "Conductor Noise Tool") + right-aligned username/Log-out block
    client.py       # BackendClient - HTTP wrapper the frontend uses instead of ORM
    assets/
      app_styles.css  # ported from the old app's application/static/css/app_styles.css - table/card styling, zebra stripes, editable-cell highlight CSS, fixed column widths, Dash auto-loads this via assets_folder
    callbacks/      # sites.py (incl. is_ignored 0/1 editable column), outages.py, reconductoring.py, historical.py (add/edit/delete via diff-against-server-truth on Save; all four also have a CSV export callback via dcc.Download, same in-memory pattern as Charts - no on-disk files); charts.py (conductor/grease option population, chart refresh incl. show_historical switch, raw-table refresh/save/PATCH gated on the table collapse being open, CSV export via dcc.Download); locations.py (builds the Scattermapbox figure client-side from GET /api/sites/detail; two more independent callbacks build a go.Barpolar wind rose and a go.Bar monthly-rainfall chart off the same map-click clickData); trends.py (all 3 sub-tabs - Conductor summary, Rain rate vs level, Age effects - each refresh a server-built figure via their own POST /api/trends/... route, same server-builds-the-figure pattern as Charts)
    layout/         # sites.py (incl. is_ignored column), outages.py (dropdown-backed outage_type), reconductoring.py, historical.py, locations.py (dcc.Graph map + click-to-inspect info div + wind-rose/monthly-rainfall dcc.Graphs), trends.py (3 real sub-tabs: Rain rate vs level, Age effects, Conductor summary - no placeholders left); charts.py (site+date range / condition+parameter+aggregation+duration / conductor+grease / detection-logic+plot-by+show-historical filter rows, collapsible raw-data table, two dcc.Download components); table_styles.py (shared EDITABLE_CELL_HIGHLIGHT style_data_conditional) - every tab's buttons use dbc.Button with the old app's role-based color convention (secondary/success/primary); dbc.Switch is the pattern for new boolean toggles (show_historical) vs. the older dcc.Dropdown[True/False] pattern (include_dry) - both exist, no need to retrofit
  shared/
    contracts.py    # Pydantic DTOs - Site* (incl. is_ignored), ChartFilters (incl. show_historical)/ChartsResponse/ChartTableRow/ChartTableResponse, ConductorSummaryFilters, RainRateVsLevelFilters, AgeEffectsFilters, WindRoseSector, MonthlyRainfall, UserSummary, Outage*, Reconductoring*, HistoricalResult*, ProcessedReadingUpdate
alembic/
  env.py            # wired to real SQLAlchemy metadata, online mode works
  versions/         # 0001-0007: create site/user/processed_reading/reading/outage/reconductoring/historical_result tables
                     # 0008: site.latitude/longitude  |  0009: measurement_duration_minutes on reading+processed_reading
                     # 0010: processed_reading.detection_logic + reading.leq_rmse  |  0011: processed_reading.leq_rmse
                     # 0012: create conductor_summary table  |  0013: conductor_summary gains measurement_duration_minutes in its key
                     # 0014: create rain_rate_fit table (precomputed per-site/detection_logic/metric logarithmic best-fit)
                     # 0015: composite index on processed_reading(noise_site_id, datetime)  |  0016: site.is_ignored
                     # 0017: create wind_rose table  |  0018: create monthly_rainfall table
                     # 0019: processed_reading.reconductoring_age  |  0020: create conductor_age_fit table
                     # Every migration here mirrors the previous table's shape closely - see whichever's most similar before writing a new one from scratch.
tests/
  test_health.py, test_sites.py, test_auth.py, test_charts.py, test_site_updates.py, test_outages.py,
  test_reconductoring.py, test_historical.py, test_site_climate.py  # full-Flask-app API-level tests
  test_processing_service.py, test_processing_service_updated_2026.py, test_nw_client.py  # pure-function / mocked-HTTP tests, no Flask app needed
  test_ingestion_job.py, test_trends.py              # full-Flask-app tests for ingestion and the Trends API routes (incl. age-effects)
  test_processed_reading_repository.py, test_conductor_summary_repository.py, test_rain_rate_fit_repository.py,
  test_wind_rose_repository.py, test_monthly_rainfall_repository.py, test_conductor_age_fit_repository.py,
  test_reconductoring_repository.py, test_reading_repository_aggregation.py  # repository-level tests
  test_trends_service.py                             # trends_service.py pure-function tests (fake repositories, no DB)
  dash_callback_utils.py       # shared harness for driving Dash callbacks via /_dash-update-component in tests (no browser)
  test_charts_callbacks.py, test_sites_callbacks.py, test_outages_callbacks.py, test_reconductoring_callbacks.py,
  test_historical_callbacks.py, test_locations_callbacks.py, test_trends_callbacks.py  # Dash-callback tests, all 7 tabs
docker-compose.yml   # db, db-migrate, web, ingest (profile: ingestion), optional nginx (profile: prodlike) - LOCAL DEV ONLY
docker-compose.external-test.yml  # gitignored, local-only - points web/ingest at an external MySQL fork via -f
docker-compose.prod.yml  # PRODUCTION: db-migrate/web/ingest pointed at DATABASE_URL from .env (the managed MySQL DB, no local `db` service); web's mem_limit/healthcheck added post-incident (see "Current status") - see DEPLOY.md
.env.example         # placeholder env var reference for both local dev and DEPLOY.md's production setup - copy to .env and fill in real values (.env itself is gitignored)
DEPLOY.md             # step-by-step Digital Ocean Droplet (Ubuntu 24.04) production setup guide: server prep, TLS via host nginx+certbot, docker-compose.prod.yml, daily cron jobs (ingest, conductor-summary, rain-rate-fits, reconductoring-age, conductor-age-fits), weekly cron jobs (wind-rose, monthly-rainfall), the memory/OOM watchdog (9b), manual triage runbook
cron/
  run.sh                # flock-guarded logging wrapper shared by every cron job above
  watchdog.sh            # 5-minutely memory/OOM early-warning check, logs to /var/log/conductor-noise/watchdog.log - see DEPLOY.md "9b"
scripts/
  create_external_test_user.py                    # one-off: add a login-capable user to whatever DATABASE_URL points at
  backfill_reconductoring_grease_and_treatment.py  # one-off: backfill reconductoring.grease/conductor_and_treatment from a CSV (--dry-run)
  backfill_site_coordinates.py                     # repeatable: backfill site.latitude/longitude from data/site_locations.csv, matched by noise_site_id (--dry-run)
  backfill_updated_2026_processed_readings.py      # re-run the "Updated 2026" detection logic over each site's raw Reading history (--dry-run, --force; auto-regenerates sites whose rows predate real leq_rmse data)
  import_leq_rmse_from_sqlite.py                   # bulk-load real leq_rmse values from a local SQLite export into reading.leq_rmse (temp-table + set-based UPDATE, not per-row; --dry-run)
  generate_conductor_summary.py                    # repeatable: fully regenerates the conductor_summary table from current processed_reading data (--dry-run)
  generate_rain_rate_fits.py                       # repeatable: fully regenerates the rain_rate_fit table (per site/detection_logic/metric logarithmic best-fit) from current processed_reading data (--dry-run)
  generate_wind_rose.py                            # repeatable: fully regenerates the wind_rose table (per site x 16 compass sector) from current reading data via a set-based SQL GROUP BY, not pandas (--dry-run); cron-scheduled weekly, see DEPLOY.md
  generate_monthly_rainfall.py                     # repeatable: fully regenerates the monthly_rainfall table (per site x calendar month, climatological) from current reading data via a set-based SQL GROUP BY, not pandas (--dry-run); cron-scheduled weekly, see DEPLOY.md
  calculate_reconductoring_age.py                  # repeatable: recalculates processed_reading.reconductoring_age from each site's most recent reconductoring event, a bulk UPDATE not a materialized table (--dry-run); cron-scheduled daily, see DEPLOY.md
  generate_conductor_age_fits.py                   # repeatable: fully regenerates the conductor_age_fit table (per site/detection_logic/metric logarithmic best-fit vs. reconductoring_age) from current processed_reading data (--dry-run); cron-scheduled daily, see DEPLOY.md
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

## Current status (as of 2026-08-05)

The migration is functionally complete: all 7 of the old app's tabs exist and are feature-complete (no placeholders left, including Age effects), real ingestion has been verified against the live NW API and a real forked production database, the app is deployed and running on a real Digital Ocean Droplet (not just planned - see "Production incident" below), and 292 automated tests pass (194 backend, 98 frontend-callback).

### Production incident and stabilization (2026-08-03/04)

The Droplet went down shortly after going live: the Charts tab's default (no-filter) page load issued an unbounded `SELECT * FROM processed_reading` (260k+ rows) via `chart_service._fetch_filtered_readings_dataframe`, materialized twice (once for the line chart, once for the raw table) into pandas on every page view. The Droplet has only 1.9GB RAM, no swap, and the `web` container had no memory limit - so this reliably exhausted host RAM and let the kernel OOM-killer take out unrelated host processes (sshd, the VS Code Remote-SSH session), not just the app. Fixed in two rounds:

1. **Immediate stabilization**: added 2GB swap; added `mem_limit`/`healthcheck` to `docker-compose.prod.yml`'s `web` service (a runaway worker now gets killed by Docker's cgroup instead of the kernel picking off host processes); added a hard flat row cap to `ProcessedReadingRepository.list_readings`; added `cron/watchdog.sh` for early memory/OOM warning.
2. **Follow-up correctness fix**: the flat cap from round 1 turned out to silently drop every site whose id sorted past the cap (`ORDER BY noise_site_id, datetime LIMIT N` always returns a *prefix of sites*, not a fair sample) - most sites vanished from the default Charts view. Replaced with a **per-site window-function cap** (`per_site_limit`, default 3,000/site via `ROW_NUMBER() OVER (PARTITION BY noise_site_id ORDER BY datetime DESC)`) so every site keeps its own most-recent rows regardless of total volume. Also added: `site.is_ignored` (lets specific sites be excluded from every query/display path except the Sites tab itself, which still needs to show them to allow un-ignoring); a default `datetime > 2020-01-01` floor applied at the chart-query layer only (not baked into `ChartFilters`, to avoid silently truncating the pre-2020 `HistoricalResult` overlay - see the `show_historical` note in the Charts tab section below); `SQLALCHEMY_ENGINE_OPTIONS` (`pool_pre_ping`, `pool_recycle=280`) for connection resilience against the managed MySQL instance; a composite `(noise_site_id, datetime)` index.

Net effect: the same default page load that used to crash the whole Droplet now completes in a few seconds at ~250-265MB, verified live against production. See "Known gotchas" for the per-site-cap and stale-local-SQLite-file details, and "Outstanding issues" for what's still open (the Droplet's dev/prod dual-use, the `-1`/"Millcreek South" duplicate-site data-quality oddity, the watchdog cron entry itself).

### What's built, by area

**Auth** — Flask session-based login (`werkzeug.security` hashing, not the old app's hand-rolled cookie scheme). `write_access` enforced **server-side** on every write endpoint via `@require_write_access` — a real security fix over the old app, whose gating was client-side only.

**Charts tab** — fully feature-complete vs. the old app: per-site line chart + data-availability timeline, weekly-aggregation bucketing, historical-data overlay (splices in `HistoricalResult` up to each site's survey cutover date, gated behind the "Show historical" switch (`ChartFilters.show_historical`, default `False` — the overlay is opt-in, not shown by default)), conductor/treatment/grease filters, days-since-conductoring plot mode, `append_outages()` window exclusion, collapsible editable raw-data table (`is_wet`/`include`), in-memory CSV export (`dcc.Download`, no on-disk files — the old app's download mechanism had a confirmed path-mismatch bug). `measurement_duration_minutes` (1 or 15 min) and `detection_logic` (`original`/`updated_2026`) filters are both wired to real filtering.

**Sites / Outages / Reconductoring / Historical tabs** — Sites is edit-only (matches the old app; no add/delete flow, new sites only arrive via `data/site.csv`). Outages/Reconductoring/Historical are genuinely add/edit/delete-capable via per-row REST endpoints, with the **frontend** diffing the submitted table against server state to decide what to call (a deliberate divergence from the old app's single generic bulk-sync callback). All 5 tabs with tabular data have in-memory CSV export.

**Locations tab** — real per-site map (`Site.latitude`/`longitude`), built from `GET /api/sites/detail`; a deliberate improvement over the old app's 5-hardcoded-dummy-point stub. Read-only, no write callback (matches old app). Clicking a site marker also populates a wind rose (`go.Barpolar`, 16 compass sectors) and a climatological average-monthly-rainfall bar chart, both read from the raw `reading` table via two materialized tables (`wind_rose`, `monthly_rainfall`) precomputed by `scripts/generate_wind_rose.py`/`generate_monthly_rainfall.py` (set-based SQL `GROUP BY` via `ReadingRepository.aggregate_wind_rose`/`aggregate_monthly_rainfall`, not pandas — `reading` is ~2.4M rows, too large to pull wholesale) and regenerated weekly via cron (`DEPLOY.md` "Weekly derived-table regeneration"). Sentinel/invalid raw values (`wind_speed >= 200`, `rain_mm >= 99` — reading's ingestion-time cap-invalid convention, see `processing_service.MAX_VALID_WIND_SPEED`/`MAX_VALID_RAIN_FALL`) are excluded from both aggregations.

**Ingestion + processing** — `NoiseAndWeatherClient` → `processing_service.py` (pure pandas transform) → `ingestion_job.py::collect_new_readings` (orchestrator). Two detection-logic pipelines run side by side per ingested reading, each writing its own tagged `ProcessedReading` rows (never blended): `original` (the initial port) and `updated_2026` (`processing_service_updated_2026.py` — 22:00–05:00 window, `wind < 1.5`, current-period-only `is_wet`, no Leq−L90 filter, a valid-sensor-data check, an `leq_rmse` threshold check). `leq_rmse` is a real calculation (`processing_service.calculate_leq_rmse`): an OLS straight-line fit against the NW API's `Leq900` 1-second-per-period field, RMSE of the residuals, `NULL` if `Leq900` is missing or <50% populated. Historical `reading.leq_rmse` values (predating this calculation) were separately backfilled from an external SQLite export.

**Trends tab** — 3 sub-tabs:
- **Conductor summary** — real, populated. A materialized `conductor_summary` table (one row per site × detection_logic × measurement_duration_minutes, regenerated from `processed_reading` by `scripts/generate_conductor_summary.py`) displayed as a single horizontal box plot, one box per site, coloured by each site's *current* conductor type (from `reconductoring`'s most recent event per site, limited to Zebra/Goat/Curlew/Sulphur/Pheasant/Chukar with an "Unknown" fallback for no-match/no-event sites). Filters: metric, detection_logic, measurement_duration_minutes, site multi-select.
- **Rain rate vs level** — real, populated. Scatter of the selected metric against `rain1`, one coloured trace per site, reading raw `processed_reading` rows directly (no materialized table). Filters: detection_logic, metric, site multi-select (default all), "Include dry" toggle (default `False` — dry/`is_wet=0` points excluded by default). Each site with a stored `rain_rate_fit` row also gets a dashed logarithmic best-fit line (`metric = slope*ln(rain1) + intercept`) in the same colour as that site's markers — the fit itself is **precomputed** (`trends_service.compute_rain_rate_fits` + `scripts/generate_rain_rate_fits.py`, one row per site × detection_logic × metric in the `rain_rate_fit` table, fit over wet/included/`rain1>0` rows, skipped if <3 qualifying points) and only looked up at request time, never refit per chart request/filter change.
- **Age effects** — real, populated. Scatter of the selected metric against `processed_reading.reconductoring_age` (days since each site's most recent reconductoring event - see `scripts/calculate_reconductoring_age.py`/`ProcessedReadingRepository.recalculate_reconductoring_ages`, NULL for rows that predate a site's current conductor or for sites with no reconductoring history, and such rows are excluded from the chart entirely, not just from the fit), one coloured trace per site, reading raw `processed_reading` rows directly (no materialized table for the scatter itself). Filters: detection_logic, metric, site multi-select (default all) - same structure as Rain rate vs level, minus its "Include dry" toggle (not relevant here). Each site with a stored `conductor_age_fit` row also gets a dashed logarithmic best-fit line (`metric = slope*ln(reconductoring_age) + intercept`), same colour as that site's markers - precomputed (`trends_service.compute_conductor_age_fits` + `scripts/generate_conductor_age_fits.py`, one row per site × detection_logic × metric, fit over included rows with `reconductoring_age > 0` - log undefined at 0 - skipped if <3 qualifying points) and only looked up at request time, mirroring Rain rate vs level's own fit-lookup pattern exactly.

**Production database (the same "external MySQL fork" used for pre-launch testing)** — the managed MySQL instance the live Droplet's `docker-compose.prod.yml` points `DATABASE_URL` at is the same real forked production database referenced elsewhere in this file as "the external fork" — it was used for pre-launch testing and then became production for real once the Droplet went live, they are not two different databases. Schema is fully in sync through migration `0020` (every column/table applied there via direct `ALTER TABLE`/`CREATE TABLE`, run by you — see "How to run against the external fork" for why, and "Production incident" above for why several of 0015-0020 exist). Real data loaded/computed there: ~1.64M real `leq_rmse` values, a 137,044-row `updated_2026` backfill, a 54-row `conductor_summary`, a 162-row `rain_rate_fit`, a 260,281-row `processed_reading.reconductoring_age` recalculation (184,002 aged, 76,279 NULL), a 153-row `conductor_age_fit`, a 464-row `wind_rose`, and a 297-row `monthly_rainfall` (all generated 2026-08-03 through 2026-08-05 via the matching `scripts/generate_*.py`/`calculate_*.py`).

**Tests** — 292 passing: 194 backend (full-Flask-app tests, pure-function tests, a mocked-HTTP-boundary test, repository-level tests), 98 Dash-callback tests (all 7 tabs, via `tests/dash_callback_utils.py` driving the real `/app/_dash-update-component` endpoint — Dash callbacks are closures with no importable name, so this is the only way to exercise the actual registered callback rather than a hand-copied stand-in).

**Production deployment** — `DEPLOY.md` is a full step-by-step guide for a Digital Ocean Droplet (Ubuntu 24.04): host setup (ufw, Docker, nginx, certbot), `docker-compose.prod.yml` (points `db-migrate`/`web`/`ingest` at the existing managed MySQL DB via `DATABASE_URL` in `.env` — no local `db` container in prod), TLS via host nginx + Let's Encrypt (not a dockerized nginx — simpler cert renewal via certbot's own systemd timer), daily cron jobs (`ingest` → `generate_conductor_summary.py` → `generate_rain_rate_fits.py` → `calculate_reconductoring_age.py` → `generate_conductor_age_fits.py`, staggered 2:00am-3:05am) and weekly cron jobs (`generate_wind_rose.py`, `generate_monthly_rainfall.py`, Sunday 3:30/3:45am), all wrapped in the shared `cron/run.sh` `flock`-guarded logging script, plus `cron/watchdog.sh` (memory/OOM early warning, "9b"). **Actually provisioned and running** — this is the same Droplet the "Production incident" section above describes; it has survived a real OOM crash + fix cycle and is currently serving real traffic. The watchdog cron entry and the swap file were added by hand during the incident and aren't yet reflected as a fresh-Droplet setup step in `DEPLOY.md`'s main flow — see "Outstanding issues".

### Outstanding issues
- **The Droplet is dual-use (production host + interactive dev box)** — VS Code Remote-SSH + Claude Code CLI processes were observed consuming ~1.3GB+ of the Droplet's 1.9GB total RAM during the incident, directly reducing the headroom that would otherwise have absorbed the app's memory spike. Flagged to the user as a longer-term recommendation (a separate dev Droplet) but not acted on — still true today.
- **The watchdog cron entry (`cron/watchdog.sh`, DEPLOY.md "9b") and the 2GB swap file were added by hand mid-incident**, not via a repeatable setup step — `DEPLOY.md`'s main flow should be updated so a *fresh* Droplet setup provisions both from the start, rather than only documenting them as something added after a crash.
- **`site.is_ignored` is currently set on 4 real sites** (179, 203, 205, and `-1`) by the user directly against production, flagged during the incident as sites that "should not be called or displayed." Not further investigated *why* each was flagged — treat as intentional unless told otherwise.
- **`noise_site_id = -1` ("Transpower - Millcreek South") is a likely data-quality duplicate** of real sites 205/209 (both also named "Transpower - Millcreek South") — noticed during the incident investigation, not root-caused or fixed. It's one of the 4 currently-ignored sites above, which papers over the symptom without explaining it.
- **`ProcessedReadingRepository.list_readings`'s `per_site_limit` (default 3,000/site) is a safety cap, not a considered per-tab UX decision** — every consumer (Charts, Trends/Rain-rate-vs-level, Trends/Age-effects) now silently truncates to each site's 3,000 most-recent qualifying rows once a site has more history than that. Works fine today; revisit the constant (or make it per-endpoint-configurable) if a site's real history grows enough that 3,000 rows starts feeling short for trend analysis.
- **Locations tab** — `go.Scattermapbox` is deprecated by the installed Plotly version (cosmetic warning only); a swap to `go.Scattermap` hasn't been done.
- **Site coordinates on the fork** — 29 of 35 real sites have real `latitude`/`longitude` (backfilled 2026-08-03 from `data/site_locations.csv` via `scripts/backfill_site_coordinates.py`). 6 real sites still have no entry in `data/site_locations.csv` and remain uncoordinated; add them there and re-run the script (safe/idempotent) as more real coordinates become available.
- **No scheduling for the `ingest` service locally** — `docker-compose.yml` (local dev) only supports a manually-triggered one-shot, matching the old app. `DEPLOY.md`'s production Droplet setup has real cron scheduling for everything (see "Production deployment" above) — but that's Droplet-only, not something a local `docker compose up` gets.
- **Ingestion doesn't auto-create `Site` rows** for sites the NW API knows about but the local DB doesn't (deliberately not ported — the old app's field mapping for this was never confirmed, so it was skipped rather than guessed). Any real site must exist in `data/site.csv`/the `site` table first.
- **The 2 wind-rose/rainfall memory-optimization ideas flagged but not implemented**: (1) deduplicating the Charts tab's figures+table double-fetch (each is an independent HTTP request/pipeline run today, gated only by the table-collapse-open check — a genuine server-side fetch merge would need a request-scoped cache or a combined endpoint); (2) ORM column-trimming via `load_only`/`with_entities` on `list_readings` — investigated and deliberately skipped because the method is shared by callers with different column needs (the offline `generate_conductor_summary.py`/backfill scripts read columns the interactive paths don't), and trimming risked silently reintroducing per-row lazy-load queries there.

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
- **Auto-mode's write-action classifier reliably blocks raw schema-mutating SQL against the production/fork DB** (an inline `ALTER TABLE`/`CREATE TABLE` via `docker exec ... python -c "...execute(text('ALTER TABLE ...'))"`) **every time**, across many repeated attempts this session — this is not "unpredictable" in practice, treat it as a hard rule. It does **not** block data-writing script invocations (`docker compose run --rm db-migrate python scripts/generate_*.py`, even without `--dry-run`) or read-only queries (`SELECT`/`SHOW` via the same `python -c` pattern) — only DDL. Standing workflow for any new migration: show the user the exact `ALTER`/`CREATE TABLE` (already logged in "How to run against the external fork" below), then either they run it or they explicitly authorize you to via `AskUserQuestion` — don't just retry the blocked command.
- **A flat `LIMIT` after `ORDER BY noise_site_id, datetime` on a shared, multi-site table always returns a *prefix of sites by id*, not a fair sample** — the first fix for the OOM incident (a plain row cap) silently made every site past the cap vanish from the default Charts view entirely. Any cap on a per-site multi-tenant table needs to be a **per-site** cap (window function: `ROW_NUMBER() OVER (PARTITION BY site_id ORDER BY datetime DESC) <= N`, see `processed_reading_repository.py`), not a flat one.
- **A repository method that aggregates "globally" (not scoped to a specific site/filter) will pick up the demo seed's own baseline rows even in a test that only inserts data for other sites** — hit writing `ReconductoringRepository.latest_by_site()` tests: it has no site filter by design (callers need every site's cutoff at once), so a test using sites 51/115 collided with `AUTO_SEED_DATA`'s 2 baseline `reconductoring` rows for those exact sites. Fix: either pick sites with no baseline data (e.g. 137/142 — see `data/reconductoring.csv` for which 2 sites *do* have seeded rows) or assert on specific dict keys (`cutoffs[SITE_A] == ...`) instead of comparing the whole returned dict/list.
- **`reading.wind_speed`/`reading.rain_mm` carry a handful of ingestion-time invalid-value sentinels** (`wind_speed = 999.9`, `rain_mm = 99.9` — see `processing_service.MAX_VALID_WIND_SPEED`/`MAX_VALID_RAIN_FALL`, the values used to cap-and-keep rather than reject a bad reading) **plus the occasional real sensor glitch just under that cap** (one row at `wind_speed = 244.7`, confirmed live). Any new aggregation over raw `reading` data needs its own plausibility filter (see `ReadingRepository.MAX_PLAUSIBLE_WIND_SPEED`/`MAX_PLAUSIBLE_RAIN_MM`, both stricter than the ingestion-time caps) — don't assume `NOT NULL` alone is a clean filter.
- **Cross-dialect (SQLite test / MySQL prod) aggregation math must use SQLAlchemy Core expressions, not raw SQL strings** — `sa.extract("month", ...)`, `sa.func.floor(...)`, and the plain `%` modulo operator all compile correctly on both backends; a raw `MONTH(...)`/`DATEDIFF(...)` string only works on MySQL and silently has no SQLite equivalent. See `ReadingRepository.aggregate_wind_rose`/`aggregate_monthly_rainfall`'s 16-sector bucketing (`floor((direction + 11.25) / 22.5) % 16`) for a worked example, including its boundary-angle test coverage.
- **A default value silently applied to a *shared* filter field can break an unrelated feature that reads the same field** — when defaulting `ChartFilters.start_date` to `2020-01-01` for the OOM fix, the naive approach (bake the default into the Pydantic model) would have also silently truncated `_historical_dataframe`'s pre-2020 `HistoricalResult` overlay, since that function reads `filters.start_date` too. Fixed by applying the default at the query-construction call site only (`chart_service.py`), leaving the shared filter object itself untouched. Check every *other* reader of a field before defaulting it, not just the one you're fixing.
- **A chunked bulk `UPDATE` over ~260k rows via SQLAlchemy Core executemany against the managed MySQL instance took longer than a single foreground command's timeout** (`ProcessedReadingRepository.recalculate_reconductoring_ages`, run via `scripts/calculate_reconductoring_age.py`) — ran to completion fine, just needed backgrounding (`run_in_background`) rather than assuming a bulk op at this scale finishes within a couple of minutes.
- Dev environment quirks (Windows host, Git Bash tool): prefix any `docker run`/`docker compose` command containing a bind-mount path with `MSYS_NO_PATHCONV=1` (Git Bash mangles POSIX paths otherwise); `/tmp` is not reliably writable/readable from this Bash tool — use the session's scratchpad directory instead.
- **A bare `__pycache__/` line in `.dockerignore` does NOT reliably exclude nested `__pycache__` dirs at every depth** (confirmed by building `docker/Dockerfile.migrate` after adding `COPY scripts /app/scripts` — `scripts/__pycache__/*.pyc` still landed in the image). Use `**/__pycache__/` instead. `.gitignore`'s bare `__pycache__/` is unaffected (git's own matching does apply at any depth) — this is a Docker-build-context-specific gotcha, not a general one.
- **The local dev SQLite fallback file (`data/transpower_conductor_noise_tool_2026.db`) goes stale every time a migration adds a column and gets hit repeatedly** — `test_health.py::test_health_endpoint` (the only test that calls bare `create_app()` with no `DATABASE_URL` override) fails with `no such column` against this file after nearly every schema change this session. Reflex fix, every time: `rm -f data/transpower_conductor_noise_tool_2026.db` before re-running the suite — this is the same underlying issue as the `db.create_all()`-never-ALTERs gotcha above, just worth calling out how often it actually recurs in practice.

## Key decisions already made (don't relitigate without reason)
- Keep the original `transpower-conductor-noise-tool` untouched as a reference copy — never import from it.
- Modular-monolith-to-two-apps migration, not a microservices split.
- Frontend/backend separation is the primary boundary; don't split ingestion/API/persistence into separate deployables yet.
- Preserve current user-facing behavior first, refine internals second.
- Shared DTOs live inside this repo (`shared/contracts.py`), not a separate installable package.
- Frontend calls backend via a thin client wrapper (`frontend/client.py`), not raw HTTP calls scattered through callbacks.
- Follow the layered vertical-slice pattern for any new feature (model → repository → domain service → API route → shared contract → frontend client → callback/page), and apply `@require_write_access` to any new write endpoint.
- For any tab/feature where the old app has little or no real behavior to port, treat that as a scope question for the user via `AskUserQuestion` rather than silently inventing or silently faithfully-porting a stub.
- Every precomputed/materialized derived table (`conductor_summary`, `rain_rate_fit`, `wind_rose`, `monthly_rainfall`, `conductor_age_fit`) is fully **delete-then-bulk-insert** (`replace_all`) on every regeneration run, never incrementally patched — a stale combination that no longer has matching source data is naturally dropped, not left behind with garbage stats.
- **Aggregation over a large source table (`reading`, ~2.4M rows) is done in SQL (Core `GROUP BY`/window functions), not pulled into pandas** — the pandas-in-Python approach used for `conductor_summary`/`rain_rate_fit` (source: `processed_reading`, ~260k rows) doesn't scale to `reading`'s size; `wind_rose`/`monthly_rainfall` generation only ever pulls back the small, already-aggregated result. Follow this precedent (Core aggregation, not ORM-objects-into-pandas) for any future table whose source is `reading` rather than `processed_reading`.
- New boolean toggle UI controls use `dbc.Switch` (e.g. Charts' "Show historical") rather than the older `dcc.Dropdown([True, False])` pattern (Trends' "Include dry") — both exist in the codebase, no need to retrofit the older ones to match.

## Migration history (condensed)

The original 7-phase migration plan (skeleton → layering → repositories/services → API endpoints → frontend → deployment boundaries → test coverage) is complete. Sequencing was **A (auth) → C (Charts MVP) → B (ingestion) → D (remaining tabs) → E (test coverage)** — chosen over the plan's implied backend-first order so the app was demoable behind auth as early as possible, and the highest-value/hardest UI (Charts) got fast feedback before ingestion was built around a still-changing schema. All phases and slices are done; see "What's built, by area" above for current state rather than the historical slice-by-slice record.

Post-migration, the app went live on a real Digital Ocean Droplet, hit a production OOM incident within its first day, and was stabilized — see "Production incident and stabilization" under "Current status" above, and "Outstanding issues" for what that incident left unresolved. Three further features shipped after the migration was "complete": Locations-tab wind rose/monthly-rainfall charts, the Charts-tab `show_historical` toggle, and the Trends/Age-effects sub-tab — all documented under "What's built, by area."

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

# Chart data (site multi-select optional - omit/empty noise_site_id for all
# non-ignored sites; interval_weeks controls bucketing width, 1-4, default 2;
# show_historical defaults to False - omit it and site 115's real pre-2020
# HistoricalResult points will NOT appear, even though the data exists)
curl -X POST http://localhost:5001/api/charts -H "Content-Type: application/json" \
  -d '{"noise_site_id":[51],"condition":"all","parameter":"tone_100hz","interval_weeks":2}'

# Same request with the historical overlay switched on
curl -X POST http://localhost:5001/api/charts -H "Content-Type: application/json" \
  -d '{"noise_site_id":[115],"show_historical":true}'

# Conductor/treatment/grease filters + days-since-conductoring mode (requires one of
# these filters, otherwise returns an empty chart with an explanatory title)
curl -X POST http://localhost:5001/api/charts -H "Content-Type: application/json" \
  -d '{"noise_site_id":[51],"conductor_and_treatment":["Standard conductor (standard grease)"],"plot_by":"days_since_conductoring"}'

# Raw per-reading table backing the Charts tab's collapsible table
curl -X POST http://localhost:5001/api/charts/table -H "Content-Type: application/json" -d '{"noise_site_id":[51]}'

# Trends tab: conductor summary box plot / rain-rate-vs-level scatter / age-effects scatter
curl -X POST http://localhost:5001/api/trends/conductor-summary -H "Content-Type: application/json" \
  -d '{"metric":"l90","detection_logic":"original","measurement_duration_minutes":15}'
curl -X POST http://localhost:5001/api/trends/rain-rate-vs-level -H "Content-Type: application/json" \
  -d '{"metric":"l90","detection_logic":"original","include_dry":false}'
curl -X POST http://localhost:5001/api/trends/age-effects -H "Content-Type: application/json" \
  -d '{"metric":"l90","detection_logic":"original"}'

# Locations tab: per-site wind rose / climatological monthly rainfall (empty items,
# not a 404, for a site with no precomputed rows yet)
curl http://localhost:5001/api/sites/115/wind-rose
curl http://localhost:5001/api/sites/115/monthly-rainfall

# Site detail (incl. latitude/longitude, is_ignored) and update (requires write_access=True - demo user has it)
curl http://localhost:5001/api/sites/detail                    # excludes is_ignored sites by default
curl http://localhost:5001/api/sites/detail?include_ignored=true
curl -b /tmp/cookies.txt -X PATCH http://localhost:5001/api/sites/51 \
  -H "Content-Type: application/json" -d '{"site_code":"NEW","plot_color":"#aabbcc","latitude":-40.35,"longitude":175.61,"is_ignored":false}'

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
# backfill_updated_2026_processed_readings.py / generate_conductor_summary.py / generate_rain_rate_fits.py /
# calculate_reconductoring_age.py / generate_conductor_age_fits.py all reuse the app's own repositories (ORM-based)
# and support --dry-run. generate_wind_rose.py / generate_monthly_rainfall.py also support --dry-run but read
# `reading` via set-based SQL Core (not the ORM/pandas pattern the others use - reading is too large, ~2.4M rows).
# import_leq_rmse_from_sqlite.py is Core/bulk-SQL too, for the same row-count reason - see "Known gotchas".
set -a; source .env; set +a
python scripts/create_external_test_user.py --email you@example.com --password <pw> [--write-access]
python scripts/backfill_site_coordinates.py --dry-run   # then without --dry-run to apply; safe/idempotent to re-run as data/site_locations.csv grows
python scripts/generate_conductor_summary.py --dry-run  # re-run any time processed_reading changes materially
python scripts/generate_rain_rate_fits.py --dry-run      # re-run any time processed_reading changes materially
python scripts/generate_wind_rose.py --dry-run           # re-run any time reading changes materially (weekly via cron in prod)
python scripts/generate_monthly_rainfall.py --dry-run    # re-run any time reading changes materially (weekly via cron in prod)
python scripts/calculate_reconductoring_age.py --dry-run # re-run whenever processed_reading or reconductoring changes (daily via cron in prod) - MUST run before generate_conductor_age_fits.py
python scripts/generate_conductor_age_fits.py --dry-run  # re-run any time reconductoring_age changes materially (daily via cron in prod)

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

-- migration 0017, NOT YET applied to the fork (full DDL: alembic/versions/0017_create_wind_rose.py):
CREATE TABLE wind_rose (
    noise_site_id INT NOT NULL,
    direction_sector VARCHAR(3) NOT NULL,
    sample_count INT NOT NULL,
    avg_wind_speed DECIMAL(4,1) NOT NULL,
    computed_at DATETIME NOT NULL,
    PRIMARY KEY (noise_site_id, direction_sector),
    CONSTRAINT fk_wind_rose_site FOREIGN KEY (noise_site_id)
        REFERENCES site (noise_site_id) ON UPDATE CASCADE ON DELETE CASCADE
);
-- after creating the table, populate it: python scripts/generate_wind_rose.py --dry-run, then for real

-- migration 0018, NOT YET applied to the fork (full DDL: alembic/versions/0018_create_monthly_rainfall.py):
CREATE TABLE monthly_rainfall (
    noise_site_id INT NOT NULL,
    month INT NOT NULL,
    avg_rain_mm DECIMAL(4,2) NOT NULL,
    sample_count INT NOT NULL,
    computed_at DATETIME NOT NULL,
    PRIMARY KEY (noise_site_id, month),
    CONSTRAINT fk_monthly_rainfall_site FOREIGN KEY (noise_site_id)
        REFERENCES site (noise_site_id) ON UPDATE CASCADE ON DELETE CASCADE
);
-- after creating the table, populate it: python scripts/generate_monthly_rainfall.py --dry-run, then for real

-- migration 0019, NOT YET applied to the fork (full DDL: alembic/versions/0019_add_processed_reading_reconductoring_age.py):
ALTER TABLE processed_reading ADD COLUMN reconductoring_age INT NULL;
-- after adding the column, populate it: python scripts/calculate_reconductoring_age.py

-- migration 0020, NOT YET applied to the fork (full DDL: alembic/versions/0020_create_conductor_age_fit.py):
CREATE TABLE conductor_age_fit (
    noise_site_id INT NOT NULL,
    detection_logic VARCHAR(20) NOT NULL,
    metric VARCHAR(20) NOT NULL,
    slope DECIMAL(10,4) NOT NULL,
    intercept DECIMAL(10,4) NOT NULL,
    r_squared DECIMAL(5,4) NULL,
    sample_count INT NOT NULL,
    computed_at DATETIME NOT NULL,
    PRIMARY KEY (noise_site_id, detection_logic, metric),
    CONSTRAINT fk_conductor_age_fit_site FOREIGN KEY (noise_site_id)
        REFERENCES site (noise_site_id) ON UPDATE CASCADE ON DELETE CASCADE
);
-- after creating the table (and after reconductoring_age is populated), run: python scripts/generate_conductor_age_fits.py --dry-run, then for real
```
If a future migration adds another column/table, add its equivalent statement here and run it the same way (single multi-clause `ALTER TABLE` for any PK change — see "Known gotchas").

**Real data on the fork, not just schema**: `reading.leq_rmse` has ~1.64M real values (of ~2.38M rows), loaded via `scripts/import_leq_rmse_from_sqlite.py`. `scripts/backfill_updated_2026_processed_readings.py` has regenerated all sites' `updated_2026` rows (137,044 total). Every `generate_*.py`/`calculate_*.py` script listed above has been run for real at least once — see "Production database" under "Current status" for current row counts (`conductor_summary`, `rain_rate_fit`, `wind_rose`, `monthly_rainfall`, `conductor_age_fit`, `processed_reading.reconductoring_age`). Re-running any of these is only needed if the underlying source data changes again — each is safe/idempotent to re-run (see each script's own `--dry-run` output before doing so).

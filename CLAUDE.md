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
    api/            # Flask blueprint(s) + routes; auth_guard.py (require_write_access decorator); processed_reading_routes.py (PATCH is_wet/include); trends_routes.py (POST /api/trends/conductor-summary, /rain-rate-vs-level, /age-effects); site_climate_routes.py (GET /api/sites/<id>/wind-rose, /monthly-rainfall, /monthly-weather-stats - all 3 accept optional ?start=YYYY-MM&end=YYYY-MM month+year-only range params, parsed by _parse_year_month and silently ignored if malformed rather than 400ing, since this is a frontend-controlled internal API; plus GET /api/sites/<id>/summary, added 2026-08-24, bundling reconductoring events/outages/availability range/detected-event counts for the Locations tab in one round trip); reconductoring_routes.py also serves GET /api/reconductoring/grease-descriptions; chart_routes.py's GET /api/charts/timeline takes no request body/params at all - deliberately decoupled from POST /api/charts, which no longer returns a timeline_chart key
    domain/         # site_service.py, auth_service.py, chart_service.py (fully feature-complete vs. the old app - outage exclusion, bucketing, historical overlay (opt-in via ChartFilters.show_historical), conductor/treatment/grease filtering, days-since-conductoring mode, raw table rows; as of 2026-08-24, a site's historical segment renders as its own go.Scatter trace - reduced opacity (HISTORICAL_OPACITY=0.5), color = site.historical_line_color or that site's own SITE_COLOR_PALETTE color, sharing a legendgroup with its current-data sibling trace so they toggle together in the legend - and a site's trace further splits wherever reconductoring.plot_linestyle changes, via the shared _contiguous_runs(df, columns) helper - see "What's built, by area" and "Known gotchas"), processing_service.py (pure Reading -> ProcessedReading pandas transform, "original" detection logic, real leq_rmse calculation from Leq900 data), processing_service_updated_2026.py ("Updated 2026" detection logic - new filter rules, run alongside the original), historical_service.py, processed_reading_service.py, site_climate_service.py (get_wind_rose/get_monthly_rainfall re-aggregate a date-scoped set of (site, year, month) precomputed rows down to the chart's final shape in Python - summing sample_count/total_rain, weighting avg_wind_speed/avg_rain_mm by each bucket's own sample_count - never touching raw reading directly; get_monthly_weather_stats is a straight range-filtered read, already at the right granularity; get_site_summary bundles reconductoring events + outages + availability range + detected-event counts for one site, backing the Locations tab), trends_service.py (get_rain_rate_vs_level, get_conductor_summary, and get_age_effects are all real; compute_rain_rate_fits and compute_conductor_age_fits are the pure log-fit functions behind rain_rate_fit/conductor_age_fit)
    ingestion/      # nw_client.py (Noise and Weather API connector), ingestion_job.py (orchestrator), ingest_cli.py (entrypoint)
    persistence/
      models/       # SQLAlchemy ORM models: Site (incl. is_ignored - excluded from queries/display everywhere except the Sites management tab; historical_line_color, added 2026-08-24 - optional hex override for a site's historical-segment chart color, same shape/validator as the pre-existing plot_color, which stays vestigial/unread by chart_service.py), User, ProcessedReading (incl. reconductoring_age), Reading, ReadingAvailability (per-site full-history min/max/count, backs the Data Availability Timeline and the Locations tab's per-site summary), Outage, OutageType, Reconductoring (incl. for_reconductoring_age - defaults True, excludes a treatment-only event from the age-cutoff calculation when flagged False; plot_linestyle - now exposed/editable as of 2026-08-24, see "What's built, by area"), GreaseDescription (grease code -> human description, e.g. "C1.5" -> "1 layer of Al greased"), HistoricalResult, ConductorSummary, RainRateFit, WindRose (now (site, year, month, direction_sector), not full-history-collapsed), MonthlyRainfall (now (site, year, month), not climatological), MonthlyWeatherStats (new 2026-08-24 - per (site, year, month) min/max/avg rain_mm and wind_speed, backs the Weather tab's date-range stats chart), ConductorAgeFit
      repositories/ # repository-pattern data access - one per model, plus find_by_id/save/add/delete method shapes as each tab needed them; conductor_summary_repository.py, rain_rate_fit_repository.py, wind_rose_repository.py, monthly_rainfall_repository.py, monthly_weather_stats_repository.py, conductor_age_fit_repository.py, and reading_availability_repository.py are all delete-all-then-bulk-insert only (replace_all - the whole table is always fully regenerated, never patched incrementally); wind_rose/monthly_rainfall/monthly_weather_stats repositories additionally support an optional start_year_month/end_year_month range filter (packed YYYYMM ints, so SQLite's lack of row-value/tuple comparison support isn't a problem) - see site_climate_service.py; processed_reading_repository.py's list_readings uses a per-site window-function cap (per_site_limit, default 3,000 via Settings.PER_SITE_READING_LIMIT - env-tunable, see "Known gotchas" for why a flat LIMIT is wrong here) plus recalculate_reconductoring_ages (bulk, chunked) plus aggregate_availability (set-based SQL GROUP BY over processed_reading's *full* history, unbounded by per_site_limit - backs reading_availability) plus count_by_detection_logic (per-site {"original": N, "updated_2026": M} counts, backs the Locations tab's detected-event-count summary); reading_repository.py has aggregate_wind_rose/aggregate_monthly_rainfall/aggregate_monthly_weather_stats (set-based SQL GROUP BY, not pandas - reading is ~2.4M rows; all three now group by (site, year, month) rather than collapsing across years); reconductoring_repository.py has latest_by_site() (global, not scoped - see "Known gotchas" - and now filters out rows not flagged for_reconductoring_age) and list_events()/OutageRepository.list_outages() both now accept an optional noise_site_id filter (used by the Locations tab's per-site summary, added default-None so every pre-existing unfiltered caller is unaffected); grease_description_repository.py is a plain hand-maintained lookup (list_all/add_all), not derived/regenerated like the replace_all tables above
      seed.py       # CSV-based demo data seeding
      seed_cli.py   # entrypoint used by db-migrate container
    app.py          # Flask app factory
    config.py       # Settings incl. AUTO_INIT_DB / AUTO_SEED_DATA / SECRET_KEY / SESSION_COOKIE_SECURE / *_FIXTURE_PATH / NW_* flags; SQLALCHEMY_ENGINE_OPTIONS (pool_pre_ping, pool_recycle=280 - added after the OOM incident, see "Current status"); PER_SITE_READING_LIMIT (default 3000, env-tunable, ProcessedReadingRepository's own fallback default - no current caller relies on it); CHARTS_PER_SITE_LIMIT (default 100000, env-tunable, passed explicitly by chart_service.py); TRENDS_PER_SITE_LIMIT (default 100000, env-tunable, passed explicitly by trends_service.py's get_rain_rate_vs_level/get_age_effects - see "Outstanding issues" for the Age-effects truncation bug this fixed)
    extensions.py   # db = SQLAlchemy(); also enables SQLite FK enforcement (off by default in SQLite, on in the real MySQL deployment)
  frontend/
    app.py          # Dash app factory (create_dashboard) + plain /login, /logout routes + dcc.Location auth gate + dbc.Tabs(Charts, Sites, Outages, Reconductoring, Historical, Trends, Locations, Weather, Help) - the 7 old-app tabs plus two new tabs with no old-app equivalent (Help: static; Weather: dropdown-driven wind rose/monthly rainfall, see "What's built, by area"); explicit assets_folder= (Dash's default inference would otherwise resolve to backend/assets, not frontend/assets); header is title (H1.display-6, "Conductor Noise Tool") + right-aligned username/Log-out block
    client.py       # BackendClient - HTTP wrapper the frontend uses instead of ORM
    assets/
      app_styles.css  # ported from the old app's application/static/css/app_styles.css - table/card styling, zebra stripes, editable-cell highlight CSS, fixed column widths, Dash auto-loads this via assets_folder
    callbacks/      # sites.py (incl. is_ignored 0/1 editable column, plus historical_line_color as of 2026-08-24 - plain optional-string field, no special handling needed), outages.py, reconductoring.py (incl. for_reconductoring_age 0/1 editable column - handled separately from the other editable fields' generic "row.get(field) or None" treatment, since that would wrongly null out a False/0 value and break the blank-new-row check, see CORE_EDITABLE_FIELDS; plot_linestyle added to CORE_EDITABLE_FIELDS 2026-08-24 - a plain optional string, unlike for_reconductoring_age it needs no special handling), historical.py (add/edit/delete via diff-against-server-truth on Save; all four also have a CSV export callback via dcc.Download, same in-memory pattern as Charts - no on-disk files); charts.py (conductor/grease option population - both share one chart-reconductoring-events-store dcc.Store populated once per page load instead of each independently calling client.get_reconductoring_events(), noise-chart refresh incl. show_historical switch (refresh_charts, one Output now, not two), a *separate* refresh_chart_timeline callback for the Data Availability Timeline whose only Input is chart-init.n_intervals - deliberately not wired to any filter, bulk_select_sites (Output chart-site-select.value, uses dash.ctx.triggered_id to distinguish its two button Inputs - "Select all" sets every current option's value, "Clear" empties it; prevent_initial_call=True so it never overrides manual per-site clicks in the dropdown itself), raw-table refresh/save/PATCH gated on the table collapse being open, CSV export via dcc.Download); locations.py (builds the Scattermapbox figure client-side from GET /api/sites/detail; as of 2026-08-24 the wind-rose/monthly-rainfall charts have moved to the Weather tab - clicking a site marker now populates a site-activity panel instead (display_site_activity, GET /api/sites/<id>/summary via client.get_site_summary) showing reconductoring events, outages, data-availability range, and original/updated_2026 detected-event counts as plain HTML tables/text, built by _build_site_activity_panel; _build_wind_rose_figure/_build_monthly_rainfall_figure/_empty_figure/DIRECTION_SECTORS/MONTH_LABELS all still live here, since weather.py imports the three functions from this module rather than duplicating them); weather.py (populate_weather_site_options mirrors charts.py's populate_site_options; as of 2026-08-24 gained a month+year start/end date range (4 dropdowns) passed through to client.get_wind_rose/get_monthly_rainfall's new optional start/end kwargs, plus a 2-chart date-range stats callback (update_weather_range_stats, one callback with two Outputs to avoid a duplicate backend fetch) built from client.get_monthly_weather_stats - rainfall and wind-speed are two separate charts, not one dual-axis chart, per this app's own no-dual-axis convention; still imports and reuses locations.py's _build_wind_rose_figure/_build_monthly_rainfall_figure/_empty_figure directly); trends.py (all 3 sub-tabs - Conductor summary, Rain rate vs level, Age effects - each refresh a server-built figure via their own POST /api/trends/... route, same server-builds-the-figure pattern as Charts; Rain rate vs level and Age effects each also have a "Hide data" button that toggles marker-trace visibility client-side on the already-fetched figure, no new backend call)
    layout/         # sites.py (incl. is_ignored column, plus historical_line_color as of 2026-08-24), outages.py (dropdown-backed outage_type), reconductoring.py (incl. for_reconductoring_age column, plus plot_linestyle/"Line style" as of 2026-08-24), historical.py, locations.py (dcc.Graph map + click-to-inspect info div + a site-activity-panel div, as of 2026-08-24 - the wind-rose/monthly-rainfall dcc.Graphs that used to sit here moved to the Weather tab), weather.py (a single-select Sites dcc.Dropdown, a start/end month+year date-range picker (4 dcc.Dropdowns, plain Month+Year - no DatePickerRange, which has no month-only mode; MONTH_OPTIONS duplicated here rather than imported from callbacks.locations to keep layout modules independent of the callbacks layer), and 4 dcc.Graphs: wind rose, monthly rainfall, and (new 2026-08-24) a monthly-rainfall-range and a monthly-windspeed-range stats chart), trends.py (3 real sub-tabs: Rain rate vs level, Age effects, Conductor summary - no placeholders left), help.py (static end-user help text, 4 subheadings, no callbacks); charts.py (two-column filter area, changed 2026-08-23: left column stacks date-range / condition+parameter / aggregation+duration / conductor-and-treatment / grease / detection-logic+plot-by+show-historical rows - condition+parameter and aggregation+duration were originally one combined row, and conductor-and-treatment and grease were originally one combined row, until both got split across two rows each the same day to stop overflowing into the widened Sites box (see "Known gotchas" for the flexWrap fix that goes with this); right column is a dbc.Card "Sites" box (minWidth 600px/maxWidth 650px/minHeight 500px as of 2026-08-23 - tuned several times that day, starting from an initial 260-320px that was too narrow; the outer two-column row *and* every inner filter row now have flexWrap: "wrap" so nothing forces horizontal overflow/an overlap with a narrower left column) with the multi-select site dropdown - given className="chart-site-select-wide" so app_styles.css can force its selected-site chips to flex-wrap onto the same row instead of stacking one-per-row (targets the classic-react-select `.Select-multi-value-wrapper`/`.Select-value` classes dcc.Dropdown still renders under the hood) - plus "Select all"/"Clear" buttons for one-click bulk selection instead of clicking each site individually; collapsible raw-data table, two dcc.Download components, chart-reconductoring-events-store dcc.Store); table_styles.py (shared EDITABLE_CELL_HIGHLIGHT style_data_conditional); table_columns_config.py (VISIBLE_COLUMNS - per-tab column-visibility config for Sites/Outages/Reconductoring/Historical, pre-populated all-visible, consumed via visible_column_defs() in each of those four layout files' content() - display-only, does NOT affect CSV export, see that file's own comment) - every tab's buttons use dbc.Button with the old app's role-based color convention (secondary/success/primary); dbc.Switch is the pattern for new boolean toggles (show_historical) vs. the older dcc.Dropdown[True/False] pattern (include_dry) - both exist, no need to retrofit
  shared/
    contracts.py    # Pydantic DTOs - Site* (incl. is_ignored, historical_line_color), ChartFilters (incl. show_historical)/ChartsResponse/ChartTableRow/ChartTableResponse, ConductorSummaryFilters, RainRateVsLevelFilters, AgeEffectsFilters, WindRoseSector, MonthlyRainfall, MonthlyWeatherStats, SiteActivitySummary (new 2026-08-24, backs GET /api/sites/<id>/summary), GreaseDescription, UserSummary, Outage*, Reconductoring* (incl. plot_linestyle), HistoricalResult*, ProcessedReadingUpdate
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
                     # 0021: create grease_description table (grease code -> human description lookup for the Charts tab's Grease dropdown)
                     # 0022: monthly_rainfall.total_rain (cumulative rain per site/month, alongside the existing avg_rain_mm)
                     # 0023: reconductoring.for_reconductoring_age (excludes treatment-only events from the age-cutoff calculation)
                     # 0024: create reading_availability table (precomputed per-site full-history min/max/count, backs the Data Availability Timeline, fully decoupled from Charts tab filters)
                     # 0025: wind_rose gains year/month, PK widens to (site, year, month, direction_sector) - was full-history-collapsed, now date-range-queryable
                     # 0026: monthly_rainfall gains year, PK widens to (site, year, month) - was climatological (years collapsed), now date-range-queryable
                     # 0027: create monthly_weather_stats table (per (site, year, month) min/max/avg rain_mm and wind_speed, backs the Weather tab's date-range stats chart)
                     # 0028: site.historical_line_color (optional hex override for a site's historical-segment chart color)
                     # Every migration here mirrors the previous table's shape closely - see whichever's most similar before writing a new one from scratch.
tests/
  test_health.py, test_sites.py, test_auth.py, test_charts.py, test_site_updates.py, test_outages.py,
  test_reconductoring.py, test_historical.py, test_site_climate.py  # full-Flask-app API-level tests - test_site_climate.py
    # now also covers start/end range params and GET /api/sites/<id>/monthly-weather-stats
  test_processing_service.py, test_processing_service_updated_2026.py, test_nw_client.py  # pure-function / mocked-HTTP tests, no Flask app needed
  test_ingestion_job.py, test_trends.py              # full-Flask-app tests for ingestion and the Trends API routes (incl. age-effects)
  test_processed_reading_repository.py, test_conductor_summary_repository.py, test_rain_rate_fit_repository.py,
  test_wind_rose_repository.py, test_monthly_rainfall_repository.py, test_monthly_weather_stats_repository.py,
  test_conductor_age_fit_repository.py, test_outage_repository.py,
  test_reconductoring_repository.py, test_reading_repository_aggregation.py, test_grease_description_repository.py,
  test_reading_availability_repository.py  # repository-level tests
  test_site_climate_service.py  # site_climate_service.py's date-range re-aggregation math (weighted avg, sum) and get_site_summary - fake DB, no HTTP
  test_table_columns_config.py  # frontend/layout/table_columns_config.py's visible_column_defs() - no Flask app needed
  test_trends_service.py                             # trends_service.py pure-function tests (fake repositories, no DB)
  dash_callback_utils.py       # shared harness for driving Dash callbacks via /_dash-update-component in tests (no browser)
  test_charts_callbacks.py, test_sites_callbacks.py, test_outages_callbacks.py, test_reconductoring_callbacks.py,
  test_historical_callbacks.py, test_locations_callbacks.py, test_trends_callbacks.py  # Dash-callback tests, all 7 old-app tabs -
    # test_locations_callbacks.py now covers display_site_activity instead of the old wind-rose/rainfall callbacks
  test_weather_callbacks.py  # Dash-callback tests for the Weather tab, incl. the date-range Inputs and the 2-chart range-stats callback
  test_help_layout.py  # static-layout test - the Help tab has no callbacks, so this just asserts on content()'s rendered repr()
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
  generate_wind_rose.py                            # repeatable: fully regenerates the wind_rose table (per site x year x month x 16 compass sector, since migration 0025) from current reading data via a set-based SQL GROUP BY, not pandas (--dry-run); cron-scheduled weekly, see DEPLOY.md
  generate_monthly_rainfall.py                     # repeatable: fully regenerates the monthly_rainfall table (per site x year x calendar month, since migration 0026 - no longer climatological/years-collapsed) from current reading data via a set-based SQL GROUP BY, not pandas (--dry-run); cron-scheduled weekly, see DEPLOY.md
  generate_monthly_weather_stats.py                # repeatable: fully regenerates the monthly_weather_stats table (per site x year x month, min/max/avg rain_mm and wind_speed) from current reading data via a set-based SQL GROUP BY, not pandas (--dry-run); cron-scheduled weekly, see DEPLOY.md
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
data/grease_description.csv   # small hand-maintained lookup (3 rows: C1/C1.5/C2 -> human description), seeded like any other fixture, edited by hand when a new grease code appears
data/historical_result.csv    # 154 rows ported from the old repo's real data, filtered to the sites in this repo's trimmed data/site.csv
data/site_locations.csv       # real, manually-curated site coordinates ("Site ID,lon,lat" - a different shape from site.csv, which carries no coordinate columns), growing over time; source of truth for scripts/backfill_site_coordinates.py
```
Local-only, gitignored files used for testing against the external MySQL fork: `.env` (`DATABASE_URL`/`NW_USERNAME`/`NW_PASSWORD`/`NW_BASE_URL`/`INGEST_SITE_IDS`), `docker-compose.external-test.yml`, `ca-certificate.crt` (TLS CA cert). See "How to run against the external MySQL fork" below.

Also machine-local, entirely outside this repo (one level up, provided by you): `../local_data/db_3.sqlite` (14GB, `noise_weather_exported` table) — the real RMSE data source for `scripts/import_leq_rmse_from_sqlite.py`. `../local_data/example_leq900.txt` — a real example of the NW API's `Leq900` field, used to confirm the parsing format for `processing_service.calculate_leq_rmse`.

## Current status (as of 2026-08-05)

The migration is functionally complete: all 7 of the old app's tabs exist and are feature-complete (no placeholders left, including Age effects), real ingestion has been verified against the live NW API and a real forked production database, the app is deployed and running on a real Digital Ocean Droplet (not just planned - see "Production incident" below), and 376 automated tests pass (240 backend, 127 frontend-callback, 9 static-layout).

### Production incident and stabilization (2026-08-03/04)

The Droplet went down shortly after going live: the Charts tab's default (no-filter) page load issued an unbounded `SELECT * FROM processed_reading` (260k+ rows) via `chart_service._fetch_filtered_readings_dataframe`, materialized twice (once for the line chart, once for the raw table) into pandas on every page view. The Droplet has only 1.9GB RAM, no swap, and the `web` container had no memory limit - so this reliably exhausted host RAM and let the kernel OOM-killer take out unrelated host processes (sshd, the VS Code Remote-SSH session), not just the app. Fixed in two rounds:

1. **Immediate stabilization**: added 2GB swap; added `mem_limit`/`healthcheck` to `docker-compose.prod.yml`'s `web` service (a runaway worker now gets killed by Docker's cgroup instead of the kernel picking off host processes); added a hard flat row cap to `ProcessedReadingRepository.list_readings`; added `cron/watchdog.sh` for early memory/OOM warning.
2. **Follow-up correctness fix**: the flat cap from round 1 turned out to silently drop every site whose id sorted past the cap (`ORDER BY noise_site_id, datetime LIMIT N` always returns a *prefix of sites*, not a fair sample) - most sites vanished from the default Charts view. Replaced with a **per-site window-function cap** (`per_site_limit`, default 3,000/site via `ROW_NUMBER() OVER (PARTITION BY noise_site_id ORDER BY datetime DESC)`) so every site keeps its own most-recent rows regardless of total volume. Also added: `site.is_ignored` (lets specific sites be excluded from every query/display path except the Sites tab itself, which still needs to show them to allow un-ignoring); a default `datetime > 2020-01-01` floor applied at the chart-query layer only (not baked into `ChartFilters`, to avoid silently truncating the pre-2020 `HistoricalResult` overlay - see the `show_historical` note in the Charts tab section below); `SQLALCHEMY_ENGINE_OPTIONS` (`pool_pre_ping`, `pool_recycle=280`) for connection resilience against the managed MySQL instance; a composite `(noise_site_id, datetime)` index.

Net effect: the same default page load that used to crash the whole Droplet now completes in a few seconds at ~250-265MB, verified live against production. See "Known gotchas" for the per-site-cap and stale-local-SQLite-file details, and "Outstanding issues" for what's still open (the Droplet's dev/prod dual-use, the `-1`/"Millcreek South" duplicate-site data-quality oddity, the watchdog cron entry itself).

### What's built, by area

**Auth** — Flask session-based login (`werkzeug.security` hashing, not the old app's hand-rolled cookie scheme). `write_access` enforced **server-side** on every write endpoint via `@require_write_access` — a real security fix over the old app, whose gating was client-side only.

**Charts tab** — fully feature-complete vs. the old app: per-site line chart + data-availability timeline, weekly-aggregation bucketing, historical-data overlay (splices in `HistoricalResult` up to each site's survey cutover date, gated behind the "Show historical" switch (`ChartFilters.show_historical`, default `False` — the overlay is opt-in, not shown by default)), conductor/treatment/grease filters, days-since-conductoring plot mode, `append_outages()` window exclusion, collapsible editable raw-data table (`is_wet`/`include`), in-memory CSV export (`dcc.Download`, no on-disk files — the old app's download mechanism had a confirmed path-mismatch bug). **As of 2026-08-24**, each site's line chart trace is drawn with an explicit color (`chart_service.SITE_COLOR_PALETTE`, matching `trends_service`'s own explicit-cycling pattern, rather than Plotly's implicit per-trace auto-coloring, which it relied on before) so a historical-segment trace can deliberately share color with its current-segment sibling. When `show_historical` is on, the historical portion of a site's line now renders as its *own* trace (opacity 0.5, color = `site.historical_line_color` if set else that site's own palette color), sharing a `legendgroup` with the current-data trace so the legend doesn't double up (only the first/earliest run shows in the legend). A site's trace further splits wherever `reconductoring.plot_linestyle` changes for it (see the Sites/Outages/Reconductoring/Historical tabs section below) - both splits go through one shared helper, `chart_service._contiguous_runs(df, columns)`, keyed on `(is_historical, linestyle)`. `measurement_duration_minutes` (1 or 15 min) and `detection_logic` (`original`/`updated_2026`) filters are both wired to real filtering. The Grease dropdown's options are labelled `"{code} - {description}"` (e.g. `"C1.5 - 1 layer of Al greased"`) by looking up each site-scoped grease code against the small `grease_description` lookup table (`GET /api/reconductoring/grease-descriptions`) — the dropdown's `value` sent in `ChartFilters.grease` is still the bare code, only the on-screen label changes; a code with no matching row (e.g. demo-seed values) falls back to the bare code as its label. The default query no longer applies a `2020-01-01` floor (removed 2026-08-21 - the old `DEFAULT_CHART_START_DATE` constant is gone entirely) - a request with no `start_date` now queries a site's *full* history, still bounded by Charts' own `Settings.CHARTS_PER_SITE_LIMIT` (default 100,000/site - much higher than Trends' 3,000/site `PER_SITE_READING_LIMIT`, see "Outstanding issues"). The conductor-treatment and grease dropdowns share one `chart-reconductoring-events-store` `dcc.Store`, populated once per page load, instead of each independently calling `GET /api/reconductoring` (previously 2 identical round trips on every default load, now 1). **The "Data Availability Timeline" is fully decoupled from every other Charts tab option** (2026-08-22) — it's its own `GET /api/charts/timeline` endpoint (no request body, no query params at all) backed by the precomputed `reading_availability` table (`chart_service.get_availability_timeline`), and its own frontend callback (`refresh_chart_timeline`, the *only* Input is `chart-init.n_intervals` — none of the filter dropdowns/date-picker/switches are wired to it). `POST /api/charts` now returns only `{"noise_chart": ...}` — the old combined `{"noise_chart", "timeline_chart"}` response shape is gone. See "Outstanding issues" for the fuller page-load performance writeup, including why this replaced the earlier (2026-08-21) decision to leave the timeline filter-coupled.

**Sites / Outages / Reconductoring / Historical tabs** — Sites is edit-only (matches the old app; no add/delete flow, new sites only arrive via `data/site.csv`). Outages/Reconductoring/Historical are genuinely add/edit/delete-capable via per-row REST endpoints, with the **frontend** diffing the submitted table against server state to decide what to call (a deliberate divergence from the old app's single generic bulk-sync callback). All 5 tabs with tabular data have in-memory CSV export. Reconductoring's table has an editable "For reconductoring age" (0/1) column backing `reconductoring.for_reconductoring_age` (migration 0023) - flag a row `0` to exclude it from `ReconductoringRepository.latest_by_site()`'s cutoff calculation without deleting the row itself (e.g. a logged event that was really just a grease/treatment change, not a genuine new conductor). **As of 2026-08-24**, Reconductoring also has an editable "Line style" column (`plot_linestyle`, free text - "dash", "dashdot", etc.) - the column already existed on the model (schema fidelity with the old app) but was never exposed; now it drives a date-cutover mechanism (not the old app's identity-keyed one) in `chart_service._stamp_conductor`: for each site, its reconductoring events with a non-null `plot_linestyle` are walked oldest-first, and every reading from that event's date onward is stamped with that style, defaulting to `"solid"` before any styled event or for a site with none. Sites gained an editable "Historical line colour" column (`historical_line_color`, optional hex) the same day - see the Charts tab section above for how it's used. Which columns each of these four tables *displays* is controlled by `frontend/layout/table_columns_config.py`'s `VISIBLE_COLUMNS` (pre-populated all-`True`) - suppress a column by flipping its entry to `False`, no layout-file changes needed; doesn't affect CSV export (still exports every field regardless).

**Help tab** — new, no old-app equivalent. Fully static (`frontend/layout/help.py::content()`, no callbacks, no backend calls, no `register_callbacks` entry needed), four subheadings: Detection Logic, Historical Data, Wind Roses, Site Location - plain-language explanations of those four features for end users, kept in sync by hand with the actual filter/toggle/chart behavior each describes (there's no automated check that the prose matches the code - if one of those four features' behavior changes, update this tab's copy too).

**Locations tab** — real per-site map (`Site.latitude`/`longitude`), built from `GET /api/sites/detail`; a deliberate improvement over the old app's 5-hardcoded-dummy-point stub. Read-only, no write callback (matches old app). **As of 2026-08-24**, the wind-rose/monthly-rainfall charts that used to live here moved to the Weather tab (see below) - clicking a site marker now populates a site-activity panel instead: reconductoring events and outages (both as plain HTML tables), the site's data-availability date range (`reading_availability`), and its detected-event counts by `detection_logic` (`original` vs `updated_2026`, `include=True` only), all fetched in one round trip via `GET /api/sites/<id>/summary` (`site_climate_service.get_site_summary`, bundling `ReconductoringRepository.list_events(noise_site_id=...)`, `OutageRepository.list_outages(noise_site_id=...)`, `ReadingAvailabilityRepository.find_by_site`, and `ProcessedReadingRepository.count_by_detection_logic`).

**Weather tab** — new, no old-app equivalent (2026-08-23; date-range + stats chart added 2026-08-24). A "Sites" `dcc.Dropdown` (single-select, `weather-site-select`) plus an optional start/end month+year date range (4 dropdowns - month-only granularity, no day picker) reproduces the wind rose (`go.Barpolar`, 16 compass sectors) and monthly-rainfall (`go.Bar`, `total_rain`) charts that used to live on Locations. Backing data is fully precomputed, never a live `reading` query: `wind_rose`/`monthly_rainfall` were widened (migrations 0025/0026) from full-history-collapsed/climatological to `(site, year, month, ...)` granularity specifically so a date range can be served by re-aggregating a small, already-precomputed rowset in Python (`site_climate_service._collapse_wind_rose`/`_collapse_monthly_rainfall` - sum `sample_count`/`total_rain`, weight `avg_wind_speed`/`avg_rain_mm` by each bucket's own `sample_count`) rather than re-querying the ~2.4M-row `reading` table per request - both tables stay weekly-cron-regenerated (`scripts/generate_wind_rose.py`/`generate_monthly_rainfall.py`, `ReadingRepository.aggregate_wind_rose`/`aggregate_monthly_rainfall`, both now grouped by `(site, year, month, ...)`). No range selected = full-history behavior, byte-for-byte the same as before the date range existed. Selecting a range also populates two new charts - "Monthly Rainfall Range" and "Monthly Wind Speed Range" (deliberately two separate charts, not one dual-axis chart - different units, per this app's own no-dual-axis convention) - each a min/max shaded band plus a mean line, from the new `monthly_weather_stats` table (migration 0027, `ReadingRepository.aggregate_monthly_weather_stats`, `scripts/generate_monthly_weather_stats.py`, weekly cron) via `GET /api/sites/<id>/monthly-weather-stats`; already at `(site, year, month)` granularity, so no re-aggregation needed, just a range-filtered read. `callbacks/weather.py` still imports `_build_wind_rose_figure`/`_build_monthly_rainfall_figure`/`_empty_figure` directly from `callbacks/locations.py` rather than duplicating them, even though the click-triggered callbacks that used to live alongside them in `locations.py` are gone.

**Ingestion + processing** — `NoiseAndWeatherClient` → `processing_service.py` (pure pandas transform) → `ingestion_job.py::collect_new_readings` (orchestrator). Two detection-logic pipelines run side by side per ingested reading, each writing its own tagged `ProcessedReading` rows (never blended): `original` (the initial port) and `updated_2026` (`processing_service_updated_2026.py` — 22:00–05:00 window, `wind < 1.5`, current-period-only `is_wet`, no Leq−L90 filter, a valid-sensor-data check, an `leq_rmse` threshold check). `leq_rmse` is a real calculation (`processing_service.calculate_leq_rmse`): an OLS straight-line fit against the NW API's `Leq900` 1-second-per-period field, RMSE of the residuals, `NULL` if `Leq900` is missing or <50% populated. Historical `reading.leq_rmse` values (predating this calculation) were separately backfilled from an external SQLite export.

**Trends tab** — 3 sub-tabs:
- **Conductor summary** — real, populated. A materialized `conductor_summary` table (one row per site × detection_logic × measurement_duration_minutes, regenerated from `processed_reading` by `scripts/generate_conductor_summary.py`) displayed as a single horizontal box plot, one box per site, coloured by each site's *current* conductor type (from `reconductoring`'s most recent event per site, limited to Zebra/Goat/Curlew/Sulphur/Pheasant/Chukar with an "Unknown" fallback for no-match/no-event sites). Filters: metric, detection_logic, measurement_duration_minutes, site multi-select.
- **Rain rate vs level** — real, populated. Scatter of the selected metric against `rain1`, one coloured trace per site, reading raw `processed_reading` rows directly (no materialized table). Filters: detection_logic, metric, site multi-select (default all), "Include dry" toggle (default `False` — dry/`is_wet=0` points excluded by default). Each site with a stored `rain_rate_fit` row also gets a dashed logarithmic best-fit line (`metric = slope*ln(rain1) + intercept`) in the same colour as that site's markers — the fit itself is **precomputed** (`trends_service.compute_rain_rate_fits` + `scripts/generate_rain_rate_fits.py`, one row per site × detection_logic × metric in the `rain_rate_fit` table, fit over wet/included/`rain1>0` rows, skipped if <3 qualifying points) and only looked up at request time, never refit per chart request/filter change. A "Hide data" `dbc.Button` (`trends-rain-rate-hide-data-button`) toggles the raw marker traces' visibility client-side only (`callbacks/trends.py::_hide_marker_traces`, matched on each trace's `mode == "markers"`/`"lines"`) - marker traces get `visible=False` (removes the points from the plot) and `showlegend=False`; each site's fit-line trace (matched by shared `legendgroup`, not touched otherwise) gets `showlegend=True` so the legend swaps from "marker colour + site" to "line colour/dash + site" instead of just going blank (a trace with `visible=False` drops out of the legend entirely, so the marker can't stay the legend representative once hidden). A site with no fit line (too few qualifying points) has no legend entry while data is hidden - nothing of its is left on the chart to label. No new backend/filter field - purely a post-processing step on the already-fetched figure JSON, so "data shown" is just the untouched original response, no reverse-transform needed. State is tracked by `n_clicks` parity (odd = hidden), not a `dcc.Store` - the button's own label flips "Hide data"/"Show data" via a second callback on the same `n_clicks` Input (an independent side effect, not an ordering dependency, so this doesn't hit the "two callbacks on one Input" gotcha).
- **Age effects** — real, populated. Scatter of the selected metric against `processed_reading.reconductoring_age` (days since each site's most recent *qualifying* reconductoring event - see `scripts/calculate_reconductoring_age.py`/`ProcessedReadingRepository.recalculate_reconductoring_ages`, NULL for rows that predate a site's current conductor or for sites with no reconductoring history, and such rows are excluded from the chart entirely, not just from the fit), one coloured trace per site, reading raw `processed_reading` rows directly (no materialized table for the scatter itself). Filters: detection_logic, metric, site multi-select (default all) - same structure as Rain rate vs level, minus its "Include dry" toggle (not relevant here). Each site with a stored `conductor_age_fit` row also gets a dashed logarithmic best-fit line (`metric = slope*ln(reconductoring_age) + intercept`), same colour as that site's markers - precomputed (`trends_service.compute_conductor_age_fits` + `scripts/generate_conductor_age_fits.py`, one row per site × detection_logic × metric, fit over included rows with `reconductoring_age > 0` - log undefined at 0 - skipped if <3 qualifying points) and only looked up at request time, mirroring Rain rate vs level's own fit-lookup pattern exactly. Has its own "Hide data" button (`trends-age-effects-hide-data-button`), same client-side-only marker-hiding mechanism as Rain rate vs level's.

**Production database (the same "external MySQL fork" used for pre-launch testing)** — the managed MySQL instance the live Droplet's `docker-compose.prod.yml` points `DATABASE_URL` at is the same real forked production database referenced elsewhere in this file as "the external fork" — it was used for pre-launch testing and then became production for real once the Droplet went live, they are not two different databases. Schema is fully in sync through migration `0028` (every column/table applied there via direct `ALTER TABLE`/`CREATE TABLE`, run by you — see "How to run against the external fork" for why, and "Production incident" above for why several of 0015-0020 exist). Real data loaded/computed there: ~1.64M real `leq_rmse` values, a 137,044-row `updated_2026` backfill, a 54-row `conductor_summary`, a 162-row `rain_rate_fit`, a `processed_reading.reconductoring_age` recalculation refreshed daily via cron (~261k rows and growing; last hand-confirmed 2026-08-22 at 261,340 rows, 184,278 aged, 77,062 NULL), a 153-row `conductor_age_fit`, a 13,291-row `wind_rose` (regenerated 2026-08-24 at its new (site, year, month, direction_sector) granularity, migration 0025 - up from 464 rows when it was full-history-collapsed), an 883-row `monthly_rainfall` (regenerated 2026-08-24 at its new (site, year, month) granularity, migration 0026 - up from 297 rows when it was climatological), an 883-row `monthly_weather_stats` (new 2026-08-24, migration 0027), a 3-row `grease_description` (C1/C1.5/C2, hand-inserted 2026-08-06), `reconductoring.for_reconductoring_age` (migration 0023 - now in real use: site 209's 2022-11-04 event (id=43) is flagged `False`, correctly excluded from `latest_by_site()`'s cutoff so its 2023-02-21 event (id=42) anchors that site's age instead - confirmed live, see "Outstanding issues"), a 29-row `reading_availability` (migration 0024, one row per real site with any processed_reading history, 25 of those visible via `GET /api/charts/timeline` after excluding the 4 already-`is_ignored` sites), and `site.historical_line_color` (migration 0028, added 2026-08-24, unset on every real site so far - no historical-segment color override in production yet, every site's historical trace currently falls back to its own current-trace color). `web` and `db-migrate` have both been rebuilt and redeployed against this schema (`docker compose -f docker-compose.prod.yml build web db-migrate && up -d web`), confirmed serving `/api/reconductoring/grease-descriptions`, `total_rain`-populated `/api/sites/<id>/monthly-rainfall`, `for_reconductoring_age`-populated `/api/reconductoring`, the fully-decoupled `/api/charts/timeline`, and (as of 2026-08-24) date-range-scoped `/api/sites/<id>/wind-rose`/`/monthly-rainfall`, `/api/sites/<id>/monthly-weather-stats`, and `/api/sites/<id>/summary` all live.

**Tests** — 376 passing: 240 backend (full-Flask-app tests, pure-function tests, a mocked-HTTP-boundary test, repository-level tests, domain-service tests), 127 Dash-callback tests (all 7 old-app tabs plus Weather, via `tests/dash_callback_utils.py` driving the real `/app/_dash-update-component` endpoint — Dash callbacks are closures with no importable name, so this is the only way to exercise the actual registered callback rather than a hand-copied stand-in), 9 static-layout tests (`test_help_layout.py`, `test_table_columns_config.py` — no Flask app/callbacks needed for either).

**Production deployment** — `DEPLOY.md` is a full step-by-step guide for a Digital Ocean Droplet (Ubuntu 24.04): host setup (ufw, Docker, nginx, certbot), `docker-compose.prod.yml` (points `db-migrate`/`web`/`ingest` at the existing managed MySQL DB via `DATABASE_URL` in `.env` — no local `db` container in prod), TLS via host nginx + Let's Encrypt (not a dockerized nginx — simpler cert renewal via certbot's own systemd timer), daily cron jobs (`ingest` → `generate_conductor_summary.py` → `generate_rain_rate_fits.py` → `calculate_reconductoring_age.py` → `generate_conductor_age_fits.py`, staggered 2:00am-3:05am) and weekly cron jobs (`generate_wind_rose.py`, `generate_monthly_rainfall.py`, `generate_monthly_weather_stats.py`, Sunday 3:30/3:45/4:00am), all wrapped in the shared `cron/run.sh` `flock`-guarded logging script, plus `cron/watchdog.sh` (memory/OOM early warning, "9b"). **Actually provisioned and running** — this is the same Droplet the "Production incident" section above describes; it has survived a real OOM crash + fix cycle and is currently serving real traffic. The watchdog cron entry and the swap file were added by hand during the incident and aren't yet reflected as a fresh-Droplet setup step in `DEPLOY.md`'s main flow — see "Outstanding issues".

### Outstanding issues
- **The Droplet is dual-use (production host + interactive dev box)** — VS Code Remote-SSH + Claude Code CLI processes were observed consuming ~1.3GB+ of the Droplet's 1.9GB total RAM during the incident, directly reducing the headroom that would otherwise have absorbed the app's memory spike. Flagged to the user as a longer-term recommendation (a separate dev Droplet) but not acted on — still true today.
- ~~The watchdog cron entry and the 2GB swap file were added by hand mid-incident, not via a repeatable setup step~~ — **resolved**: `DEPLOY.md` now has a "2a. Swap file" step (fallocate/mkswap/swapon/fstab) ahead of "9b. Memory/OOM watchdog" (which already had real setup commands), so a fresh Droplet setup provisions both from the start.
- **`site.is_ignored` is currently set on 4 real sites** (179, 203, 205, and `-1`) by the user directly against production, flagged during the incident as sites that "should not be called or displayed." Not further investigated *why* each was flagged — treat as intentional unless told otherwise.
- **`noise_site_id = -1` ("Transpower - Millcreek South") is a likely data-quality duplicate** of real sites 205/209 (both also named "Transpower - Millcreek South") — noticed during the incident investigation, not root-caused or fixed. It's one of the 4 currently-ignored sites above, which papers over the symptom without explaining it.
- **`ProcessedReadingRepository.list_readings`'s `per_site_limit` is now per-endpoint, not a single global cap** — Charts (figures + raw table, changed 2026-08-22) and Trends (Rain-rate-vs-level + Age-effects, changed 2026-08-23) each pass their own explicit cap now (`Settings.CHARTS_PER_SITE_LIMIT`/`Settings.TRENDS_PER_SITE_LIMIT`, both default 100,000/site) instead of relying on the repository's own `DEFAULT_PER_SITE_LIMIT`/`Settings.PER_SITE_READING_LIMIT` (3,000/site, now just a generic unused-in-practice fallback - see `config.py`). Both remain env-tunable without a code change (wired into `docker-compose.yml`/`docker-compose.prod.yml`'s `web` service and documented in `.env.example`) — restart `web` after changing either. Neither is a true removal of the cap, both were deliberately raised rather than suppressed outright, for the same reason: Charts is the same query path that caused the original OOM incident, and falls back on the container's `mem_limit`/watchdog as the safety net for a site whose history outgrows the cap, rather than a second hard app-level limit.
- **Bug found and fixed 2026-08-23: Age-effects was silently truncating long-history sites' visible time series to a narrow tail-end age band.** Root cause: the (then-shared) 3,000-row `per_site_limit` kept each site's 3,000 most-recent-*by-datetime* rows before Age-effects filtered to non-NULL `reconductoring_age` - fine for sites with a short conductor lifespan, but for site 209 (cutoff 2023-02-21, ~1,277 days of history by 2026-08) it meant only the most recent ~325 days of rows survived the cap, so the chart only ever showed ages ~952-1277, never the early 5-951 range, even though the *column itself* had the full range computed correctly. Confirmed via direct query before fixing (`list_readings(site_ids=[209], detection_logic="original")` returned exactly ages 952-1277) and confirmed fixed after (now returns the full 5-1277 range, 11,555 points). This is conceptually the same bug class as the original Charts per-site-cap incident (a "most recent N" truncation silently biasing what's visible) but manifesting as a truncated *value range* on one axis rather than missing *sites* - worth remembering as a pattern: any per-site row cap combined with a time-correlated x-axis can silently misrepresent the full picture, not just drop volume.
- **Locations tab** — `go.Scattermapbox` is deprecated by the installed Plotly version (cosmetic warning only); a swap to `go.Scattermap` hasn't been done.
- **Site coordinates on the fork** — 29 of 35 real sites have real `latitude`/`longitude` (backfilled 2026-08-03 from `data/site_locations.csv` via `scripts/backfill_site_coordinates.py`). 6 real sites still have no entry in `data/site_locations.csv` and remain uncoordinated; add them there and re-run the script (safe/idempotent) as more real coordinates become available.
- **No scheduling for the `ingest` service locally** — `docker-compose.yml` (local dev) only supports a manually-triggered one-shot, matching the old app. `DEPLOY.md`'s production Droplet setup has real cron scheduling for everything (see "Production deployment" above) — but that's Droplet-only, not something a local `docker compose up` gets.
- **Ingestion doesn't auto-create `Site` rows** for sites the NW API knows about but the local DB doesn't (deliberately not ported — the old app's field mapping for this was never confirmed, so it was skipped rather than guessed). Any real site must exist in `data/site.csv`/the `site` table first.
- **The 2 wind-rose/rainfall memory-optimization ideas flagged but not implemented**: (1) deduplicating the Charts tab's figures+table double-fetch (each is an independent HTTP request/pipeline run today, gated only by the table-collapse-open check — a genuine server-side fetch merge would need a request-scoped cache or a combined endpoint - **still not done**, not to be confused with the separate reconductoring-events dedup below, which *is* done); (2) ORM column-trimming via `load_only`/`with_entities` on `list_readings` — investigated and deliberately skipped because the method is shared by callers with different column needs (the offline `generate_conductor_summary.py`/backfill scripts read columns the interactive paths don't), and trimming risked silently reintroducing per-row lazy-load queries there.
- **Page-load performance investigation (2026-08-21/22)** — the Charts tab (default landing tab) fired 4 HTTP round trips on every default load; one was a genuinely redundant duplicate (`populate_conductor_treatment_options`/`populate_grease_options` each independently called `GET /api/reconductoring` for identical data) and has been fixed via `chart-reconductoring-events-store`. A second cost - the timeline chart's min/max derivation running as part of the same expensive `_fetch_filtered_readings_dataframe` pandas pipeline as the noise chart - is also now fixed, but via decoupling rather than caching: the Data Availability Timeline is precomputed (`reading_availability` table, migration 0024, `scripts/generate_reading_availability.py`) and served by its own `GET /api/charts/timeline` endpoint with **zero request parameters**, deliberately independent of every Charts tab filter (site, date range, condition, conductor/grease, detection_logic, show_historical) - see "What's built, by area" above. This reverses the earlier 2026-08-21 decision to leave the timeline coupled to the current filters "to match old-app parity" - re-litigated and changed on explicit request (2026-08-22): the timeline no longer changes when you change any other Charts tab option. **Still not fixed**: `_fetch_filtered_readings_dataframe`'s per-request pandas work for the *noise chart itself* (row-by-row DataFrame construction, per-site conductor-event stamping, sparse-bucket-shifting) still reruns from scratch on every load with no caching, unlike Trends/Locations, which read from a precomputed table. A `chart_bucket`-style precomputed table (mirroring `conductor_summary`/`rain_rate_fit`'s pattern) remains the natural next step for that piece specifically.
- **How many rows load per site**: **stale as of 2026-08-22** - at the time this was written, Charts and Trends shared one 3,000/site `PER_SITE_READING_LIMIT`. They no longer do - see the `per_site_limit` bullet above: Trends is still 3,000/site, Charts is now 100,000/site via its own `CHARTS_PER_SITE_LIMIT`.
- **The Charts tab's `2020-01-01` default date floor has been removed** (2026-08-21, `chart_service.DEFAULT_CHART_START_DATE` deleted) - a request with no `start_date` now queries full history, still bounded by Charts' own per-site cap (`CHARTS_PER_SITE_LIMIT`, raised from the shared 3,000/site default to 100,000/site the following day - see the `per_site_limit` bullet above). Since a per-site cap already limits final row count regardless of date range, this doesn't reintroduce OOM risk, but does mean the SQL window function scans further back before truncating for any site with fewer than the cap's rows in its post-2020 history.
- **Reconductoring age review (2026-08-21)**: many sites lacking `processed_reading.reconductoring_age` is *mostly* a data-availability gap, not a code bug - checking the real 42-row `data/reconductoring_2026.csv` by hand, only 31 of 35 real sites have *any* reconductoring row at all; the other 4 have zero history to anchor an age on, and no column or query change can manufacture that. Of the 11 sites with 2 logged rows, `MAX(date)` (the pre-existing `latest_by_site()` logic) already picked the genuine event correctly in 10 cases (explicit "commissioning of reconductored line" notes + a conductor-family change) - only site 204 was genuinely ambiguous (id=44, "Fully greased duplex new Zebra", same Zebra family as the earlier row, so possibly just a re-grease rather than a true swap). `reconductoring.for_reconductoring_age` (migration 0023) exists to let a specific ambiguous row like that be excluded going forward, once reviewed - it was **not** applied to any specific production row automatically; the CSV evidence wasn't strong enough to justify guessing at real conductor history, so site 204's `id=44` (and any other future ambiguous case) needs a human call via the Reconductoring tab's now-editable column. **Now in real use**: site 209's `id=43` (2022-11-04) is flagged `False`, so `latest_by_site()` anchors that site's age on `id=42` (2023-02-21) instead - confirmed live. **Important nuance discovered debugging that (2026-08-23): `for_reconductoring_age` only affects `processed_reading.reconductoring_age`/Age-effects - it does NOT affect the Charts tab's separate "Days since conductoring" plot mode** (`chart_service._stamp_conductor`, a different multi-event walk over `ReconductoringRepository.list_events()`, called unfiltered). Flagging `id=43` False stops it anchoring Age-effects, but Charts' own plot mode still segments on it, so a reading ~10 days after 2022-11-04 will show `days_since_conductoring ≈ 10` on Charts even though the same reading correctly has `reconductoring_age = NULL` (predates the 2023-02-21 qualifying cutoff) in Age-effects. Not a bug in either mechanism individually, but a real trap if you assume the two "days since conductoring" concepts are the same calculation reading the same event set - they aren't.

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
- **`AUTO_SEED_DATA` seeds 829 demo `ProcessedReading` rows (all `detection_logic="original"`, `include=True`, plus a couple of real `reconductoring` rows for sites 51/115) into every test database** — an "empty data"/"no baseline" test scoped to the default `detection_logic="original"` isn't actually empty, and a test seeding its own row can silently lose to (or collide with) this baseline data. Hit repeatedly (`test_ingestion_job.py`, the Trends API tests, the conductor-colour test). Fix: scope such tests to `detection_logic="updated_2026"` (zero seeded rows) or otherwise date/id your test data outside what the baseline CSVs contain — don't assume a fresh test DB has *no* data in it. **The 829 `ProcessedReading` rows are spread across many sites, not just 51/115** — that "only 51/115 have baseline rows" fact is specific to `reconductoring.csv`'s 2 rows (see the `latest_by_site()` gotcha below), not `processed_reading.csv`. A `processed_reading`-aggregating test (e.g. `aggregate_availability`) can't assume an arbitrary "probably-unused" site id has zero baseline rows the way a `reconductoring`-aggregating test can — assert on min/max bounds instead of exact counts, or don't assert row_count at all.
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
- **`outage.outage_type` is itself foreign-key-constrained to the `outage_type` lookup table** (`data/outage_type.csv`: only `"monitoring"`/`"line"` are seeded) - an ORM-level `Outage(...)` insert in a test using an arbitrary string like `"planned"` fails with a plain `IntegrityError: FOREIGN KEY constraint failed` that (unlike a column-level FK on `noise_site_id`) is easy to misread as a *site*-id problem first, since that's the far more common FK failure in this codebase. Check both FKs on the model before assuming which one tripped.
- **SQLite has no row-value/tuple comparison support**, so a repository method that needs to filter a composite `(year, month)` range can't do `(WindRose.year, WindRose.month) >= (start_year, start_month)` portably across SQLite (tests) and MySQL (prod) the way it could with plain scalar columns. Fix used throughout the 2026-08-24 Weather-tab work: compare a single packed `year * 100 + month` (YYYYMM) integer expression instead - `WindRoseRepository.list_sectors`/`MonthlyRainfallRepository.list_months`/`MonthlyWeatherStatsRepository.list_months` all take `start_year_month`/`end_year_month` as plain ints for exactly this reason, and `site_climate_service._year_month()` packs a `(year, month)` tuple into the same shape before calling them.
- **A Plotly trace's `opacity` (and `line.color`) apply to the *whole* `go.Scatter`, not per-point** - there's no way to make some points/segments of one trace 50% transparent and others fully opaque within a single trace. Rendering a site's historical segment at reduced opacity (or a reconductoring-event-driven linestyle change) therefore requires *splitting* that site's data into multiple traces at each transition point, not styling individual points within one trace - see `chart_service._contiguous_runs`/`_build_noise_chart`. Each split trace needs its own `legendgroup` (shared across the runs from one logical site/conductor group) plus `showlegend=True` on only the first run, or the legend shows one duplicate entry per run.
- **Rebuilding and redeploying `web` alone is not enough when a change also touches a `scripts/generate_*.py`/`calculate_*.py` script** — those run in production via `docker compose -f docker-compose.prod.yml run --rm db-migrate python scripts/...`, a *separate* image (`docker/Dockerfile.migrate`) from `web`'s. Confirmed live: after adding `monthly_rainfall.total_rain`, running `generate_monthly_rainfall.py --dry-run` against the still-old `db-migrate` image printed the old (no-`total_rain`) output with no error - it silently ran stale code rather than failing loudly. Rebuild both images (`docker compose -f docker-compose.prod.yml build web db-migrate`) whenever a change touches backend/shared code that either image runs.
- **Adding a new boolean/0-1 editable column to a "diff the submitted table against server state" Save callback (Outages/Reconductoring/Historical's pattern) can't reuse the other fields' generic `row.get(field) or None` normalization** — that treatment exists to turn a blank text-field string into `NULL`, but applied to a boolean it wrongly turns a real `False`/`0` value into `None` (silently dropping the flag instead of clearing it - and if the column is `NOT NULL`, actually raises on save). It also breaks the "is this new row still blank, skip it" check, since a boolean defaulting to a truthy value makes every freshly-added row look non-blank. Fix: keep the boolean out of the generic per-field loop entirely, compute it separately via `bool(row.get(field, default))`, and give `add_row`'s blank-row template the column's real default (not `""`). See `reconductoring.py`'s `CORE_EDITABLE_FIELDS` vs `EDITABLE_FIELDS` split for the worked example (`for_reconductoring_age`).
- **No browser automation available in this dev environment** (no chromium, no node/npx, no playwright on host or in any container) — a CSS-only/visual-only UI change (widened boxes, chip wrapping, colours, spacing) can only be verified structurally (correct CSS shipped, correct className/style values present in the server-rendered component tree via `_dash-update-component`), never with an actual screenshot. Say so explicitly when reporting on this kind of change rather than implying a visual check happened - confirmed structurally correct is not the same claim as confirmed to look right. **Consequence hit in practice**: widening the Charts tab's Sites box (600-650px) without also giving the *left* column's own filter rows `flexWrap: "wrap"` caused a real overlap (Sites over Measurement duration/Grease) that only surfaced once looked at in a real browser - a flex row with `nowrap` (the default) doesn't shrink its children below their own `minWidth`, it lets them overflow the parent's bounds instead, and that overflow silently draws over whatever sits to the right. Any flex row of fixed-minWidth items sitting next to another sized box needs `flexWrap: "wrap"` on itself (not just the outer container) or it can overflow into that box the moment the available width changes - this app's `charts.py` now sets it on every filter row for exactly this reason.

## Key decisions already made (don't relitigate without reason)
- Keep the original `transpower-conductor-noise-tool` untouched as a reference copy — never import from it.
- Modular-monolith-to-two-apps migration, not a microservices split.
- Frontend/backend separation is the primary boundary; don't split ingestion/API/persistence into separate deployables yet.
- Preserve current user-facing behavior first, refine internals second.
- Shared DTOs live inside this repo (`shared/contracts.py`), not a separate installable package.
- Frontend calls backend via a thin client wrapper (`frontend/client.py`), not raw HTTP calls scattered through callbacks.
- Follow the layered vertical-slice pattern for any new feature (model → repository → domain service → API route → shared contract → frontend client → callback/page), and apply `@require_write_access` to any new write endpoint.
- For any tab/feature where the old app has little or no real behavior to port, treat that as a scope question for the user via `AskUserQuestion` rather than silently inventing or silently faithfully-porting a stub.
- Every precomputed/materialized derived table (`conductor_summary`, `rain_rate_fit`, `wind_rose`, `monthly_rainfall`, `monthly_weather_stats`, `conductor_age_fit`) is fully **delete-then-bulk-insert** (`replace_all`) on every regeneration run, never incrementally patched — a stale combination that no longer has matching source data is naturally dropped, not left behind with garbage stats.
- **Aggregation over a large source table (`reading`, ~2.4M rows) is done in SQL (Core `GROUP BY`/window functions), not pulled into pandas** — the pandas-in-Python approach used for `conductor_summary`/`rain_rate_fit` (source: `processed_reading`, ~260k rows) doesn't scale to `reading`'s size; `wind_rose`/`monthly_rainfall` generation only ever pulls back the small, already-aggregated result. Follow this precedent (Core aggregation, not ORM-objects-into-pandas) for any future table whose source is `reading` rather than `processed_reading`.
- New boolean toggle UI controls use `dbc.Switch` (e.g. Charts' "Show historical") rather than the older `dcc.Dropdown([True, False])` pattern (Trends' "Include dry") — both exist in the codebase, no need to retrofit the older ones to match.
- `dbc.Card`/`dbc.CardHeader`/`dbc.CardBody` is the pattern for a visually-boxed-off UI section (first used for Charts' "Sites" panel, 2026-08-23) — no prior precedent existed before that; use it for any future "put this control in its own box" request rather than a plain bordered `html.Div`.
- A multi-select `dcc.Dropdown` that's expected to hold many selections (e.g. Charts' site selector, 29-35 real sites) gets "Select all"/"Clear" buttons next to it (`bulk_select_sites` in `callbacks/charts.py`, using `dash.ctx.triggered_id` to tell the two buttons apart) rather than relying on clicking each option in the dropdown individually - the standing pattern for "make bulk multi-select easy" requests.

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
# HistoricalResult points will NOT appear, even though the data exists).
# Response is {"noise_chart": ...} only - no timeline_chart key any more.
curl -X POST http://localhost:5001/api/charts -H "Content-Type: application/json" \
  -d '{"noise_site_id":[51],"condition":"all","parameter":"tone_100hz","interval_weeks":2}'

# Data Availability Timeline - a plain GET, no body/params of any kind (site
# selection, date range, etc. on the Charts tab have zero effect on this)
curl http://localhost:5001/api/charts/timeline

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

# Weather tab: per-site wind rose / monthly rainfall (each item has avg_rain_mm and
# total_rain; empty items, not a 404, for a site with no precomputed rows yet) -
# optional ?start=YYYY-MM&end=YYYY-MM (month+year only) re-aggregates a date-scoped
# subset instead of full history; omit both for the old full-history behavior
curl http://localhost:5001/api/sites/115/wind-rose
curl http://localhost:5001/api/sites/115/monthly-rainfall
curl "http://localhost:5001/api/sites/115/wind-rose?start=2025-01&end=2025-12"

# Weather tab: monthly min/max/avg rain_mm and wind_speed for a date range - already
# at (site, year, month) granularity, so start/end here is a straight filter, no
# re-aggregation
curl "http://localhost:5001/api/sites/115/monthly-weather-stats?start=2025-01&end=2025-12"

# Locations tab: per-site summary shown when a map marker is clicked - reconductoring
# events, outages, data-availability date range, and original/updated_2026 detected-
# event counts, all in one request
curl http://localhost:5001/api/sites/115/summary

# Site detail (incl. latitude/longitude, is_ignored) and update (requires write_access=True - demo user has it)
curl http://localhost:5001/api/sites/detail                    # excludes is_ignored sites by default
curl http://localhost:5001/api/sites/detail?include_ignored=true
curl -b /tmp/cookies.txt -X PATCH http://localhost:5001/api/sites/51 \
  -H "Content-Type: application/json" -d '{"site_code":"NEW","plot_color":"#aabbcc","latitude":-40.35,"longitude":175.61,"is_ignored":false}'

# Outages / Reconductoring / Historical (same shape, full add/edit/delete, requires write_access)
curl http://localhost:5001/api/outages
curl -b /tmp/cookies.txt -X POST http://localhost:5001/api/outages -H "Content-Type: application/json" \
  -d '{"noise_site_id":51,"outage_type":"monitoring","start_datetime":"2025-01-01T00:00:00","end_datetime":"2025-01-01T01:00:00"}'

# Grease code -> human description lookup, backing the Charts tab's Grease dropdown labels
curl http://localhost:5001/api/reconductoring/grease-descriptions

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

**Fork schema is fully in sync through migration `0024`** — every column/table this repo's migrations have added is applied there too, via direct SQL (never this repo's own Alembic — see "Known gotchas" for why), run by you:
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

-- migration 0015, already applied to the fork (full DDL: alembic/versions/0015_add_processed_reading_site_datetime_index.py):
CREATE INDEX ix_processed_reading_site_datetime ON processed_reading (noise_site_id, datetime);

-- migration 0016, already applied to the fork (full DDL: alembic/versions/0016_add_site_is_ignored.py):
ALTER TABLE site ADD COLUMN is_ignored TINYINT(1) NOT NULL DEFAULT 0;

-- migration 0017, already applied to the fork (full DDL: alembic/versions/0017_create_wind_rose.py):
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

-- migration 0018, already applied to the fork (full DDL: alembic/versions/0018_create_monthly_rainfall.py):
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

-- migration 0019, already applied to the fork (full DDL: alembic/versions/0019_add_processed_reading_reconductoring_age.py):
ALTER TABLE processed_reading ADD COLUMN reconductoring_age INT NULL;
-- after adding the column, populate it: python scripts/calculate_reconductoring_age.py

-- migration 0020, already applied to the fork (full DDL: alembic/versions/0020_create_conductor_age_fit.py):
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

-- migration 0021, already applied to the fork (full DDL: alembic/versions/0021_create_grease_description.py):
CREATE TABLE grease_description (
    grease VARCHAR(20) NOT NULL,
    description VARCHAR(255) NOT NULL,
    PRIMARY KEY (grease)
);
INSERT INTO grease_description (grease, description) VALUES
    ('C1', 'Steel core greased only'),
    ('C1.5', '1 layer of Al greased'),
    ('C2', 'Fully greased');
-- no generation script needed - this is a small hand-maintained lookup table, not a
-- derived/materialized one. Add a new row by hand (INSERT ... ON DUPLICATE KEY UPDATE
-- description = VALUES(description) to also cover editing an existing code's wording)
-- whenever a reconductoring event introduces a new grease code.

-- migration 0022, already applied to the fork (full DDL: alembic/versions/0022_add_monthly_rainfall_total_rain.py):
ALTER TABLE monthly_rainfall ADD COLUMN total_rain DECIMAL(8,2) NOT NULL DEFAULT 0;
-- after adding the column, regenerate it: python scripts/generate_monthly_rainfall.py --dry-run, then for real
-- (the DEFAULT 0 only matters for the instant between the ALTER and the next
-- regeneration run - monthly_rainfall is always fully replace_all'd, so every
-- row's real total_rain is written on the very next run)

-- migration 0023, already applied to the fork (full DDL: alembic/versions/0023_add_reconductoring_for_age_flag.py):
ALTER TABLE reconductoring ADD COLUMN for_reconductoring_age TINYINT(1) NOT NULL DEFAULT 1;
-- no data backfill needed/planned - every existing row defaults to True (no
-- behavior change), so ReconductoringRepository.latest_by_site()'s new
-- .filter(for_reconductoring_age.is_(True)) picks up every current row
-- exactly as before. Flag a specific row False by hand (via the Reconductoring
-- tab's now-editable "For reconductoring age" column, or direct SQL) only
-- once you've confirmed it's a treatment-only event, not a genuine new
-- conductor - see "Reconductoring age review" under "Outstanding issues".

-- migration 0024, already applied to the fork (full DDL: alembic/versions/0024_create_reading_availability.py):
CREATE TABLE reading_availability (
    noise_site_id INT NOT NULL,
    min_datetime DATETIME NOT NULL,
    max_datetime DATETIME NOT NULL,
    row_count INT NOT NULL,
    computed_at DATETIME NOT NULL,
    PRIMARY KEY (noise_site_id),
    CONSTRAINT fk_reading_availability_site FOREIGN KEY (noise_site_id)
        REFERENCES site (noise_site_id) ON UPDATE CASCADE ON DELETE CASCADE
);
-- after creating the table, populate it: python scripts/generate_reading_availability.py --dry-run, then for real.
-- Cron-schedule this daily (processed_reading grows daily via ingestion) - see DEPLOY.md's daily chain.

-- migration 0025, already applied to the fork (full DDL: alembic/versions/0025_wind_rose_year_month.py):
ALTER TABLE wind_rose
    DROP PRIMARY KEY,
    ADD COLUMN year INT NOT NULL DEFAULT 0,
    ADD COLUMN month INT NOT NULL DEFAULT 0,
    ADD PRIMARY KEY (noise_site_id, year, month, direction_sector);

-- migration 0026, already applied to the fork (full DDL: alembic/versions/0026_monthly_rainfall_year.py):
ALTER TABLE monthly_rainfall
    DROP PRIMARY KEY,
    ADD COLUMN year INT NOT NULL DEFAULT 0,
    ADD PRIMARY KEY (noise_site_id, year, month);

-- migration 0027, already applied to the fork (full DDL: alembic/versions/0027_create_monthly_weather_stats.py):
CREATE TABLE monthly_weather_stats (
    noise_site_id INT NOT NULL,
    year INT NOT NULL,
    month INT NOT NULL,
    min_rain_mm DECIMAL(4,2) NULL,
    max_rain_mm DECIMAL(4,2) NULL,
    avg_rain_mm DECIMAL(4,2) NULL,
    min_wind_speed DECIMAL(4,1) NULL,
    max_wind_speed DECIMAL(4,1) NULL,
    avg_wind_speed DECIMAL(4,1) NULL,
    sample_count INT NOT NULL,
    computed_at DATETIME NOT NULL,
    PRIMARY KEY (noise_site_id, year, month),
    CONSTRAINT fk_monthly_weather_stats_site FOREIGN KEY (noise_site_id)
        REFERENCES site (noise_site_id) ON UPDATE CASCADE ON DELETE CASCADE
);

-- migration 0028, already applied to the fork (full DDL: alembic/versions/0028_add_site_historical_line_color.py):
ALTER TABLE site ADD COLUMN historical_line_color VARCHAR(7) NULL;
```
Migrations 0025-0028 applied 2026-08-24, followed by real (non-dry-run) `generate_wind_rose.py`/`generate_monthly_rainfall.py`/`generate_monthly_weather_stats.py` runs (13,291 / 883 / 883 rows written respectively) and a `web`+`db-migrate` rebuild+redeploy - confirmed live via `GET /api/sites/209/wind-rose` (16 sectors, both full-history and `?start=2026-06&end=2026-08`-scoped), `GET /api/sites/209/monthly-weather-stats?start=2026-06&end=2026-08` (3 real rows), and `GET /api/sites/209/summary` (real outages/availability/detected-event-count data). `reconductoring.plot_linestyle` needed no SQL - the column already existed on the fork from an earlier migration, this round only added the app-level UI/logic to use it.
If a future migration adds another column/table, add its equivalent statement here and run it the same way (single multi-clause `ALTER TABLE` for any PK change — see "Known gotchas").

**Real data on the fork, not just schema**: `reading.leq_rmse` has ~1.64M real values (of ~2.38M rows), loaded via `scripts/import_leq_rmse_from_sqlite.py`. `scripts/backfill_updated_2026_processed_readings.py` has regenerated all sites' `updated_2026` rows (137,044 total). Every `generate_*.py`/`calculate_*.py` script listed above has been run for real at least once — see "Production database" under "Current status" for current row counts (`conductor_summary`, `rain_rate_fit`, `wind_rose`, `monthly_rainfall`, `conductor_age_fit`, `processed_reading.reconductoring_age`). Re-running any of these is only needed if the underlying source data changes again — each is safe/idempotent to re-run (see each script's own `--dry-run` output before doing so).

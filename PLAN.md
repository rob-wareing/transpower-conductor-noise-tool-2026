# Plan: fix callback timeouts / self-call deadlock

## Background

In October 2026 the Charts tab and the Outages table intermittently failed to load. The logs showed only `ReadTimeout` errors: Dash callbacks calling the app's own API at `127.0.0.1:5000` and getting no answer within 10s/30s. Daily counts: 2-7 on 5-7 Oct, 31 on 18 Oct, 420 on 22 Oct, 18 on 25 Oct. The new outage rows (ids 492-495, site 209) were valid and were not the cause.

Cause: gunicorn ran `--workers 2 --threads 4`, i.e. 8 request slots shared by the Dash callbacks and the API they call over HTTP. Opening the app starts the initial-load callbacks for every tab at once (20+), each holding a slot while it waits on an API request that needs a slot of its own. Once all 8 slots are held by waiting callbacks, the API requests can't run and everything stalls until the timeouts fire. The host is also short of memory (~2 GB RAM, ~850 MB swap in use; each gunicorn worker ~340 MB), which makes every request slower and the stall more likely.

## Order

1. **Raise gunicorn threads** - done, deployed 2026-10-25 (commit c1105c5).
2. **3a - Load each tab's data only when it is opened** - implemented, not yet committed or deployed.
3. **2 - Call the backend in the same process** instead of over HTTP.
4. **3b - Make the default chart faster.**
5. **3c - Free up memory on the server** - operational, can happen any time.

## 1. Raise gunicorn threads (done, deployed)

`Dockerfile` CMD changed from `--threads 4` to `--threads 16` (32 slots). Threads cost little memory, unlike extra workers. Deploy with:

```bash
docker compose -f docker-compose.prod.yml up -d --build web
```

## 3a. Load each tab's data only when it is opened (implemented)

Every tab currently loads its data from a one-shot `dcc.Interval` (`*-init`, `max_intervals=1`) that fires about a second after the page renders, including for hidden tabs.

1. Give the main `dbc.Tabs` in `frontend/app.py` an id (`main-tabs`), and the Trends sub-tabs an id (`trends-tabs`).
2. Every `*-init` interval except `chart-init` (Charts is the default tab) starts `disabled=True`.
3. A new `frontend/callbacks/tab_loading.py` enables each tab's interval the first time that tab (and for Trends, that sub-tab) becomes active. Because the intervals have `max_intervals=1`, each tab then loads once per page load. Switching back to a tab does not refetch, the same as today.
4. Dash runs every callback once on the initial render (`n_intervals=0`), so a disabled interval alone doesn't stop the backend calls. All 18 callbacks with a `*-init` input now start with `if not n_intervals: return no_update`. That includes the Charts tab's, which also removes a duplicate all-sites chart request on every page load.
5. Tests: `tests/test_tab_loading_callbacks.py` (31 tests) covers enabling each interval, intervals starting disabled, and the initial-render guards. The existing tests needed no changes; the full suite passes (420).

Result: opening the app runs only the Charts tab's callbacks instead of every tab's.

Possible follow-up: the Outages/Reconductoring/Historical/Sites tables could refresh each time their tab is reopened, to pick up other users' edits. That's not needed for the fix.

## 2. Call the backend in the same process

Goal: Dash callbacks stop making HTTP requests to their own server, so a callback can never wait on a free request slot. The `BackendClient` methods, the API routes, the write-access checks and the shared contracts all stay as they are, which keeps the rule that the frontend talks to the backend only through its API.

1. Add a small in-memory transport (about 40 lines, e.g. `frontend/wsgi_transport.py`): a `requests` adapter that runs each request through the Flask app via Werkzeug's test tools. It must pass cookies and query strings through and return a normal `requests.Response`, so `.json()`, `.raise_for_status()` and `.status_code` keep working. Writing it ourselves avoids a dependency; the `requests-wsgi-adapter` package does the same thing.
2. Change `BackendClient` to use a `requests.Session` (`self.session.get/post/...` instead of `requests.get/post/...` - a mechanical find-and-replace of about 30 calls). Add an optional `wsgi_app`: when set, the session uses the in-memory transport; when not, it uses HTTP as today.
3. Build one client in `create_dashboard` and pass it to every `register_callbacks`, instead of each of the eight callback modules building its own `BackendClient(backend_url)`. Update `wsgi.py` to pass the backend app.
4. Login (riskiest part): `_relay_cookies` copies the backend's session cookie onto the browser response. In-memory responses don't fill in `response.cookies` the way real HTTP ones do, so either the adapter fills it in or `_relay_cookies` reads the `Set-Cookie` header.
5. `timeout=` arguments have no effect in memory. That's fine, because gunicorn's `--timeout 120` still stops runaway requests. Keep them for HTTP mode.
6. Tests: existing callback tests use `MagicMock(spec=BackendClient)` and shouldn't break. Add:
   - adapter tests (GET with a query string, POST with JSON, cookies in both directions, error status codes);
   - one end-to-end test that logs in and loads the outages table entirely in memory.
7. Check under load: open several browser tabs at once and confirm there are no `ReadTimeout` errors in the logs. Then `--threads` can come back down if wanted.

Effort: about half a day to a day.

## 3b. Make the default chart faster

The default `POST /api/charts` (no site filter) takes about 15s.

- Measure where `chart_service` spends its time on that request.
- Likely options: cache the reconductoring and outage data for a short time, or open with a sensible default site or date range instead of all sites.

## 3c. Free up memory on the server (no code changes)

- Close VS Code Remote / Claude Code sessions on the production server when not in use, or move development to a separate server (already flagged in CLAUDE.md).
- Don't add gunicorn workers (~340 MB each); add threads instead.

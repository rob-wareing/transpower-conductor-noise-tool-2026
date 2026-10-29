# Plan: reliability fixes

Two workstreams: callback timeouts / self-call deadlock (sections 1-3c), and Outages table saves that silently didn't save (section 4).

## Background

In October 2026 the Charts tab and the Outages table intermittently failed to load. The logs showed only `ReadTimeout` errors: Dash callbacks calling the app's own API at `127.0.0.1:5000` and getting no answer within 10s/30s. Daily counts: 2-7 on 5-7 Oct, 31 on 18 Oct, 420 on 22 Oct, 18 on 25 Oct. The new outage rows (ids 492-495, site 209) were valid and were not the cause.

Cause: gunicorn ran `--workers 2 --threads 4`, i.e. 8 request slots shared by the Dash callbacks and the API they call over HTTP. Opening the app starts the initial-load callbacks for every tab at once (20+), each holding a slot while it waits on an API request that needs a slot of its own. Once all 8 slots are held by waiting callbacks, the API requests can't run and everything stalls until the timeouts fire. The host is also short of memory (~2 GB RAM, ~850 MB swap in use; each gunicorn worker ~340 MB), which makes every request slower and the stall more likely.

## Order

1. **Raise gunicorn threads** - done, deployed 2026-10-25 (commit c1105c5).
2. **3a - Load each tab's data only when it is opened** - done (commit af66950).
3. **2 - Call the backend in the same process** instead of over HTTP.
4. **3b - Make the default chart faster.**
5. **3c - Free up memory on the server** - operational, can happen any time.

## 1. Raise gunicorn threads (done, deployed)

`Dockerfile` CMD changed from `--threads 4` to `--threads 16` (32 slots). Threads cost little memory, unlike extra workers. Deploy with:

```bash
docker compose -f docker-compose.prod.yml up -d --build web
```

## 3a. Load each tab's data only when it is opened (done)

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

## 4. Outages table: rows that didn't save

### Background

In October 2026 a user adding several outage rows found that occasionally a row didn't save. The logs from that time were lost when the container restarted, so the exact cause per row isn't known. Contributing causes found in the code and data:

- A rejected row got an error message under the table, but the table then reloaded from the server, so the row disappeared and the message was easy to miss.
- Rows are rejected for strict date formats (e.g. `2026-09-27 1:33`, `27/09/2026 01:33` and trailing spaces all fail; `2026-09-27 01:33` works) and for a mistyped Site ID (the database refuses unknown sites).
- Outage id 513 is missing from an otherwise regular sequence (511 site 181, 512 site 209, 514 site 206): the first attempt at the 206 row most likely reached the database and was refused, then was entered again.
- Save deleted every server row missing from the browser's copy of the table, so saving from a stale copy deleted rows other users had added since.
- An unexpected server error (e.g. notes over the database's 200-character limit) returned an HTML page; the save then crashed with no message, and the rows after it weren't saved.

Ruled out: timeouts. The database round trip is 0.6 ms and the thread fix was already live.

### Order

1. **Keep rejected rows in the table, with the reason** - done (not yet committed).
2. **Delete only rows the user removed** - done (not yet committed).
3. **Clear message on unexpected server errors** - partly done; backend part to do.
4. **Accept more date formats and show the expected format.**
5. **Make Site ID a dropdown of real sites.**
6. **Only send changed rows.**
7. **Apply the same fixes to the Reconductoring, Historical and Sites tables.**

### 4.1 Keep rejected rows in the table (done)

`frontend/callbacks/outages.py`, `layout/outages.py`, `layout/table_styles.py`:

- `save_outages` now writes the table itself (`outages-table.data`, `allow_duplicate=True`) instead of `refresh_outages_table` reloading on every `outages-status` change (that Input has been removed).
- After saving it reloads the server rows, then puts back the failed rows: a failed update keeps the user's values instead of the server's; a failed new row is appended at the end; a row whose delete failed stays. Each carries a `save_error` string with the reason.
- `SAVE_ERROR_HIGHLIGHT` (`filter_query: "{save_error} is str"`) colours those rows red. A read-only "Save error" column is added to the table's `columns` only while there are failed rows, and removed on the next clean save.
- The status line explains that highlighted rows didn't save, followed by the list of errors.
- `save_error` is display-only: it isn't in `EDITABLE_FIELDS`, so it's never sent to the backend, and a row that saves on retry comes back from the server without it.

### 4.2 Delete only rows the user removed (done)

- A `dcc.Store` (`outages-loaded-ids`) holds the ids the table was last loaded with. It is set by `refresh_outages_table` and by every save.
- Save deletes only `loaded ids - submitted ids`: rows that were in the user's table and that they removed. Rows added by others after the table loaded are left alone.
- A delete that returns 404 (already deleted elsewhere) counts as success.

### 4.3 Clear message on unexpected server errors (frontend done, backend to do)

Done: `_error_message()` in `callbacks/outages.py` reads `{"error": ...}` from the response. For a pydantic error list it takes the first message, and for a non-JSON response it returns `server error (HTTP 500)`, so the save carries on and the row is kept with that reason.

To do:

- `shared/contracts.py`: add `Field(max_length=200)` to `notes` and `max_length=20` to `outage_type` on `OutageCreate`/`OutageUpdate`, matching the `outage` table's columns. Over-long values are then rejected with a clear message before they reach the database.
- `backend/api/outage_routes.py`: also catch `sqlalchemy.exc.DataError` (MySQL runs in `STRICT_ALL_TABLES`, so bad values raise rather than being truncated). Roll back and return 400 `{"error": "value too long or invalid for the database"}` instead of an HTML 500.
- Tests: an over-long note is rejected by the contract; a `DataError` from the service maps to 400.

### 4.4 Accept more date formats and show the expected format

- `shared/contracts.py`: add a `field_validator("start_datetime", "end_datetime", mode="before")` on `OutageCreate` and `OutageUpdate`. Because the backend validates with the same contract, this applies on both sides. The validator should:
  - strip surrounding whitespace;
  - try `datetime.strptime` with `%Y-%m-%d %H:%M`, `%Y-%m-%d %H:%M:%S`, `%Y-%m-%dT%H:%M`, `%Y-%m-%dT%H:%M:%S`, `%d/%m/%Y %H:%M` and `%d/%m/%Y`;
  - otherwise fall through to pydantic's own parsing.

  `strptime`'s `%H`/`%m`/`%d` accept single digits, so `2026-9-27 1:33` works.
- Treat slashes as day/month/year (NZ order) only. Say so in the Help tab, since `03/10/2026` would otherwise be ambiguous.
- `layout/outages.py`: rename the column headers to "Start (YYYY-MM-DD HH:MM)" and "End (YYYY-MM-DD HH:MM)", or add `tooltip_header` with the accepted formats.
- Tests: a table of accepted and rejected strings in `tests/test_outages.py`, including the cases above.

### 4.5 Make Site ID a dropdown of real sites

- `layout/outages.py`: give the `noise_site_id` column `presentation: "dropdown"`, as `outage_type` already has.
- `callbacks/outages.py`: extend `populate_outage_type_options` (rename it `populate_dropdowns`) to also return `{"noise_site_id": {"options": [{"label": "(206) Name", "value": 206}, ...]}}`.
- Use `client.get_site_details(include_ignored=True)`, not `get_sites()`. Existing rows for ignored sites (e.g. 205) must still show their site rather than a blank cell.
- Tests: the dropdown options include ignored sites, and their values are integers.

### 4.6 Only send changed rows

Save currently PATCHes every existing row (about 470 requests per save) with whatever the browser holds. This can overwrite another user's recent edit with stale values.

- Change `outages-loaded-ids` to store the loaded rows themselves, as `{id: fields}`.
- On save, PATCH only rows whose `EDITABLE_FIELDS` differ from that snapshot. Deletes still use the snapshot's ids.
- Tests: an unchanged row isn't PATCHed; an edited row is.

### 4.7 Reconductoring, Historical and Sites tables

`callbacks/reconductoring.py` and `callbacks/historical.py` use the same "delete every server row missing from the table" logic (`server_*.keys() - submitted_ids`) and the same reload-after-save. Apply 4.1-4.3 and 4.6 to each. `callbacks/sites.py` has no delete or create, but would benefit from 4.1 and 4.6.

Pull the shared pieces (`_error_message`, `_with_save_error`, the column helpers, the delete/update/create loop) into a common module such as `frontend/callbacks/table_save.py`, so the four tables don't each get a copy.

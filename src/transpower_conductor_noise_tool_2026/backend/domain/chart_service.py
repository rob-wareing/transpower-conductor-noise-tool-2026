import json
from datetime import date, datetime

import pandas as pd
import plotly.colors
import plotly.graph_objects as go
import plotly.io as pio

from transpower_conductor_noise_tool_2026.backend.config import Settings
from transpower_conductor_noise_tool_2026.backend.persistence.repositories.historical_result_repository import (
    HistoricalResultRepository,
)
from transpower_conductor_noise_tool_2026.backend.persistence.repositories.outage_repository import (
    OutageRepository,
)
from transpower_conductor_noise_tool_2026.backend.persistence.repositories.processed_reading_repository import (
    ProcessedReadingRepository,
)
from transpower_conductor_noise_tool_2026.backend.persistence.repositories.reading_availability_repository import (
    ReadingAvailabilityRepository,
)
from transpower_conductor_noise_tool_2026.backend.persistence.repositories.reconductoring_repository import (
    ReconductoringRepository,
)
from transpower_conductor_noise_tool_2026.backend.persistence.repositories.site_repository import (
    SiteRepository,
)
from transpower_conductor_noise_tool_2026.shared.contracts import ChartFilters

PARAMETER_COLUMNS = {"leq_adj", "tone_100hz", "tone_200hz"}
CONDITION_TO_IS_WET = {"wet": True, "dry": False}
RAW_COLUMNS = [
    "id",
    "noise_site_id",
    "site_name",
    "datetime",
    "leq_adj",
    "tone_100hz",
    "tone_200hz",
    "rain1",
    "rain2",
    "is_wet",
    "include",
]
TABLE_COLUMNS = [
    "id",
    "noise_site_id",
    "site_name",
    "datetime",
    "conductor_and_treatment",
    "grease",
    "days_since_conductoring",
    "leq_adj",
    "tone_100hz",
    "tone_200hz",
    "rain1",
    "rain2",
    "is_wet",
    "include",
]
BUCKETED_COLUMNS = [
    "noise_site_id",
    "site_name",
    "datetime",
    "conductor_and_treatment",
    "grease",
    "days_since_conductoring",
    "leq_adj",
    "tone_100hz",
    "tone_200hz",
    "linestyle",
    "is_historical",
    "event_count",
    "conductor_label",
]
# Matches trends_service.SITE_COLOR_PALETTE - explicit per-site cycling
# (rather than Plotly's own implicit per-trace auto-coloring) so a site's
# historical-segment trace can deliberately share color with its current-
# segment sibling trace.
SITE_COLOR_PALETTE = plotly.colors.qualitative.Plotly
HISTORICAL_OPACITY = 0.5
PLOT_BY_AXIS_TITLES = {"datetime": "Date", "days_since_conductoring": "Days since conductoring"}
DAYS_SINCE_GUARD_TITLE = (
    "Select a conductor/treatment or grease filter to plot by days since conductoring"
)
# Fixed epoch bucket boundaries are anchored to, ported from the old app so its
# historical HistoricalResult period_end_dates land on matching 2-week grid lines.
AGGREGATION_DATE = date(2016, 3, 13)
MIN_BUCKET_READINGS = 3
TIMELINE_COLORS = [
    "#1f77b4",
    "#ff7f0e",
    "#2ca02c",
    "#d62728",
    "#9467bd",
    "#8c564b",
    "#e377c2",
    "#7f7f7f",
    "#bcbd22",
    "#17becf",
]


def _figure_to_json(figure):
    # plotly's own encoder handles numpy arrays / pandas Timestamps that the
    # stdlib json module (used by Flask's jsonify) can't serialize.
    return json.loads(pio.to_json(figure))


def _rows_to_dataframe(readings, sites_by_id):
    records = []
    for reading in readings:
        site = sites_by_id.get(reading.noise_site_id)
        height_adj_db = float(site.height_adj_db) if site else 0.0
        records.append(
            {
                "id": reading.id,
                "noise_site_id": reading.noise_site_id,
                "site_name": site.site_name if site else str(reading.noise_site_id),
                "datetime": reading.datetime,
                "leq_adj": float(reading.l90) + height_adj_db,
                "tone_100hz": float(reading.tone_100hz),
                "tone_200hz": float(reading.tone_200hz),
                "rain1": float(reading.rain1),
                "rain2": float(reading.rain2),
                "is_wet": bool(reading.is_wet),
                "include": bool(reading.include),
            }
        )
    df = pd.DataFrame.from_records(records, columns=RAW_COLUMNS)
    # An empty (zero-row) dataframe built from records has no data to infer
    # dtypes from, so "datetime" can come in as plain `object` rather than
    # datetime64 - cast explicitly here so every downstream comparison/
    # arithmetic operation on it is safe even when there are zero readings.
    df["datetime"] = pd.to_datetime(df["datetime"])
    # Low-cardinality repeated string columns and metric columns don't need
    # full object/float64 width - shrinks peak memory with no behaviour
    # change (Plotly/JSON serialization still goes through .tolist(), which
    # yields plain Python values regardless of the narrower backing dtype).
    df["site_name"] = df["site_name"].astype("category")
    for column in ("leq_adj", "tone_100hz", "tone_200hz", "rain1", "rain2"):
        df[column] = df[column].astype("float32")
    return df


def _exclude_outage_windows(df, outages):
    # A reading taken while a site's logger was known to be down/noise-
    # corrupted (an Outage window) shouldn't count toward that period's
    # average, or appear in the raw-data table at all - ported from the old
    # app's append_outages(), ordered before conductor stamping/bucketing so
    # excluded readings never influence either.
    for outage in outages:
        is_outage = (
            (df["noise_site_id"] == outage.noise_site_id)
            & (df["datetime"] > outage.start_datetime)
            & (df["datetime"] <= outage.end_datetime)
        )
        df = df.loc[~is_outage]
    return df


def _stamp_conductor(df, events, conductor_and_treatment, grease):
    # For each site, walk its Reconductoring events oldest-first and stamp
    # every reading from that event's date onward with its conductor/grease -
    # a later event overwrites an earlier one for rows after it, so every
    # reading always reflects whichever event was most recently in effect.
    # When a conductor_and_treatment/grease filter is active, only events
    # matching it are stamped at all - readings never covered by a matching
    # event are left blank and get dropped by _apply_conductor_filters.
    df = df.copy()
    # An empty (zero-row) dataframe built from records has no data to infer
    # dtypes from, so "datetime" can come in as plain `object` rather than
    # datetime64 - cast explicitly so the subtraction below always works.
    df["datetime"] = pd.to_datetime(df["datetime"])
    df["conductor_and_treatment"] = ""
    df["grease"] = ""
    # Assigning a bare pd.NaT scalar to a new column produces an *object*
    # dtype column, not datetime64 - explicitly cast so later datetime
    # subtraction works even when zero rows end up stamped.
    df["reconductoring_date"] = pd.to_datetime(pd.Series(pd.NaT, index=df.index))
    df["days_since_conductoring"] = None
    df["linestyle"] = "solid"

    events_by_site = {}
    for event in events:
        if conductor_and_treatment and event.conductor_and_treatment not in conductor_and_treatment:
            continue
        if grease and event.grease not in grease:
            continue
        events_by_site.setdefault(event.noise_site_id, []).append(event)

    for site_id, site_events in events_by_site.items():
        for event in sorted(site_events, key=lambda e: e.reconductoring_date):
            event_datetime = pd.Timestamp(
                datetime.combine(event.reconductoring_date, datetime.min.time())
            )
            mask = (df["noise_site_id"] == site_id) & (df["datetime"] >= event_datetime)
            df.loc[mask, "conductor_and_treatment"] = event.conductor_and_treatment or ""
            df.loc[mask, "grease"] = event.grease or ""
            df.loc[mask, "reconductoring_date"] = event_datetime

    stamped = df["reconductoring_date"].notna()
    df.loc[stamped, "days_since_conductoring"] = (
        df.loc[stamped, "datetime"] - df.loc[stamped, "reconductoring_date"]
    ).dt.days
    # reconductoring_date is kept (not just days_since_conductoring) so bucket
    # aggregation can later derive its own per-bucket days-since value from it.

    # Line style is a site-wide visual timeline (which reconductoring "era" a
    # reading falls in), independent of any active conductor_and_treatment/
    # grease filter - so it's a second, separate date-ordered walk over
    # *every* reconductoring event for the site that has a plot_linestyle set
    # (not just ones matching the filter above). A row before any such event,
    # or a site with no styled events at all, keeps the "solid" default.
    linestyle_events_by_site = {}
    for event in events:
        if not event.plot_linestyle:
            continue
        linestyle_events_by_site.setdefault(event.noise_site_id, []).append(event)

    for site_id, site_events in linestyle_events_by_site.items():
        for event in sorted(site_events, key=lambda e: e.reconductoring_date):
            event_datetime = pd.Timestamp(
                datetime.combine(event.reconductoring_date, datetime.min.time())
            )
            mask = (df["noise_site_id"] == site_id) & (df["datetime"] >= event_datetime)
            df.loc[mask, "linestyle"] = event.plot_linestyle

    return df


def _apply_conductor_filters(df, conductor_and_treatment, grease):
    if conductor_and_treatment:
        df = df.loc[df["conductor_and_treatment"].isin(conductor_and_treatment)]
    if grease:
        df = df.loc[df["grease"].isin(grease)]
    return df


def _shift_sparse_buckets_forward(df):
    # A bucket with too few readings is noisy/underpowered, so its rows get
    # merged into the *next* bucket instead of plotted on their own. The last
    # bucket for a site is never merged forward (there's nothing after it to
    # merge into), so it's left alone even if sparse. Sparseness is judged on
    # plain (site, aggregate_date) counts, independent of any conductor/grease
    # split applied later - matches the old app's two-stage pipeline.
    df = df.copy()
    for site_id in df["noise_site_id"].unique():
        while True:
            site_mask = df["noise_site_id"] == site_id
            counts = df.loc[site_mask].groupby("aggregate_date").size().sort_index()
            if len(counts) < 2:
                break

            merged = False
            buckets = list(counts.index)
            for position, bucket_date in enumerate(buckets[:-1]):
                if counts.iloc[position] < MIN_BUCKET_READINGS:
                    next_date = buckets[position + 1]
                    rows_mask = site_mask & (df["aggregate_date"] == bucket_date)
                    df.loc[rows_mask, "aggregate_date"] = next_date
                    merged = True
                    break

            if not merged:
                break
    return df


def _conductor_label(conductor_and_treatment, grease):
    # "Conductor and treatment (Grease)" as shown in the chart hover text;
    # blank when a reading has no reconductoring event stamped on it.
    conductor_and_treatment = conductor_and_treatment or ""
    grease = grease or ""
    if conductor_and_treatment and grease:
        return f"{conductor_and_treatment} ({grease})"
    if grease:
        return f"({grease})"
    return conductor_and_treatment


def _bucket_readings(df, interval_weeks, group_by_conductor):
    empty = pd.DataFrame(columns=BUCKETED_COLUMNS)
    if df.empty:
        return empty

    working = df.loc[df["include"]].copy()
    if working.empty:
        return empty

    interval = pd.Timedelta(days=7 * interval_weeks)
    epoch = pd.Timestamp(datetime.combine(AGGREGATION_DATE, datetime.min.time()))
    working["aggregate_date"] = (
        working["datetime"] + interval - ((working["datetime"] - epoch) % interval)
    )
    working = _shift_sparse_buckets_forward(working)
    working["conductor_label"] = [
        _conductor_label(conductor, grease)
        for conductor, grease in zip(working["conductor_and_treatment"], working["grease"])
    ]

    group_columns = ["noise_site_id", "aggregate_date"]
    if group_by_conductor:
        group_columns += ["conductor_and_treatment", "grease"]

    grouped = working.groupby(group_columns)
    aggregated = grouped[["leq_adj", "tone_100hz", "tone_200hz"]].mean()
    aggregated["site_name"] = grouped["site_name"].first()
    # A bucket may straddle a linestyle-changing reconductoring date - taking
    # the first (earliest) row's already-stamped value, same as site_name, is
    # an approximation an interval_weeks-coarsened bucket inherently accepts.
    aggregated["linestyle"] = grouped["linestyle"].first()
    # Hover-text extras: how many readings were averaged into the point, and
    # which conductor/treatment applied. An ungrouped bucket can straddle a
    # reconductoring date, so distinct labels are all listed (in row order).
    aggregated["event_count"] = grouped.size()
    aggregated["conductor_label"] = grouped["conductor_label"].agg(
        lambda labels: " / ".join(dict.fromkeys(label for label in labels if label))
    )
    if group_by_conductor:
        aggregated["reconductoring_date"] = grouped["reconductoring_date"].first()
    aggregated = aggregated.reset_index().rename(columns={"aggregate_date": "datetime"})

    if group_by_conductor:
        has_event = aggregated["reconductoring_date"].notna()
        aggregated["days_since_conductoring"] = None
        aggregated.loc[has_event, "days_since_conductoring"] = (
            aggregated.loc[has_event, "datetime"] - aggregated.loc[has_event, "reconductoring_date"]
        ).dt.days
        aggregated = aggregated.drop(columns="reconductoring_date")
    else:
        aggregated["conductor_and_treatment"] = ""
        aggregated["grease"] = ""
        aggregated["days_since_conductoring"] = None

    aggregated["is_historical"] = False
    return aggregated[BUCKETED_COLUMNS]


def _historical_dataframe(filters: ChartFilters, sites_by_id, historical_repository, events):
    empty = pd.DataFrame(columns=BUCKETED_COLUMNS)
    # HistoricalResult rows are always from wet-condition surveys, per the old
    # app's own hardcoded assumption - excluded entirely for a dry-only filter.
    # Also excluded entirely in days-since-conductoring mode: a manually
    # surveyed historical point has no clean per-row link to a reconductoring
    # event the way an automated reading does, so the old app's own handling
    # of this combination is undefined/glitchy - simplified here by leaving
    # historical data out of that particular view rather than reproducing it.
    if filters.condition == "dry" or filters.plot_by == "days_since_conductoring":
        return empty

    results = historical_repository.list_results(site_ids=filters.noise_site_id or None)
    records = []
    for result in results:
        if result.noise_site_id not in sites_by_id:
            continue  # unknown or ignored site - excluded from display
        if filters.start_date and result.period_end_date <= filters.start_date:
            continue
        if filters.end_date and result.period_end_date > filters.end_date:
            continue
        site = sites_by_id.get(result.noise_site_id)
        records.append(
            {
                "noise_site_id": result.noise_site_id,
                "site_name": site.site_name if site else str(result.noise_site_id),
                "datetime": pd.Timestamp(result.period_end_date),
                "leq_adj": float(result.leq_adj) if result.leq_adj is not None else None,
                "tone_100hz": float(result.tone_100hz) if result.tone_100hz is not None else None,
                "tone_200hz": None,
            }
        )
    historical_df = pd.DataFrame.from_records(
        records, columns=["noise_site_id", "site_name", "datetime", "leq_adj", "tone_100hz", "tone_200hz"]
    )
    for column in ("leq_adj", "tone_100hz", "tone_200hz"):
        historical_df[column] = historical_df[column].astype(float)

    historical_df = _stamp_conductor(
        historical_df, events, filters.conductor_and_treatment, filters.grease
    )
    historical_df = _apply_conductor_filters(
        historical_df, filters.conductor_and_treatment, filters.grease
    )
    historical_df["is_historical"] = True
    # A manually surveyed historical point has no per-reading breakdown.
    historical_df["event_count"] = None
    historical_df["conductor_label"] = [
        _conductor_label(conductor, grease)
        for conductor, grease in zip(
            historical_df["conductor_and_treatment"], historical_df["grease"]
        )
    ]
    return historical_df[BUCKETED_COLUMNS]


def _combine_with_historical(current_df, historical_df):
    if historical_df.empty:
        return current_df
    if current_df.empty:
        return historical_df

    current_df = current_df.copy()
    for site_id in current_df["noise_site_id"].unique():
        site_historical = historical_df.loc[historical_df["noise_site_id"] == site_id]
        if site_historical.empty:
            continue

        # A site's historical (manually-surveyed) data always wins up to its
        # own latest date; automated current-data points only appear after it.
        cutover = site_historical["datetime"].max()
        drop_index = current_df.loc[
            (current_df["noise_site_id"] == site_id) & (current_df["datetime"] <= cutover)
        ].index
        current_df = current_df.drop(index=drop_index)

    combined = pd.concat([historical_df, current_df], ignore_index=True)
    return combined.sort_values("datetime")


def _contiguous_runs(df, columns):
    # Splits an already-ordered dataframe into consecutive runs of rows that
    # share the same values across `columns`, without reordering or
    # collapsing anything - e.g. a site's trace toggling
    # (is_historical, linestyle) between solid/dash and back over time
    # produces 3 runs, not 2, even though "solid" repeats.
    runs = []
    keys = list(df[columns].itertuples(index=False, name=None))
    start = 0
    for position in range(1, len(keys) + 1):
        if position == len(keys) or keys[position] != keys[start]:
            runs.append((keys[start], df.iloc[start:position]))
            start = position
    return runs


def _hover_customdata(run_df):
    # One [count, conductor] pair per point, pre-formatted as strings so a
    # missing value (historical points have no count; readings with no
    # reconductoring event have no conductor) shows a dash, not "undefined".
    return [
        [
            "-" if pd.isna(count) else str(int(count)),
            label or "-",
        ]
        for count, label in zip(run_df["event_count"], run_df["conductor_label"])
    ]


def _build_noise_chart(
    df, parameter, plot_by, group_by_conductor, historical_colors, title_override=None
):
    figure = go.Figure()

    if not df.empty:
        # Explicit per-site color cycling (not Plotly's own implicit
        # per-trace auto-coloring) so a site's historical-segment run can
        # deliberately reuse its current-segment sibling's color.
        site_ids = sorted(df["noise_site_id"].unique())
        site_colors = {
            site_id: SITE_COLOR_PALETTE[index % len(SITE_COLOR_PALETTE)]
            for index, site_id in enumerate(site_ids)
        }

        group_columns = ["noise_site_id"]
        if group_by_conductor:
            group_columns += ["conductor_and_treatment", "grease"]

        for key, group_df in df.sort_values(plot_by).groupby(group_columns):
            key = key if isinstance(key, tuple) else (key,)
            site_id = key[0]

            plot_df = group_df.loc[~group_df[parameter].isna() & ~group_df[plot_by].isna()]
            if plot_df.empty:
                continue

            name = plot_df["site_name"].iloc[0]
            if group_by_conductor:
                conductor_and_treatment = key[1]
                if conductor_and_treatment:
                    name = f"{name} ({conductor_and_treatment})"

            x_title = PLOT_BY_AXIS_TITLES.get(plot_by, "Date")
            hovertemplate = (
                f"{x_title}: %{{x}}<br>{parameter}: %{{y}}"
                "<br>Count: %{customdata[0]}<br>Conductor: %{customdata[1]}"
                "<extra>%{fullData.name}</extra>"
            )
            base_color = site_colors[site_id]
            historical_color = historical_colors.get(site_id) or base_color
            legend_group = f"site-{'-'.join(str(part) for part in key)}"

            for run_index, ((is_historical, linestyle), run_df) in enumerate(
                _contiguous_runs(plot_df, ["is_historical", "linestyle"])
            ):
                color = historical_color if is_historical else base_color
                figure.add_trace(
                    go.Scatter(
                        # Plain Python lists (not numpy-backed pandas Series)
                        # so plotly's JSON encoder emits real arrays rather
                        # than its compact base64 "bdata" typed-array format -
                        # the chart still renders either way, but a plain-
                        # list response is what any generic JSON consumer of
                        # this API expects.
                        x=run_df[plot_by].tolist(),
                        y=run_df[parameter].tolist(),
                        customdata=_hover_customdata(run_df),
                        hovertemplate=hovertemplate,
                        mode="lines+markers",
                        name=name,
                        legendgroup=legend_group,
                        showlegend=run_index == 0,
                        opacity=HISTORICAL_OPACITY if is_historical else 1.0,
                        line=dict(dash=linestyle, color=color),
                        marker=dict(color=color),
                    )
                )

    figure.update_layout(
        title=title_override or "Noise readings over time",
        xaxis_title=PLOT_BY_AXIS_TITLES.get(plot_by, "Date"),
        yaxis_title=parameter,
        height=450,
    )
    return _figure_to_json(figure)


def _build_timeline_chart(availability_rows):
    # availability_rows: [{"noise_site_id", "site_name", "min_datetime",
    # "max_datetime"}, ...], already sorted by noise_site_id - see
    # get_availability_timeline. Deliberately not a pandas DataFrame; the
    # source is already one pre-aggregated row per site, no groupby needed.
    figure = go.Figure()

    if not availability_rows:
        figure.update_layout(title="Data Availability Timeline", height=400)
        return _figure_to_json(figure)

    tickvals = []
    ticktext = []
    for position, row in enumerate(availability_rows):
        label = f"({row['noise_site_id']}) {row['site_name']}"
        color = TIMELINE_COLORS[position % len(TIMELINE_COLORS)]
        figure.add_trace(
            go.Scatter(
                x=[
                    row["min_datetime"],
                    row["max_datetime"],
                    row["max_datetime"],
                    row["min_datetime"],
                    row["min_datetime"],
                ],
                y=[position - 0.4, position - 0.4, position + 0.4, position + 0.4, position - 0.4],
                fill="toself",
                mode="lines",
                line=dict(width=0, color=color),
                name=label,
                showlegend=False,
            )
        )
        tickvals.append(position)
        ticktext.append(label)

    figure.update_layout(
        title="Data Availability Timeline",
        xaxis_title="Date",
        yaxis=dict(tickmode="array", tickvals=tickvals, ticktext=ticktext),
        height=max(400, 40 * len(tickvals)),
        showlegend=False,
    )
    return _figure_to_json(figure)


def get_availability_timeline(
    site_repository: SiteRepository | None = None,
    availability_repository: ReadingAvailabilityRepository | None = None,
):
    # Deliberately decoupled from ChartFilters/every other Charts tab option
    # (site selection, date range, condition, conductor/grease,
    # detection_logic, show_historical) - always shows every active site's
    # full processed_reading history, precomputed in reading_availability
    # (see scripts/generate_reading_availability.py) rather than derived from
    # whatever the noise chart's own request happens to be scoped to.
    site_repository = site_repository or SiteRepository()
    availability_repository = availability_repository or ReadingAvailabilityRepository()

    # list_sites() already excludes ignored sites - the timeline must never
    # show one, same as every other consumer of this repository.
    sites_by_id = {site.noise_site_id: site for site in site_repository.list_sites()}
    rows = [
        {
            "noise_site_id": row.noise_site_id,
            "site_name": sites_by_id[row.noise_site_id].site_name,
            "min_datetime": row.min_datetime,
            "max_datetime": row.max_datetime,
        }
        for row in availability_repository.list_all()
        if row.noise_site_id in sites_by_id
    ]
    rows.sort(key=lambda row: row["noise_site_id"])
    return _build_timeline_chart(rows)


def _fetch_filtered_readings_dataframe(
    filters: ChartFilters, repository, site_repository, events, outages
):
    start_datetime = (
        datetime.combine(filters.start_date, datetime.min.time()) if filters.start_date else None
    )
    end_datetime = (
        datetime.combine(filters.end_date, datetime.max.time()) if filters.end_date else None
    )
    is_wet = CONDITION_TO_IS_WET.get(filters.condition)

    # site_repository.list_sites() excludes ignored sites by default - never
    # query an ignored site's readings, even if explicitly requested by id.
    sites_by_id = {site.noise_site_id: site for site in site_repository.list_sites()}
    active_site_ids = set(sites_by_id)
    requested_site_ids = set(filters.noise_site_id) if filters.noise_site_id else active_site_ids
    site_ids = sorted(requested_site_ids & active_site_ids)

    readings = (
        repository.list_readings(
            site_ids=site_ids,
            start_datetime=start_datetime,
            end_datetime=end_datetime,
            is_wet=is_wet,
            measurement_duration_minutes=filters.measurement_duration,
            detection_logic=filters.detection_logic,
            # Charts gets its own, much higher per-site cap than the
            # repository's own default (used by Trends) - see
            # Settings.CHARTS_PER_SITE_LIMIT.
            per_site_limit=Settings.CHARTS_PER_SITE_LIMIT,
        )
        if site_ids
        else []
    )

    df = _rows_to_dataframe(readings, sites_by_id)
    df = _exclude_outage_windows(df, outages)
    df = _stamp_conductor(df, events, filters.conductor_and_treatment, filters.grease)
    df = _apply_conductor_filters(df, filters.conductor_and_treatment, filters.grease)
    return df, sites_by_id


def get_chart_figures(
    filters: ChartFilters,
    repository: ProcessedReadingRepository | None = None,
    site_repository: SiteRepository | None = None,
    historical_repository: HistoricalResultRepository | None = None,
    reconductoring_repository: ReconductoringRepository | None = None,
    outage_repository: OutageRepository | None = None,
):
    repository = repository or ProcessedReadingRepository()
    site_repository = site_repository or SiteRepository()
    historical_repository = historical_repository or HistoricalResultRepository()
    reconductoring_repository = reconductoring_repository or ReconductoringRepository()
    outage_repository = outage_repository or OutageRepository()

    events = reconductoring_repository.list_events()
    outages = outage_repository.list_outages()
    df, sites_by_id = _fetch_filtered_readings_dataframe(
        filters, repository, site_repository, events, outages
    )

    parameter = filters.parameter if filters.parameter in PARAMETER_COLUMNS else "tone_100hz"
    group_by_conductor = bool(filters.conductor_and_treatment or filters.grease)
    days_since_guard = filters.plot_by == "days_since_conductoring" and not group_by_conductor

    if days_since_guard:
        chart_df = pd.DataFrame(columns=BUCKETED_COLUMNS)
    else:
        bucketed_df = _bucket_readings(df, filters.interval_weeks, group_by_conductor)
        if filters.show_historical:
            historical_df = _historical_dataframe(
                filters, sites_by_id, historical_repository, events
            )
            chart_df = _combine_with_historical(bucketed_df, historical_df)
        else:
            chart_df = bucketed_df

    historical_colors = {
        site_id: site.historical_line_color for site_id, site in sites_by_id.items()
    }
    noise_chart = _build_noise_chart(
        chart_df,
        parameter,
        filters.plot_by,
        group_by_conductor,
        historical_colors,
        title_override=DAYS_SINCE_GUARD_TITLE if days_since_guard else None,
    )
    return noise_chart


def get_chart_table_rows(
    filters: ChartFilters,
    repository: ProcessedReadingRepository | None = None,
    site_repository: SiteRepository | None = None,
    reconductoring_repository: ReconductoringRepository | None = None,
    outage_repository: OutageRepository | None = None,
):
    repository = repository or ProcessedReadingRepository()
    site_repository = site_repository or SiteRepository()
    reconductoring_repository = reconductoring_repository or ReconductoringRepository()
    outage_repository = outage_repository or OutageRepository()

    events = reconductoring_repository.list_events()
    outages = outage_repository.list_outages()
    df, _sites_by_id = _fetch_filtered_readings_dataframe(
        filters, repository, site_repository, events, outages
    )
    return df[TABLE_COLUMNS].to_dict("records")

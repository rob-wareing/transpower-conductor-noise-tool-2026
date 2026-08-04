import json
from datetime import date, datetime

import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio

from transpower_conductor_noise_tool_2026.backend.persistence.repositories.historical_result_repository import (
    HistoricalResultRepository,
)
from transpower_conductor_noise_tool_2026.backend.persistence.repositories.outage_repository import (
    OutageRepository,
)
from transpower_conductor_noise_tool_2026.backend.persistence.repositories.processed_reading_repository import (
    ProcessedReadingRepository,
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
# Default lower bound for the underlying processed_reading query when the
# caller hasn't picked a start date - applied here only (not on
# ChartFilters.start_date itself), so _historical_dataframe's own date
# filtering of pre-2020 HistoricalResult overlay points is unaffected.
DEFAULT_CHART_START_DATE = date(2020, 1, 1)
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
]
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
    return df


def _apply_conductor_filters(df, conductor_and_treatment, grease):
    if conductor_and_treatment:
        df = df.loc[df["conductor_and_treatment"].isin(conductor_and_treatment)]
    if grease:
        df = df.loc[df["grease"].isin(grease)]
    return df


def _build_linestyle_index(events):
    return {
        (event.noise_site_id, event.conductor_and_treatment or "", event.grease or ""): (
            event.plot_linestyle or "solid"
        )
        for event in events
    }


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

    group_columns = ["noise_site_id", "aggregate_date"]
    if group_by_conductor:
        group_columns += ["conductor_and_treatment", "grease"]

    grouped = working.groupby(group_columns)
    aggregated = grouped[["leq_adj", "tone_100hz", "tone_200hz"]].mean()
    aggregated["site_name"] = grouped["site_name"].first()
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


def _build_noise_chart(df, parameter, plot_by, group_by_conductor, linestyles, title_override=None):
    figure = go.Figure()

    if not df.empty:
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
            linestyle = "solid"
            if group_by_conductor:
                conductor_and_treatment, grease = key[1], key[2]
                if conductor_and_treatment:
                    name = f"{name} ({conductor_and_treatment})"
                linestyle = linestyles.get((site_id, conductor_and_treatment, grease), "solid")

            figure.add_trace(
                go.Scatter(
                    # Plain Python lists (not numpy-backed pandas Series) so
                    # plotly's JSON encoder emits real arrays rather than its
                    # compact base64 "bdata" typed-array format - the chart
                    # still renders either way, but a plain-list response is
                    # what any generic JSON consumer of this API expects.
                    x=plot_df[plot_by].tolist(),
                    y=plot_df[parameter].tolist(),
                    mode="lines+markers",
                    name=name,
                    line=dict(dash=linestyle),
                )
            )

    figure.update_layout(
        title=title_override or "Noise readings over time",
        xaxis_title=PLOT_BY_AXIS_TITLES.get(plot_by, "Date"),
        yaxis_title=parameter,
        height=450,
    )
    return _figure_to_json(figure)


def _build_timeline_chart(df):
    figure = go.Figure()

    if df.empty:
        figure.update_layout(title="Data Availability Timeline", height=400)
        return _figure_to_json(figure)

    summary = (
        df.groupby(["noise_site_id", "site_name"], observed=True)["datetime"]
        .agg(["min", "max"])
        .reset_index()
        .sort_values("noise_site_id")
    )

    tickvals = []
    ticktext = []
    for position, row in enumerate(summary.itertuples()):
        label = f"({row.noise_site_id}) {row.site_name}"
        color = TIMELINE_COLORS[position % len(TIMELINE_COLORS)]
        figure.add_trace(
            go.Scatter(
                x=[row.min, row.max, row.max, row.min, row.min],
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


def _fetch_filtered_readings_dataframe(
    filters: ChartFilters, repository, site_repository, events, outages
):
    effective_start_date = filters.start_date or DEFAULT_CHART_START_DATE
    start_datetime = datetime.combine(effective_start_date, datetime.min.time())
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
        historical_df = _historical_dataframe(filters, sites_by_id, historical_repository, events)
        chart_df = _combine_with_historical(bucketed_df, historical_df)

    linestyles = _build_linestyle_index(events)
    noise_chart = _build_noise_chart(
        chart_df,
        parameter,
        filters.plot_by,
        group_by_conductor,
        linestyles,
        title_override=DAYS_SINCE_GUARD_TITLE if days_since_guard else None,
    )
    # The timeline (data-availability) chart always reflects raw reading dates
    # regardless of plot_by/bucketing, but does respect the same site/date/
    # condition/conductor/grease filters as the line chart, matching the old
    # app's own timeline callback.
    timeline_chart = _build_timeline_chart(df)
    return noise_chart, timeline_chart


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

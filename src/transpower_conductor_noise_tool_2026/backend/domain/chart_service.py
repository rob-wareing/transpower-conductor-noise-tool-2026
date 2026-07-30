import json
from datetime import date, datetime

import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio

from transpower_conductor_noise_tool_2026.backend.persistence.repositories.historical_result_repository import (
    HistoricalResultRepository,
)
from transpower_conductor_noise_tool_2026.backend.persistence.repositories.processed_reading_repository import (
    ProcessedReadingRepository,
)
from transpower_conductor_noise_tool_2026.backend.persistence.repositories.site_repository import (
    SiteRepository,
)
from transpower_conductor_noise_tool_2026.shared.contracts import ChartFilters

PARAMETER_COLUMNS = {"leq_adj", "tone_100hz", "tone_200hz"}
CONDITION_TO_IS_WET = {"wet": True, "dry": False}
CHART_COLUMNS = ["noise_site_id", "site_name", "datetime", "leq_adj", "tone_100hz", "tone_200hz"]
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
                "noise_site_id": reading.noise_site_id,
                "site_name": site.site_name if site else str(reading.noise_site_id),
                "datetime": reading.datetime,
                "leq_adj": float(reading.l90) + height_adj_db,
                "tone_100hz": float(reading.tone_100hz),
                "tone_200hz": float(reading.tone_200hz),
                "include": bool(reading.include),
            }
        )
    return pd.DataFrame.from_records(
        records,
        columns=[*CHART_COLUMNS, "include"],
    )


def _shift_sparse_buckets_forward(df):
    # A bucket with too few readings is noisy/underpowered, so its rows get
    # merged into the *next* bucket instead of plotted on their own. The last
    # bucket for a site is never merged forward (there's nothing after it to
    # merge into), so it's left alone even if sparse.
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


def _bucket_readings(df, interval_weeks):
    empty = pd.DataFrame(columns=CHART_COLUMNS)
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

    grouped = working.groupby(["noise_site_id", "aggregate_date"])
    aggregated = grouped[["leq_adj", "tone_100hz", "tone_200hz"]].mean()
    aggregated["site_name"] = grouped["site_name"].first()
    aggregated = aggregated.reset_index().rename(columns={"aggregate_date": "datetime"})
    return aggregated[CHART_COLUMNS]


def _historical_dataframe(filters: ChartFilters, sites_by_id, historical_repository):
    empty = pd.DataFrame(columns=CHART_COLUMNS)
    # HistoricalResult rows are always from wet-condition surveys, per the old
    # app's own hardcoded assumption - excluded entirely for a dry-only filter.
    if filters.condition == "dry":
        return empty

    results = historical_repository.list_results(site_ids=filters.noise_site_id or None)
    records = []
    for result in results:
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
    historical_df = pd.DataFrame.from_records(records, columns=CHART_COLUMNS)
    for column in ("leq_adj", "tone_100hz", "tone_200hz"):
        historical_df[column] = historical_df[column].astype(float)
    return historical_df


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


def _build_noise_chart(df, parameter):
    figure = go.Figure()

    if not df.empty:
        for _site_id, site_df in df.sort_values("datetime").groupby("noise_site_id"):
            figure.add_trace(
                go.Scatter(
                    x=site_df["datetime"],
                    y=site_df[parameter],
                    mode="lines+markers",
                    name=site_df["site_name"].iloc[0],
                )
            )

    figure.update_layout(
        title="Noise readings over time",
        xaxis_title="Date",
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
        df.groupby(["noise_site_id", "site_name"])["datetime"]
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


def get_chart_figures(
    filters: ChartFilters,
    repository: ProcessedReadingRepository | None = None,
    site_repository: SiteRepository | None = None,
    historical_repository: HistoricalResultRepository | None = None,
):
    repository = repository or ProcessedReadingRepository()
    site_repository = site_repository or SiteRepository()
    historical_repository = historical_repository or HistoricalResultRepository()

    start_datetime = (
        datetime.combine(filters.start_date, datetime.min.time()) if filters.start_date else None
    )
    end_datetime = (
        datetime.combine(filters.end_date, datetime.max.time()) if filters.end_date else None
    )
    is_wet = CONDITION_TO_IS_WET.get(filters.condition)

    readings = repository.list_readings(
        site_ids=filters.noise_site_id or None,
        start_datetime=start_datetime,
        end_datetime=end_datetime,
        is_wet=is_wet,
    )
    sites_by_id = {site.noise_site_id: site for site in site_repository.list_sites()}

    df = _rows_to_dataframe(readings, sites_by_id)
    parameter = filters.parameter if filters.parameter in PARAMETER_COLUMNS else "tone_100hz"

    bucketed_df = _bucket_readings(df, filters.interval_weeks)
    historical_df = _historical_dataframe(filters, sites_by_id, historical_repository)
    chart_df = _combine_with_historical(bucketed_df, historical_df)

    noise_chart = _build_noise_chart(chart_df, parameter)
    timeline_chart = _build_timeline_chart(df)
    return noise_chart, timeline_chart

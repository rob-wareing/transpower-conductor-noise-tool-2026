import json
from datetime import datetime

import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio

from transpower_conductor_noise_tool_2026.backend.persistence.repositories.processed_reading_repository import (
    ProcessedReadingRepository,
)
from transpower_conductor_noise_tool_2026.backend.persistence.repositories.site_repository import (
    SiteRepository,
)
from transpower_conductor_noise_tool_2026.shared.contracts import ChartFilters

PARAMETER_COLUMNS = {"leq_adj", "tone_100hz", "tone_200hz"}
CONDITION_TO_IS_WET = {"wet": True, "dry": False}
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
            }
        )
    return pd.DataFrame.from_records(
        records,
        columns=["noise_site_id", "site_name", "datetime", "leq_adj", "tone_100hz", "tone_200hz"],
    )


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
):
    repository = repository or ProcessedReadingRepository()
    site_repository = site_repository or SiteRepository()

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

    noise_chart = _build_noise_chart(df, parameter)
    timeline_chart = _build_timeline_chart(df)
    return noise_chart, timeline_chart

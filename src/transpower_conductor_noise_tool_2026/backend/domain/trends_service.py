import json

import plotly.graph_objects as go
import plotly.io as pio
from plotly.subplots import make_subplots

from transpower_conductor_noise_tool_2026.backend.persistence.repositories.conductor_summary_repository import (
    ConductorSummaryRepository,
)
from transpower_conductor_noise_tool_2026.backend.persistence.repositories.site_repository import (
    SiteRepository,
)

# Backing tables for these don't exist yet - each Trends sub-tab's data will
# come from a separate database table populated by an offline pre-processing
# pipeline that hasn't been built. These stubs exist so the eventual Trends
# sub-tabs (frontend/layout/trends.py) have a stable function to call; real
# querying logic replaces each body once its table exists.


def get_rain_rate_vs_level():
    return []


def get_age_effects():
    return []


CONDUCTOR_SUMMARY_METRICS = ["l90", "tone_100hz", "tone_200hz"]
CONDUCTOR_SUMMARY_METRIC_LABELS = {
    "l90": "L90",
    "tone_100hz": "Tone excess 100Hz",
    "tone_200hz": "Tone excess 200Hz",
}
# dict (not a plain list) so insertion order also serves as the canonical
# stat-name ordering used to rename summarize_conductor_readings' output
# columns below.
CONDUCTOR_SUMMARY_STAT_FUNCS = {
    "mean": "mean",
    "max": "max",
    "min": "min",
    "median": "median",
    "q1": lambda s: s.quantile(0.25),
    "q3": lambda s: s.quantile(0.75),
}


def summarize_conductor_readings(df):
    # df: one row per already-filtered processed_reading (include=1, is_wet=1),
    # with columns noise_site_id, detection_logic, measurement_duration_minutes,
    # l90, tone_100hz, tone_200hz. Returns one row per (noise_site_id,
    # detection_logic, measurement_duration_minutes) combination actually
    # present in df, with mean/max/min/median/q1/q3 for each metric plus
    # sample_count - a combination with zero input rows simply never appears
    # (pandas groupby never invents an empty group), matching
    # conductor_summary's skip-rather-than-NULL design (see CLAUDE.md).
    group_keys = ["noise_site_id", "detection_logic", "measurement_duration_minutes"]
    grouped = df.groupby(group_keys)[CONDUCTOR_SUMMARY_METRICS]

    summary = grouped.agg(list(CONDUCTOR_SUMMARY_STAT_FUNCS.values()))
    summary.columns = [
        f"{metric}_{stat}"
        for metric in CONDUCTOR_SUMMARY_METRICS
        for stat in CONDUCTOR_SUMMARY_STAT_FUNCS
    ]
    summary = summary.round(2)
    summary["sample_count"] = grouped.size()
    return summary.reset_index()


def _figure_to_json(figure):
    # plotly's own encoder handles numpy arrays / pandas Timestamps that the
    # stdlib json module (used by Flask's jsonify) can't serialize - same
    # reasoning as chart_service.py's own _figure_to_json.
    return json.loads(pio.to_json(figure))


def get_conductor_summary(filters, repository=None, site_repository=None):
    # Builds a box plot straight from conductor_summary's stored five-number
    # summary (mean/median/q1/q3/min/max) via Plotly's "precomputed stats"
    # box mode - no raw processed_reading data is refetched here. min/max are
    # used as the whisker fences (lowerfence/upperfence) since the underlying
    # per-reading values aren't retained - a deliberate approximation, not
    # the usual 1.5*IQR fence convention, given only summary stats exist.
    # One subplot per metric (L90, tone_100hz, tone_200hz) sharing an x-axis
    # of sites, since the three metrics live on very different scales and
    # would otherwise squash onto one shared y-axis.
    repository = repository or ConductorSummaryRepository()
    site_repository = site_repository or SiteRepository()

    summaries = repository.list_summaries(
        detection_logic=filters.detection_logic,
        measurement_duration_minutes=filters.measurement_duration_minutes,
    )

    figure = make_subplots(
        rows=len(CONDUCTOR_SUMMARY_METRICS),
        cols=1,
        shared_xaxes=True,
        subplot_titles=[CONDUCTOR_SUMMARY_METRIC_LABELS[metric] for metric in CONDUCTOR_SUMMARY_METRICS],
        vertical_spacing=0.08,
    )

    if not summaries:
        figure.update_layout(
            title=(
                "No conductor summary data for detection_logic="
                f"{filters.detection_logic!r}, measurement_duration_minutes="
                f"{filters.measurement_duration_minutes}"
            ),
            height=900,
        )
        return _figure_to_json(figure)

    summaries = sorted(summaries, key=lambda s: s.noise_site_id)
    sites_by_id = {site.noise_site_id: site for site in site_repository.list_sites()}
    x = [
        f"({s.noise_site_id}) {sites_by_id[s.noise_site_id].site_name if s.noise_site_id in sites_by_id else s.noise_site_id} (n={s.sample_count})"
        for s in summaries
    ]

    for row, metric in enumerate(CONDUCTOR_SUMMARY_METRICS, start=1):
        figure.add_trace(
            go.Box(
                x=x,
                q1=[float(getattr(s, f"{metric}_q1")) for s in summaries],
                median=[float(getattr(s, f"{metric}_median")) for s in summaries],
                q3=[float(getattr(s, f"{metric}_q3")) for s in summaries],
                lowerfence=[float(getattr(s, f"{metric}_min")) for s in summaries],
                upperfence=[float(getattr(s, f"{metric}_max")) for s in summaries],
                mean=[float(getattr(s, f"{metric}_mean")) for s in summaries],
                boxmean=True,
                name=CONDUCTOR_SUMMARY_METRIC_LABELS[metric],
                showlegend=False,
            ),
            row=row,
            col=1,
        )

    figure.update_layout(
        title=(
            f"Conductor summary — detection_logic={filters.detection_logic}, "
            f"measurement_duration_minutes={filters.measurement_duration_minutes}"
        ),
        height=900,
    )
    return _figure_to_json(figure)

import json

import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio

from transpower_conductor_noise_tool_2026.backend.persistence.repositories.conductor_summary_repository import (
    ConductorSummaryRepository,
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

# Rain rate vs level and Conductor summary both operate over the same three
# acoustic metrics; Age effects' backing table doesn't exist yet, so it stays
# a placeholder below.
METRICS = ["l90", "tone_100hz", "tone_200hz"]
METRIC_LABELS = {
    "l90": "L90",
    "tone_100hz": "Tone excess 100Hz",
    "tone_200hz": "Tone excess 200Hz",
}


def _figure_to_json(figure):
    # plotly's own encoder handles numpy arrays / pandas Timestamps that the
    # stdlib json module (used by Flask's jsonify) can't serialize - same
    # reasoning as chart_service.py's own _figure_to_json.
    return json.loads(pio.to_json(figure))


def get_rain_rate_vs_level(filters, repository=None, site_repository=None):
    # Scatter of the selected metric (y) against rain1, the current period's
    # rainfall (x) - one point per raw processed_reading row, one coloured
    # trace per site (Plotly's default per-trace colour cycling, same as
    # chart_service.py's own noise chart - no explicit colours are set).
    # Only include=1 rows count, matching the main Charts tab's own
    # convention (chart_service.py filters to include==True before
    # charting). measurement_duration_minutes is deliberately NOT filtered
    # here, unlike conductor_summary - every duration is shown. is_wet *is*
    # filtered, controlled by filters.include_dry (default False -> is_wet=1
    # only, dry/is_wet=0 points removed; True -> both wet and dry included).
    repository = repository or ProcessedReadingRepository()
    site_repository = site_repository or SiteRepository()
    metric = filters.metric

    readings = repository.list_readings(
        site_ids=filters.noise_site_id,
        detection_logic=filters.detection_logic,
        include=True,
        is_wet=None if filters.include_dry else True,
    )

    figure = go.Figure()

    if not readings:
        figure.update_layout(
            title=f"No processed reading data for detection_logic={filters.detection_logic!r}",
            height=500,
        )
        return _figure_to_json(figure)

    sites_by_id = {site.noise_site_id: site for site in site_repository.list_sites()}
    df = pd.DataFrame(
        [
            {
                "noise_site_id": reading.noise_site_id,
                "site_name": (
                    sites_by_id[reading.noise_site_id].site_name
                    if reading.noise_site_id in sites_by_id
                    else str(reading.noise_site_id)
                ),
                "rain1": float(reading.rain1),
                "value": float(getattr(reading, metric)),
            }
            for reading in readings
        ]
    )

    for noise_site_id, group in df.sort_values("noise_site_id").groupby("noise_site_id"):
        figure.add_trace(
            go.Scatter(
                x=group["rain1"].tolist(),
                y=group["value"].tolist(),
                mode="markers",
                name=f"({noise_site_id}) {group['site_name'].iloc[0]}",
            )
        )

    figure.update_layout(
        title=(
            f"Rain rate vs {METRIC_LABELS[metric]} — "
            f"detection_logic={filters.detection_logic}"
        ),
        xaxis_title="Rain (mm)",
        yaxis_title=METRIC_LABELS[metric],
        height=600,
    )
    return _figure_to_json(figure)


def get_age_effects():
    return []


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
    grouped = df.groupby(group_keys)[METRICS]

    summary = grouped.agg(list(CONDUCTOR_SUMMARY_STAT_FUNCS.values()))
    summary.columns = [
        f"{metric}_{stat}"
        for metric in METRICS
        for stat in CONDUCTOR_SUMMARY_STAT_FUNCS
    ]
    summary = summary.round(2)
    summary["sample_count"] = grouped.size()
    return summary.reset_index()


# The only conductor types this dataset actually uses - anything else (or a
# site with no reconductoring event at all) falls into "Unknown" rather than
# being invented or silently dropped from the chart. Colours are a fixed,
# stable mapping (not Plotly's default per-trace cycling) since the whole
# point is a consistent legend across every metric/filter combination.
CONDUCTOR_TYPES = ["Zebra", "Goat", "Curlew", "Sulphur", "Pheasant", "Chukar"]
CONDUCTOR_COLORS = {
    "Zebra": "#1f77b4",
    "Goat": "#ff7f0e",
    "Curlew": "#2ca02c",
    "Sulphur": "#d62728",
    "Pheasant": "#9467bd",
    "Chukar": "#8c564b",
    "Unknown": "#7f7f7f",
}


def _conductor_group(conductor_and_treatment):
    # First word of conductor_and_treatment (e.g. "Zebra emulsified fat
    # drawn..." -> "Zebra"), matched case-insensitively against the 6 known
    # types. None/blank/unrecognized all fall into "Unknown" - never invented.
    if not conductor_and_treatment or not conductor_and_treatment.strip():
        return "Unknown"
    first_word = conductor_and_treatment.strip().split()[0]
    for name in CONDUCTOR_TYPES:
        if first_word.lower() == name.lower():
            return name
    return "Unknown"


def _latest_conductor_by_site(reconductoring_repository):
    # ReconductoringRepository.list_events() already orders by
    # reconductoring_date descending, so the first event seen per site here
    # is that site's most recent (currently-installed) conductor.
    latest = {}
    for event in reconductoring_repository.list_events():
        latest.setdefault(event.noise_site_id, event.conductor_and_treatment)
    return latest


def get_conductor_summary(filters, repository=None, site_repository=None, reconductoring_repository=None):
    # Builds a single horizontal box plot (one metric at a time, chosen via
    # filters.metric) straight from conductor_summary's stored five-number
    # summary (mean/median/q1/q3/min/max) via Plotly's "precomputed stats"
    # box mode - no raw processed_reading data is refetched here. min/max are
    # used as the whisker fences (lowerfence/upperfence) since the underlying
    # per-reading values aren't retained - a deliberate approximation, not
    # the usual 1.5*IQR fence convention, given only summary stats exist.
    # Sites on the y-axis (orientation="h") so long site-name labels stay
    # readable rather than being crammed onto a shared x-axis.
    #
    # Each box is coloured by its site's current conductor type
    # (CONDUCTOR_TYPES/_conductor_group) - Plotly's box trace has no
    # per-box colour array in precomputed-stats mode, only a per-*trace*
    # colour, so sites are grouped into one go.Box trace per conductor type
    # (plus "Unknown"), each trace covering only the y-categories (sites) in
    # that group. yaxis.categoryorder/categoryarray below is what keeps the
    # overall site ordering correct across those split traces - without it,
    # Plotly would order sites by which trace/group first introduced them,
    # not by noise_site_id.
    repository = repository or ConductorSummaryRepository()
    site_repository = site_repository or SiteRepository()
    reconductoring_repository = reconductoring_repository or ReconductoringRepository()
    metric = filters.metric

    summaries = repository.list_summaries(
        noise_site_id=filters.noise_site_id,
        detection_logic=filters.detection_logic,
        measurement_duration_minutes=filters.measurement_duration_minutes,
    )

    figure = go.Figure()

    if not summaries:
        figure.update_layout(
            title=(
                "No conductor summary data for detection_logic="
                f"{filters.detection_logic!r}, measurement_duration_minutes="
                f"{filters.measurement_duration_minutes}"
            ),
            height=400,
        )
        return _figure_to_json(figure)

    # Sorted descending so the first site ends up at the top of the y-axis,
    # matching top-to-bottom reading order (Plotly's categorical y-axis
    # otherwise plots the first entry at the bottom).
    summaries = sorted(summaries, key=lambda s: s.noise_site_id, reverse=True)
    sites_by_id = {site.noise_site_id: site for site in site_repository.list_sites()}
    latest_conductor = _latest_conductor_by_site(reconductoring_repository)

    y = [
        f"({s.noise_site_id}) {sites_by_id[s.noise_site_id].site_name if s.noise_site_id in sites_by_id else s.noise_site_id} (n={s.sample_count})"
        for s in summaries
    ]
    groups = {label: _conductor_group(latest_conductor.get(s.noise_site_id)) for s, label in zip(summaries, y)}

    for group_name in [*CONDUCTOR_TYPES, "Unknown"]:
        group_summaries = [(s, label) for s, label in zip(summaries, y) if groups[label] == group_name]
        if not group_summaries:
            continue
        figure.add_trace(
            go.Box(
                y=[label for _, label in group_summaries],
                orientation="h",
                q1=[float(getattr(s, f"{metric}_q1")) for s, _ in group_summaries],
                median=[float(getattr(s, f"{metric}_median")) for s, _ in group_summaries],
                q3=[float(getattr(s, f"{metric}_q3")) for s, _ in group_summaries],
                lowerfence=[float(getattr(s, f"{metric}_min")) for s, _ in group_summaries],
                upperfence=[float(getattr(s, f"{metric}_max")) for s, _ in group_summaries],
                mean=[float(getattr(s, f"{metric}_mean")) for s, _ in group_summaries],
                boxmean=True,
                name=group_name,
                fillcolor=CONDUCTOR_COLORS[group_name],
                legendgroup=group_name,
            )
        )

    figure.update_layout(
        title=(
            f"Conductor summary — {METRIC_LABELS[metric]}, "
            f"detection_logic={filters.detection_logic}, "
            f"measurement_duration_minutes={filters.measurement_duration_minutes}"
        ),
        height=max(400, 40 * len(summaries) + 200),
        xaxis_title=METRIC_LABELS[metric],
        yaxis=dict(categoryorder="array", categoryarray=y),
    )
    return _figure_to_json(figure)

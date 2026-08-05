import json

import numpy as np
import pandas as pd
import plotly.colors
import plotly.graph_objects as go
import plotly.io as pio

from transpower_conductor_noise_tool_2026.backend.persistence.repositories.conductor_age_fit_repository import (
    ConductorAgeFitRepository,
)
from transpower_conductor_noise_tool_2026.backend.persistence.repositories.conductor_summary_repository import (
    ConductorSummaryRepository,
)
from transpower_conductor_noise_tool_2026.backend.persistence.repositories.processed_reading_repository import (
    ProcessedReadingRepository,
)
from transpower_conductor_noise_tool_2026.backend.persistence.repositories.rain_rate_fit_repository import (
    RainRateFitRepository,
)
from transpower_conductor_noise_tool_2026.backend.persistence.repositories.reconductoring_repository import (
    ReconductoringRepository,
)
from transpower_conductor_noise_tool_2026.backend.persistence.repositories.site_repository import (
    SiteRepository,
)

# Fixed palette so a site's marker trace and its fit-line trace always get
# the same colour (Plotly's default per-trace colour cycling would otherwise
# desync once fit-line traces are interleaved with marker traces).
SITE_COLOR_PALETTE = plotly.colors.qualitative.Plotly

# Rain rate vs level, Conductor summary, and Age effects all operate over
# the same three acoustic metrics.
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


def get_rain_rate_vs_level(filters, repository=None, site_repository=None, fit_repository=None):
    # Scatter of the selected metric (y) against rain1, the current period's
    # rainfall (x) - one point per raw processed_reading row, one coloured
    # trace per site, explicitly coloured via SITE_COLOR_PALETTE (not
    # Plotly's default per-trace cycling) so each site's marker trace and its
    # fit-line trace below share the same colour.
    # Only include=1 rows count, matching the main Charts tab's own
    # convention (chart_service.py filters to include==True before
    # charting). measurement_duration_minutes is deliberately NOT filtered
    # here, unlike conductor_summary - every duration is shown. is_wet *is*
    # filtered, controlled by filters.include_dry (default False -> is_wet=1
    # only, dry/is_wet=0 points removed; True -> both wet and dry included).
    #
    # Each site with a stored rain_rate_fit row (see compute_rain_rate_fits
    # and scripts/generate_rain_rate_fits.py) also gets a dashed
    # logarithmic best-fit line, precomputed rather than refit on every
    # request - the fit is looked up, never recomputed, here.
    repository = repository or ProcessedReadingRepository()
    site_repository = site_repository or SiteRepository()
    fit_repository = fit_repository or RainRateFitRepository()
    metric = filters.metric

    # site_repository.list_sites() excludes ignored sites by default - never
    # query an ignored site's readings, even if explicitly requested by id.
    sites_by_id = {site.noise_site_id: site for site in site_repository.list_sites()}
    active_site_ids = set(sites_by_id)
    requested_site_ids = set(filters.noise_site_id) if filters.noise_site_id else active_site_ids
    site_ids = sorted(requested_site_ids & active_site_ids)

    readings = (
        repository.list_readings(
            site_ids=site_ids,
            detection_logic=filters.detection_logic,
            include=True,
            is_wet=None if filters.include_dry else True,
        )
        if site_ids
        else []
    )

    figure = go.Figure()

    if not readings:
        figure.update_layout(
            title=f"No processed reading data for detection_logic={filters.detection_logic!r}",
            height=500,
        )
        return _figure_to_json(figure)

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

    fits_by_site = {
        fit.noise_site_id: fit
        for fit in fit_repository.list_fits(
            noise_site_id=filters.noise_site_id,
            detection_logic=filters.detection_logic,
            metric=metric,
        )
    }

    for index, (noise_site_id, group) in enumerate(
        df.sort_values("noise_site_id").groupby("noise_site_id")
    ):
        color = SITE_COLOR_PALETTE[index % len(SITE_COLOR_PALETTE)]
        site_name = group["site_name"].iloc[0]
        legend_group = f"site-{noise_site_id}"
        figure.add_trace(
            go.Scatter(
                x=group["rain1"].tolist(),
                y=group["value"].tolist(),
                mode="markers",
                name=f"({noise_site_id}) {site_name}",
                marker=dict(color=color),
                legendgroup=legend_group,
            )
        )

        fit = fits_by_site.get(noise_site_id)
        if fit is None:
            continue
        wet_rain1 = group.loc[group["rain1"] > 0, "rain1"]
        if wet_rain1.empty:
            continue
        x_fit = np.linspace(wet_rain1.min(), wet_rain1.max(), 30)
        y_fit = float(fit.slope) * np.log(x_fit) + float(fit.intercept)
        figure.add_trace(
            go.Scatter(
                x=x_fit.tolist(),
                y=y_fit.tolist(),
                mode="lines",
                name=f"({noise_site_id}) {site_name} — fit",
                line=dict(color=color, dash="dash"),
                legendgroup=legend_group,
                showlegend=False,
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


def compute_rain_rate_fits(df):
    # df: one row per already-filtered processed_reading (include=1, is_wet=1),
    # columns noise_site_id, detection_logic, rain1, l90, tone_100hz,
    # tone_200hz. For each metric independently, groups by (noise_site_id,
    # detection_logic), fits metric = slope*ln(rain1) + intercept via
    # np.polyfit over rows with rain1 > 0 (log undefined at 0). A group with
    # fewer than 3 qualifying points is skipped entirely - not enough data
    # for a meaningful fit - matching conductor_summary's skip-rather-than-
    # NULL convention (see CLAUDE.md).
    wet = df[df["rain1"] > 0]
    records = []
    for metric in METRICS:
        for (noise_site_id, detection_logic), group in wet.groupby(
            ["noise_site_id", "detection_logic"]
        ):
            if len(group) < 3:
                continue
            log_rain1 = np.log(group["rain1"].to_numpy())
            values = group[metric].to_numpy()
            slope, intercept = np.polyfit(log_rain1, values, 1)
            predicted = slope * log_rain1 + intercept
            ss_res = float(np.sum((values - predicted) ** 2))
            ss_tot = float(np.sum((values - values.mean()) ** 2))
            r_squared = 1 - ss_res / ss_tot if ss_tot > 0 else None
            records.append(
                {
                    "noise_site_id": int(noise_site_id),
                    "detection_logic": detection_logic,
                    "metric": metric,
                    "slope": round(float(slope), 4),
                    "intercept": round(float(intercept), 4),
                    "r_squared": round(r_squared, 4) if r_squared is not None else None,
                    "sample_count": int(len(group)),
                }
            )
    return records


def get_age_effects(filters, repository=None, site_repository=None, fit_repository=None):
    # Scatter of the selected metric (y) against reconductoring_age, the
    # number of days since each row's site had its most recent
    # reconductoring (x) - one point per raw processed_reading row, one
    # coloured trace per site, same structure as get_rain_rate_vs_level.
    # Rows with a NULL reconductoring_age (predate the site's current
    # conductor, or the site has no reconductoring history at all - see
    # scripts/calculate_reconductoring_age.py) are excluded entirely, not
    # just from the fit - "not displayed" per the column's own contract.
    # Only include=1 rows count, matching Rain rate vs level's convention.
    # measurement_duration_minutes is deliberately NOT filtered, same
    # reasoning as Rain rate vs level - every duration is shown.
    #
    # Each site with a stored conductor_age_fit row also gets a dashed
    # logarithmic best-fit line, precomputed rather than refit on every
    # request - the fit is looked up, never recomputed, here.
    repository = repository or ProcessedReadingRepository()
    site_repository = site_repository or SiteRepository()
    fit_repository = fit_repository or ConductorAgeFitRepository()
    metric = filters.metric

    sites_by_id = {site.noise_site_id: site for site in site_repository.list_sites()}
    active_site_ids = set(sites_by_id)
    requested_site_ids = set(filters.noise_site_id) if filters.noise_site_id else active_site_ids
    site_ids = sorted(requested_site_ids & active_site_ids)

    readings = (
        [
            reading
            for reading in repository.list_readings(
                site_ids=site_ids, detection_logic=filters.detection_logic, include=True
            )
            if reading.reconductoring_age is not None
        ]
        if site_ids
        else []
    )

    figure = go.Figure()

    if not readings:
        figure.update_layout(
            title=f"No processed reading data for detection_logic={filters.detection_logic!r}",
            height=500,
        )
        return _figure_to_json(figure)

    df = pd.DataFrame(
        [
            {
                "noise_site_id": reading.noise_site_id,
                "site_name": (
                    sites_by_id[reading.noise_site_id].site_name
                    if reading.noise_site_id in sites_by_id
                    else str(reading.noise_site_id)
                ),
                "reconductoring_age": reading.reconductoring_age,
                "value": float(getattr(reading, metric)),
            }
            for reading in readings
        ]
    )

    fits_by_site = {
        fit.noise_site_id: fit
        for fit in fit_repository.list_fits(
            noise_site_id=filters.noise_site_id,
            detection_logic=filters.detection_logic,
            metric=metric,
        )
    }

    for index, (noise_site_id, group) in enumerate(
        df.sort_values("noise_site_id").groupby("noise_site_id")
    ):
        color = SITE_COLOR_PALETTE[index % len(SITE_COLOR_PALETTE)]
        site_name = group["site_name"].iloc[0]
        legend_group = f"site-{noise_site_id}"
        figure.add_trace(
            go.Scatter(
                x=group["reconductoring_age"].tolist(),
                y=group["value"].tolist(),
                mode="markers",
                name=f"({noise_site_id}) {site_name}",
                marker=dict(color=color),
                legendgroup=legend_group,
            )
        )

        fit = fits_by_site.get(noise_site_id)
        if fit is None:
            continue
        positive_age = group.loc[group["reconductoring_age"] > 0, "reconductoring_age"]
        if positive_age.empty:
            continue
        x_fit = np.linspace(positive_age.min(), positive_age.max(), 30)
        y_fit = float(fit.slope) * np.log(x_fit) + float(fit.intercept)
        figure.add_trace(
            go.Scatter(
                x=x_fit.tolist(),
                y=y_fit.tolist(),
                mode="lines",
                name=f"({noise_site_id}) {site_name} — fit",
                line=dict(color=color, dash="dash"),
                legendgroup=legend_group,
                showlegend=False,
            )
        )

    figure.update_layout(
        title=(
            f"Age effects — {METRIC_LABELS[metric]} — "
            f"detection_logic={filters.detection_logic}"
        ),
        xaxis_title="Days since most recent reconductoring",
        yaxis_title=METRIC_LABELS[metric],
        height=600,
    )
    return _figure_to_json(figure)


def compute_conductor_age_fits(df):
    # df: one row per already-filtered processed_reading (include=1, non-
    # NULL reconductoring_age), columns noise_site_id, detection_logic,
    # reconductoring_age, l90, tone_100hz, tone_200hz. For each metric
    # independently, groups by (noise_site_id, detection_logic), fits
    # metric = slope*ln(reconductoring_age) + intercept via np.polyfit over
    # rows with reconductoring_age > 0 (log undefined at 0 - the row measured
    # on the exact day of reconductoring). A group with fewer than 3
    # qualifying points is skipped entirely - not enough data for a
    # meaningful fit - matching compute_rain_rate_fits' own convention.
    aged = df[df["reconductoring_age"] > 0]
    records = []
    for metric in METRICS:
        for (noise_site_id, detection_logic), group in aged.groupby(
            ["noise_site_id", "detection_logic"]
        ):
            if len(group) < 3:
                continue
            log_age = np.log(group["reconductoring_age"].to_numpy(dtype=float))
            values = group[metric].to_numpy()
            slope, intercept = np.polyfit(log_age, values, 1)
            predicted = slope * log_age + intercept
            ss_res = float(np.sum((values - predicted) ** 2))
            ss_tot = float(np.sum((values - values.mean()) ** 2))
            r_squared = 1 - ss_res / ss_tot if ss_tot > 0 else None
            records.append(
                {
                    "noise_site_id": int(noise_site_id),
                    "detection_logic": detection_logic,
                    "metric": metric,
                    "slope": round(float(slope), 4),
                    "intercept": round(float(intercept), 4),
                    "r_squared": round(r_squared, 4) if r_squared is not None else None,
                    "sample_count": int(len(group)),
                }
            )
    return records


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
    # list_sites() excludes ignored sites by default - drop any summary row
    # for an ignored (or otherwise unknown) site rather than falling back to
    # displaying it under its raw numeric id.
    sites_by_id = {site.noise_site_id: site for site in site_repository.list_sites()}
    summaries = [s for s in summaries if s.noise_site_id in sites_by_id]
    latest_conductor = _latest_conductor_by_site(reconductoring_repository)

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

    y = [f"({s.noise_site_id}) {sites_by_id[s.noise_site_id].site_name} (n={s.sample_count})" for s in summaries]
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

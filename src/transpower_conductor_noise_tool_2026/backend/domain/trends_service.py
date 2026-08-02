# Backing tables for these don't exist yet - each Trends sub-tab's data will
# come from a separate database table populated by an offline pre-processing
# pipeline that hasn't been built. These stubs exist so the eventual Trends
# sub-tabs (frontend/layout/trends.py) have a stable function to call; real
# querying logic replaces each body once its table exists.


def get_rain_rate_vs_level():
    return []


def get_age_effects():
    return []


def get_conductor_summary():
    # Still a placeholder for the *display* side, even though
    # summarize_conductor_readings/conductor_summary (below/the DB table)
    # already produce and store real data - wiring this to actually read from
    # that table is a separate, not-yet-requested follow-up.
    return []


CONDUCTOR_SUMMARY_METRICS = ["l90", "tone_100hz", "tone_200hz"]
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
    # df: one row per already-filtered processed_reading (include=1, is_wet=1,
    # measurement_duration_minutes=15), with columns noise_site_id,
    # detection_logic, l90, tone_100hz, tone_200hz. Returns one row per
    # (noise_site_id, detection_logic) combination actually present in df,
    # with mean/max/min/median/q1/q3 for each metric plus sample_count - a
    # combination with zero input rows simply never appears (pandas groupby
    # never invents an empty group), matching conductor_summary's
    # skip-rather-than-NULL design (see CLAUDE.md).
    group_keys = ["noise_site_id", "detection_logic"]
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

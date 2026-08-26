# Column-visibility configuration for the Sites, Outages, Reconductoring and
# Historical tabs' tables. Pre-populated with every current column visible -
# flip an entry to False to suppress that column from the tab's DataTable
# without touching the tab's own layout code. A column id with no explicit
# entry (e.g. a column added later) defaults to visible.
#
# Scope: this only controls what the DataTable *displays*. CSV export on all
# four tabs builds its file from the DataTable's full row data (every field
# the backend returns for that row), not from COLUMN_DEFS/this config - a
# column suppressed here still appears in the exported CSV.

VISIBLE_COLUMNS: dict[str, dict[str, bool]] = {
    "sites": {
        "noise_site_id": True,
        "site_name": True,
        "site_code": True,
        "plot_color": True,
        "historical_line_color": True,
        "height_adj_db": True,
        "data_folder": True,
        "report_folder": True,
        "latitude": True,
        "longitude": True,
        "is_ignored": True,
    },
    "outages": {
        "noise_site_id": True,
        "outage_type": True,
        "start_datetime": True,
        "end_datetime": True,
        "notes": True,
    },
    "reconductoring": {
        "noise_site_id": True,
        "conductor_and_treatment": True,
        "grease": True,
        "reconductoring_date": True,
        "plot_linestyle": True,
        "notes": True,
        "for_reconductoring_age": True,
    },
    "historical": {
        "noise_site_id": True,
        "period_end_date": True,
        "leq_adj": True,
        "tone_100hz": True,
    },
}


def visible_column_defs(tab_name, column_defs):
    """Filter a COLUMN_DEFS list down to the columns marked visible for
    `tab_name`. A column id with no explicit entry in VISIBLE_COLUMNS
    defaults to visible."""
    visibility = VISIBLE_COLUMNS.get(tab_name, {})
    return [
        (label, col_id, col_type)
        for label, col_id, col_type in column_defs
        if visibility.get(col_id, True)
    ]

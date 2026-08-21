from transpower_conductor_noise_tool_2026.frontend.layout.table_columns_config import (
    VISIBLE_COLUMNS,
    visible_column_defs,
)


def test_visible_column_defs_keeps_everything_visible_by_default():
    column_defs = [("Site ID", "noise_site_id", "numeric"), ("Notes", "notes", "text")]

    result = visible_column_defs("sites", column_defs)

    assert result == column_defs


def test_visible_column_defs_suppresses_a_column_flagged_false():
    column_defs = [("Site ID", "noise_site_id", "numeric"), ("Notes", "notes", "text")]
    VISIBLE_COLUMNS["sites"]["notes"] = False
    try:
        result = visible_column_defs("sites", column_defs)
    finally:
        VISIBLE_COLUMNS["sites"]["notes"] = True

    assert result == [("Site ID", "noise_site_id", "numeric")]


def test_visible_column_defs_defaults_unknown_column_id_to_visible():
    column_defs = [("New Column", "brand_new_column", "text")]

    result = visible_column_defs("sites", column_defs)

    assert result == column_defs


def test_visible_column_defs_defaults_unknown_tab_to_fully_visible():
    column_defs = [("Site ID", "noise_site_id", "numeric")]

    result = visible_column_defs("not-a-real-tab", column_defs)

    assert result == column_defs


def test_every_current_tab_column_is_pre_populated_visible():
    tabs_and_column_ids = {
        "sites": [
            "noise_site_id",
            "site_name",
            "site_code",
            "plot_color",
            "height_adj_db",
            "data_folder",
            "report_folder",
            "latitude",
            "longitude",
            "is_ignored",
        ],
        "outages": ["noise_site_id", "outage_type", "start_datetime", "end_datetime", "notes"],
        "reconductoring": [
            "noise_site_id",
            "conductor_and_treatment",
            "grease",
            "reconductoring_date",
            "notes",
            "for_reconductoring_age",
        ],
        "historical": ["noise_site_id", "period_end_date", "leq_adj", "tone_100hz"],
    }

    for tab_name, column_ids in tabs_and_column_ids.items():
        for column_id in column_ids:
            assert VISIBLE_COLUMNS[tab_name][column_id] is True

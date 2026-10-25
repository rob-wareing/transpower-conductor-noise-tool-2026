from dash import Input, Output, no_update

from ..layout.trends import (
    AGE_EFFECTS_TAB_ID,
    CONDUCTOR_SUMMARY_TAB_ID,
    RAIN_RATE_VS_LEVEL_TAB_ID,
)

# Main tab_id -> the *-init interval that loads that tab's data. Every one of
# these intervals starts disabled=True, so a hidden tab makes no backend calls
# on page load - previously every tab's init interval fired at once, and the
# resulting burst of callbacks (each holding a gunicorn thread while it called
# this same server's API) could use up every thread and stall the whole app
# until the requests timed out (see PLAN.md). The Charts tab is the default tab,
# so chart-init is not listed here and stays enabled from the start.
MAIN_TAB_INIT_INTERVALS = {
    "sites": "sites-init",
    "outages": "outages-init",
    "reconductoring": "reconductoring-init",
    "historical": "historical-init",
    "locations": "locations-init",
    "weather": "weather-init",
}

# Trends sub-tab_id -> init interval; only enabled while the Trends tab itself is active.
TRENDS_TAB_INIT_INTERVALS = {
    RAIN_RATE_VS_LEVEL_TAB_ID: "trends-rain-rate-init",
    AGE_EFFECTS_TAB_ID: "trends-age-effects-init",
    CONDUCTOR_SUMMARY_TAB_ID: "trends-conductor-summary-init",
}


def register_callbacks(dash_app):
    # Enabling an interval is a one-way switch: each has max_intervals=1, so
    # once enabled it fires once and the tab keeps its data for the rest of the
    # page load (same as before - switching back to a tab doesn't refetch).
    for tab_id, interval_id in MAIN_TAB_INIT_INTERVALS.items():
        _register_main_tab(dash_app, tab_id, interval_id)

    for trends_tab_id, interval_id in TRENDS_TAB_INIT_INTERVALS.items():
        _register_trends_tab(dash_app, trends_tab_id, interval_id)


def _register_main_tab(dash_app, tab_id, interval_id):
    @dash_app.callback(
        Output(interval_id, "disabled"),
        Input("main-tabs", "active_tab"),
    )
    def enable_init_interval(active_tab):
        return False if active_tab == tab_id else no_update


def _register_trends_tab(dash_app, trends_tab_id, interval_id):
    @dash_app.callback(
        Output(interval_id, "disabled"),
        Input("main-tabs", "active_tab"),
        Input("trends-tabs", "active_tab"),
    )
    def enable_init_interval(active_tab, active_trends_tab):
        if active_tab == "trends" and active_trends_tab == trends_tab_id:
            return False
        return no_update

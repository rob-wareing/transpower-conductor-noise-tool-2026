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
    return []

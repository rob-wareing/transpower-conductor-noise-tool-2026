import pandas as pd

TIME_RANGE = ("22:00:00", "07:00:00")
MAX_WIND_SPEED = 2.0
MAX_LEQ_L90_DIFF = 2.0

MAX_VALID_WIND_SPEED = 999.9
MAX_VALID_RAIN_FALL = 99.9

RAW_COLUMN_MAP = {
    "date_time": "datetime",
    "Leq": "leq",
    "L90": "l90",
    "80Hz": "leq_80hz",
    "100Hz": "leq_100hz",
    "125Hz": "leq_125hz",
    "160Hz": "leq_160hz",
    "200Hz": "leq_200hz",
    "250Hz": "leq_250hz",
    "Wind": "wind_speed",
    "Dir": "wind_direction",
    "Rain": "rain_mm",
}

READING_COLUMNS = [
    "noise_site_id",
    "datetime",
    "leq",
    "l90",
    "leq_80hz",
    "leq_100hz",
    "leq_125hz",
    "leq_160hz",
    "leq_200hz",
    "leq_250hz",
    "wind_speed",
    "wind_direction",
    "rain_mm",
]

PROCESSED_READING_COLUMNS = [
    "noise_site_id",
    "datetime",
    "l90",
    "tone_100hz",
    "tone_200hz",
    "rain1",
    "rain2",
    "is_wet",
    "include",
]


def rename_raw_columns(df):
    df = df.reset_index().rename(columns=RAW_COLUMN_MAP)
    return df[READING_COLUMNS]


def clean_readings(df):
    df = df.drop_duplicates("datetime").copy()
    df.loc[df["wind_speed"] > MAX_VALID_WIND_SPEED, "wind_speed"] = MAX_VALID_WIND_SPEED
    df.loc[df["rain_mm"] > MAX_VALID_RAIN_FALL, "rain_mm"] = MAX_VALID_RAIN_FALL
    df.loc[df["wind_direction"] > 360, "wind_direction"] = None
    return df


def _shift_down_by_one(series):
    return pd.Series([0] + series.to_list()[:-1], index=series.index)


def _filter_by_time(df):
    # start excluded, end included - matches the old app's include_start=False,
    # include_end=True (that kwarg pair was removed in newer pandas in favour of
    # this single `inclusive` argument). This right-inclusive boundary convention
    # is deliberately kept identical for every detection-logic variant (see
    # processing_service_updated_2026.py's own _filter_by_time) - only the window
    # boundary *times* differ between logics, never which end is inclusive.
    return df.between_time(*TIME_RANGE, inclusive="right")


def _filter_by_wind(df):
    return df.loc[df["wind_speed"] <= MAX_WIND_SPEED]


def _filter_by_leq_l90_diff(df):
    return df.loc[(df["leq"] - df["l90"]) <= MAX_LEQ_L90_DIFF]


def add_tone_columns(df):
    # "tone excess": the center band's level minus the average of its two flanking
    # bands. Not a copy of any raw field. Shared by every detection-logic variant
    # (see processing_service_updated_2026.py) since the formula itself doesn't
    # change between them - only the surrounding filters/thresholds do.
    df["tone_100hz"] = (df["leq_100hz"] - (df["leq_80hz"] + df["leq_125hz"]) / 2).round(2)
    df["tone_200hz"] = (df["leq_200hz"] - (df["leq_160hz"] + df["leq_250hz"]) / 2).round(2)
    return df


def calculate_leq_rmse(row):
    # Placeholder - the NW API's per-period 1-second Leq data isn't parsed or
    # ingested anywhere yet, so there's nothing to compute an RMSE from. Always
    # returns None until that data exists; the real calculation replaces this
    # body then. Lives here (not in either detection-logic module) because
    # it's a property of the raw measurement itself, computed the same way
    # regardless of which detection logic later filters on it.
    return None


def add_leq_rmse(df):
    df["leq_rmse"] = df.apply(calculate_leq_rmse, axis=1)
    return df


def clean_leq_rmse(value):
    # A DataFrame column mixing real leq_rmse floats with missing values (some
    # readings have real RMSE data, others don't) stores the missing ones as
    # float NaN, not Python None - pandas' standard behaviour for a float64
    # column. PyMySQL has no way to represent NaN (it explicitly raises rather
    # than silently converting), so anything about to be written to the DB
    # must go through this first. A uniform all-None column (every value
    # missing) stays as plain None and never needed this - which is why this
    # surfaced only once real, partial RMSE data existed, not before.
    return None if pd.isna(value) else value


def process_readings(readings_df):
    df = readings_df.set_index("datetime")
    df = df.rename(columns={"rain_mm": "rain1"})
    # rain2 = the previous chronological reading's rain1, computed on the full
    # time-ordered series *before* filtering, so it still reflects the true prior
    # reading even if that row is later dropped by the night-time/wind/Leq-L90 filter.
    df["rain2"] = _shift_down_by_one(df["rain1"])

    df = _filter_by_time(df)
    df = _filter_by_wind(df)
    df = _filter_by_leq_l90_diff(df)

    df = add_tone_columns(df)
    df["is_wet"] = (df["rain1"] > 0) | (df["rain2"] > 0)
    df["include"] = True

    return df.reset_index()[PROCESSED_READING_COLUMNS]

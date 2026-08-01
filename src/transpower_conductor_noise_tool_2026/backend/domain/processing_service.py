import numpy as np
import pandas as pd

TIME_RANGE = ("22:00:00", "07:00:00")
MAX_WIND_SPEED = 2.0
MAX_LEQ_L90_DIFF = 2.0

MAX_VALID_WIND_SPEED = 999.9
MAX_VALID_RAIN_FALL = 99.9

# Leq900: the NW API's per-period 1-second Leq series - 900 pipe-separated
# values (900 seconds = the 15-minute measurement_duration_minutes default),
# with missing seconds represented by the literal token "A". See
# calculate_leq_rmse below for what this feeds into.
LEQ900_SEPARATOR = "|"
LEQ900_NULL_TOKEN = "A"
# Below this fraction of valid (non-null, parseable) samples, the fit would be
# built from too sparse a sample of the period to be meaningful - leq_rmse
# stays NULL rather than reporting a number computed from a handful of points.
LEQ900_MIN_VALID_FRACTION = 0.5

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
    "Leq900": "leq900",
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
    "leq900",
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


def _parse_leq900(raw):
    # Splits the raw "41.2|A|43.1|..." string into (position, value) pairs,
    # using each token's index in the *full* split list as its time step (in
    # seconds) - a dropped "A"/unparsable token still leaves a real gap at its
    # position, it doesn't shift later tokens' time values down. Returns the
    # total token count alongside the valid pairs, since the total (not just
    # the valid count) is what LEQ900_MIN_VALID_FRACTION is measured against.
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return 0, []

    tokens = str(raw).split(LEQ900_SEPARATOR)
    points = []
    for position, token in enumerate(tokens):
        token = token.strip()
        if token == "" or token == LEQ900_NULL_TOKEN:
            continue
        try:
            points.append((position, float(token)))
        except ValueError:
            continue
    return len(tokens), points


def calculate_leq_rmse(row):
    # Real calculation: an ordinary-least-squares straight-line fit between
    # each valid 1-second Leq value (from the NW API's Leq900 field) and its
    # time step, then the root-mean-square of that line's residuals. Lives
    # here (not in either detection-logic module) because it's a property of
    # the raw measurement itself, computed the same way regardless of which
    # detection logic later filters on it.
    total, points = _parse_leq900(row.get("leq900"))
    if total == 0 or len(points) < 2 or len(points) < total * LEQ900_MIN_VALID_FRACTION:
        return None

    t = np.array([position for position, _ in points], dtype=float)
    y = np.array([value for _, value in points], dtype=float)
    slope, intercept = np.polyfit(t, y, 1)
    residuals = y - (slope * t + intercept)
    return round(float(np.sqrt(np.mean(residuals ** 2))), 2)


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

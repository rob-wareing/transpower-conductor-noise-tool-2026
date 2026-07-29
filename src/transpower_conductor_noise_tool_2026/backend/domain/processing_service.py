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
    # this single `inclusive` argument).
    return df.between_time(*TIME_RANGE, inclusive="right")


def _filter_by_wind(df):
    return df.loc[df["wind_speed"] <= MAX_WIND_SPEED]


def _filter_by_leq_l90_diff(df):
    return df.loc[(df["leq"] - df["l90"]) <= MAX_LEQ_L90_DIFF]


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

    # "tone excess": the center band's level minus the average of its two flanking
    # bands. Not a copy of any raw field.
    df["tone_100hz"] = (df["leq_100hz"] - (df["leq_80hz"] + df["leq_125hz"]) / 2).round(2)
    df["tone_200hz"] = (df["leq_200hz"] - (df["leq_160hz"] + df["leq_250hz"]) / 2).round(2)
    df["is_wet"] = (df["rain1"] > 0) | (df["rain2"] > 0)
    df["include"] = True

    return df.reset_index()[PROCESSED_READING_COLUMNS]

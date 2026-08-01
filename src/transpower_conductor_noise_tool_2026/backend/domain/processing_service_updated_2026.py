from transpower_conductor_noise_tool_2026.backend.domain import processing_service

# Re-exported rather than redefined: this is a variant of process_readings only -
# raw-column renaming and basic data hygiene (dedup/outlier capping) are shared
# with the original logic, not part of what "detection logic" means.
rename_raw_columns = processing_service.rename_raw_columns
clean_readings = processing_service.clean_readings

TIME_RANGE = ("22:00:00", "05:00:00")
MAX_WIND_SPEED = 1.5
MIN_RAIN_MM = 0.05
MAX_LEQ_RMSE = 0.75

# Same shape as the original, plus leq_rmse - copied across from the raw
# Reading for measurements that pass this logic's filters (see
# process_readings below). The original logic's own PROCESSED_READING_COLUMNS
# has no such field, so "original"-tagged ProcessedReading rows always keep
# leq_rmse = NULL.
PROCESSED_READING_COLUMNS = processing_service.PROCESSED_READING_COLUMNS + ["leq_rmse"]


def _filter_by_time(df):
    # Deliberately keeps the same right-inclusive boundary convention as the
    # original (start excluded, end included) - confirmed correct, not just
    # assumed: only the window's boundary *times* were specified as changing
    # (22:00-07:00 -> 22:00-05:00), never which end is inclusive.
    return df.between_time(*TIME_RANGE, inclusive="right")


def _filter_valid_wind_and_rain(df):
    # "Rain and wind speed are valid" - a row with a missing (null) sensor
    # reading for either can't be judged against the thresholds below at all,
    # so it's dropped here rather than silently passing/failing via a NaN
    # comparison.
    return df.loc[df["wind_speed"].notna() & df["rain1"].notna()]


def _filter_by_wind(df):
    return df.loc[df["wind_speed"] < MAX_WIND_SPEED]


def _filter_by_leq_rmse(df):
    # leq_rmse flows in as a real column (processing_service.add_leq_rmse adds
    # it before this runs), computed from the NW API's Leq900 1-second series
    # (see calculate_leq_rmse) - NULL when that data was missing or too sparse
    # to fit. "If it exists" means a NULL value passes the filter rather than
    # being dropped. The column-missing guard is only a defensive fallback for
    # callers that build a DataFrame directly without going through the
    # standard pipeline (e.g. some of this module's own tests).
    if "leq_rmse" not in df.columns:
        return df
    return df.loc[df["leq_rmse"].isna() | (df["leq_rmse"] <= MAX_LEQ_RMSE)]


def process_readings(readings_df):
    df = readings_df.set_index("datetime")
    df = df.rename(columns={"rain_mm": "rain1"})
    # rain2 is still computed and stored (the table column is not-null and the
    # raw-data table still displays it) but, unlike the original logic, no
    # longer feeds is_wet below - only the current period's rain1 does.
    df["rain2"] = processing_service._shift_down_by_one(df["rain1"])
    # leq_rmse is always present by the time the real ingestion pipeline calls
    # this (processing_service.add_leq_rmse adds it first) - this guards
    # direct callers (mainly this module's own tests) that build a DataFrame
    # without it, since PROCESSED_READING_COLUMNS below always selects it.
    if "leq_rmse" not in df.columns:
        df["leq_rmse"] = None

    df = _filter_by_time(df)
    df = _filter_valid_wind_and_rain(df)
    df = _filter_by_wind(df)
    df = _filter_by_leq_rmse(df)
    # No Leq-L90 diff filter in this logic (removed, not just relaxed).

    df = processing_service.add_tone_columns(df)
    df["is_wet"] = df["rain1"] >= MIN_RAIN_MM
    df["include"] = True

    return df.reset_index()[PROCESSED_READING_COLUMNS]

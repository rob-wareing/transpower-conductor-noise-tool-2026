import pandas as pd

from transpower_conductor_noise_tool_2026.backend.domain import processing_service


def test_rename_raw_columns_maps_api_field_names():
    raw = pd.DataFrame(
        [
            {
                "Leq": 50.0,
                "L90": 48.0,
                "80Hz": 30.0,
                "100Hz": 35.0,
                "125Hz": 31.0,
                "160Hz": 28.0,
                "200Hz": 33.0,
                "250Hz": 29.0,
                "Wind": 1.0,
                "Dir": 180,
                "Rain": 0.0,
                "Leq900": "40.0|41.0|42.0",
                "noise_site_id": 51,
            }
        ],
        index=pd.DatetimeIndex(["2025-01-01T23:00:00"], name="date_time"),
    )

    renamed = processing_service.rename_raw_columns(raw)

    assert list(renamed.columns) == processing_service.READING_COLUMNS
    assert renamed.loc[0, "l90"] == 48.0
    assert renamed.loc[0, "leq_100hz"] == 35.0
    assert renamed.loc[0, "datetime"] == pd.Timestamp("2025-01-01T23:00:00")
    assert renamed.loc[0, "leq900"] == "40.0|41.0|42.0"


def test_clean_readings_clamps_out_of_range_values_and_drops_duplicates():
    df = pd.DataFrame(
        [
            {"datetime": pd.Timestamp("2025-01-01T23:00:00"), "wind_speed": 5000.0,
             "rain_mm": 500.0, "wind_direction": 720},
            {"datetime": pd.Timestamp("2025-01-01T23:00:00"), "wind_speed": 1.0,
             "rain_mm": 0.0, "wind_direction": 90},
        ]
    )

    cleaned = processing_service.clean_readings(df)

    assert len(cleaned) == 1
    assert cleaned.iloc[0]["wind_speed"] == processing_service.MAX_VALID_WIND_SPEED
    assert cleaned.iloc[0]["rain_mm"] == processing_service.MAX_VALID_RAIN_FALL
    assert pd.isna(cleaned.iloc[0]["wind_direction"])


def _reading_row(dt, wind_speed=1.0, leq=50.0, l90=48.0, rain_mm=0.0):
    return {
        "noise_site_id": 51,
        "datetime": pd.Timestamp(dt),
        "leq": leq,
        "l90": l90,
        "leq_80hz": 30.0,
        "leq_100hz": 35.0,
        "leq_125hz": 31.0,
        "leq_160hz": 28.0,
        "leq_200hz": 33.0,
        "leq_250hz": 29.0,
        "wind_speed": wind_speed,
        "wind_direction": 180,
        "rain_mm": rain_mm,
    }


def test_process_readings_filters_and_computes_columns():
    rows = [
        _reading_row("2025-01-01T23:00:00", wind_speed=1.0, leq=50.0, l90=48.0, rain_mm=0.0),
        _reading_row("2025-01-02T06:00:00", wind_speed=1.5, leq=45.0, l90=44.0, rain_mm=1.0),
        _reading_row("2025-01-02T12:00:00", wind_speed=1.0, leq=50.0, l90=48.0, rain_mm=0.0),
        _reading_row("2025-01-02T23:00:00", wind_speed=3.0, leq=50.0, l90=48.0, rain_mm=0.0),
        _reading_row("2025-01-03T06:00:00", wind_speed=1.0, leq=50.0, l90=44.0, rain_mm=0.0),
        _reading_row("2025-01-03T23:00:00", wind_speed=1.0, leq=40.0, l90=39.0, rain_mm=0.0),
    ]
    df = pd.DataFrame(rows)

    result = processing_service.process_readings(df)

    # only rows 1, 2, 6 survive: row 3 is daytime, row 4 exceeds MAX_WIND_SPEED,
    # row 5 exceeds MAX_LEQ_L90_DIFF
    assert list(result["datetime"]) == [
        pd.Timestamp("2025-01-01T23:00:00"),
        pd.Timestamp("2025-01-02T06:00:00"),
        pd.Timestamp("2025-01-03T23:00:00"),
    ]

    first, second, third = result.to_dict("records")

    # tone excess: center band minus average of its two flanking bands
    assert first["tone_100hz"] == 4.5  # 35 - (30+31)/2
    assert first["tone_200hz"] == 4.5  # 33 - (28+29)/2

    # rain2 = previous chronological row's rain1, computed before filtering
    assert first["rain1"] == 0.0 and first["rain2"] == 0.0
    assert second["rain1"] == 1.0 and second["rain2"] == 0.0
    assert third["rain1"] == 0.0 and third["rain2"] == 0.0

    assert first["is_wet"] is False
    assert second["is_wet"] is True
    assert third["is_wet"] is False

    assert (result["include"] == True).all()  # noqa: E712


def test_calculate_leq_rmse_perfectly_linear_series_has_zero_rmse():
    # A perfectly linear series fits its own regression line exactly - zero
    # residuals, zero RMSE.
    row = {"leq900": "10.0|20.0|30.0|40.0|50.0|60.0|70.0|80.0|90.0|100.0"}
    assert processing_service.calculate_leq_rmse(row) == 0.0


def test_calculate_leq_rmse_matches_hand_computed_value():
    # t=[0,1,2], y=[0,0,3] - OLS slope=1.5, intercept=-0.5, residuals
    # [0.5,-1.0,0.5], RMSE=sqrt(0.5)=0.7071... -> rounds to 0.71.
    row = {"leq900": "0|0|3"}
    assert processing_service.calculate_leq_rmse(row) == 0.71


def test_calculate_leq_rmse_null_tokens_keep_their_original_position_as_time():
    # tokens at positions 0..5: "0", A, A, "9", A, "12" - the three valid
    # values sit at t=0, t=3, t=5 (their real position in the 900-token
    # series), not renumbered to t=0,1,2. Hand-computed OLS over
    # t=[0,3,5], y=[0,9,12] gives RMSE=0.8429... -> rounds to 0.84.
    # If the null tokens were instead dropped and the survivors renumbered to
    # t=[0,1,2], the fit would be a different line (slope=6, intercept=1)
    # giving RMSE=sqrt(2)=1.41 instead - a materially different result,
    # confirming positions are preserved rather than compacted.
    row = {"leq900": "0|A|A|9|A|12"}
    assert processing_service.calculate_leq_rmse(row) == 0.84


def test_calculate_leq_rmse_returns_none_when_leq900_missing():
    assert processing_service.calculate_leq_rmse({}) is None
    assert processing_service.calculate_leq_rmse({"leq900": None}) is None


def test_calculate_leq_rmse_returns_none_below_min_valid_fraction():
    # 10 tokens, only 4 valid (40%) - below the 50% LEQ900_MIN_VALID_FRACTION
    # threshold, even though 4 valid points would otherwise be enough to fit.
    row = {"leq900": "1|2|3|4|A|A|A|A|A|A"}
    assert processing_service.calculate_leq_rmse(row) is None


def test_calculate_leq_rmse_returns_none_with_fewer_than_two_tokens():
    row = {"leq900": "42.0"}
    assert processing_service.calculate_leq_rmse(row) is None


def test_add_leq_rmse_adds_a_column_without_disturbing_others():
    # Rows without a "leq900" key (the shape every other processing_service
    # test's _reading_row fixture uses) correctly resolve to None rather than
    # erroring - add_leq_rmse just applies calculate_leq_rmse per row.
    df = pd.DataFrame([_reading_row("2025-01-01T23:00:00"), _reading_row("2025-01-02T23:00:00")])

    result = processing_service.add_leq_rmse(df)

    assert list(result["leq_rmse"]) == [None, None]
    assert result["wind_speed"].tolist() == [1.0, 1.0]


def test_clean_leq_rmse_converts_nan_to_none():
    # A DataFrame column mixing real leq_rmse floats with missing values
    # stores the missing ones as NaN (pandas' standard float64 behaviour),
    # but PyMySQL rejects float('nan') outright - real values must pass
    # through unchanged, and missing ones must become a real None so they
    # bind as SQL NULL instead of erroring.
    df = pd.DataFrame([{"leq_rmse": 0.42}, {"leq_rmse": None}])

    assert processing_service.clean_leq_rmse(df.iloc[0]["leq_rmse"]) == 0.42
    assert processing_service.clean_leq_rmse(df.iloc[1]["leq_rmse"]) is None
    assert processing_service.clean_leq_rmse(None) is None

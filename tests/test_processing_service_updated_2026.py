import pandas as pd

from transpower_conductor_noise_tool_2026.backend.domain import processing_service_updated_2026


def _reading_row(dt, wind_speed=1.0, leq=50.0, l90=48.0, rain_mm=0.0, leq_rmse=None, **overrides):
    row = {
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
    if leq_rmse is not None:
        row["leq_rmse"] = leq_rmse
    row.update(overrides)
    return row


def test_time_window_is_22_to_05_right_inclusive():
    rows = [
        _reading_row("2025-01-01T22:00:00"),  # start excluded
        _reading_row("2025-01-01T23:00:00"),  # inside window
        _reading_row("2025-01-02T05:00:00"),  # end included
        _reading_row("2025-01-02T06:00:00"),  # survived under the 22:00-07:00 original window, not this one
        _reading_row("2025-01-02T12:00:00"),  # daytime
    ]
    result = processing_service_updated_2026.process_readings(pd.DataFrame(rows))

    assert list(result["datetime"]) == [
        pd.Timestamp("2025-01-01T23:00:00"),
        pd.Timestamp("2025-01-02T05:00:00"),
    ]


def test_wind_filter_is_strictly_less_than_1_5():
    rows = [
        _reading_row("2025-01-01T23:00:00", wind_speed=1.49),
        _reading_row("2025-01-01T23:01:00", wind_speed=1.5),
        _reading_row("2025-01-01T23:02:00", wind_speed=1.51),
    ]
    result = processing_service_updated_2026.process_readings(pd.DataFrame(rows))

    assert list(result["datetime"]) == [pd.Timestamp("2025-01-01T23:00:00")]


def test_is_wet_only_considers_the_current_period_not_the_previous_one():
    rows = [
        _reading_row("2025-01-01T23:00:00", rain_mm=0.05),
        _reading_row("2025-01-01T23:15:00", rain_mm=0.0),
    ]
    result = processing_service_updated_2026.process_readings(pd.DataFrame(rows))
    first, second = result.to_dict("records")

    assert first["is_wet"] is True
    # Under the original logic this would be True too (previous period's rain
    # carried over via rain2) - the new logic only looks at rain1.
    assert second["is_wet"] is False
    # rain2 is still computed/stored even though it no longer drives is_wet.
    assert second["rain2"] == 0.05


def test_is_wet_threshold_is_0_05_not_greater_than_zero():
    rows = [
        _reading_row("2025-01-01T23:00:00", rain_mm=0.04),
        _reading_row("2025-01-01T23:15:00", rain_mm=0.05),
    ]
    result = processing_service_updated_2026.process_readings(pd.DataFrame(rows))
    first, second = result.to_dict("records")

    assert first["is_wet"] is False
    assert second["is_wet"] is True


def test_leq_l90_diff_no_longer_filters_anything():
    rows = [_reading_row("2025-01-01T23:00:00", leq=50.0, l90=40.0)]  # diff of 10, would fail the original filter
    result = processing_service_updated_2026.process_readings(pd.DataFrame(rows))

    assert len(result) == 1


def test_missing_wind_or_rain_is_dropped_as_invalid():
    rows = [
        _reading_row("2025-01-01T23:00:00", wind_speed=None),
        _reading_row("2025-01-01T23:15:00", rain_mm=None),
        _reading_row("2025-01-01T23:30:00"),
    ]
    result = processing_service_updated_2026.process_readings(pd.DataFrame(rows))

    assert list(result["datetime"]) == [pd.Timestamp("2025-01-01T23:30:00")]


def test_leq_rmse_column_absent_is_a_no_op():
    rows = [_reading_row("2025-01-01T23:00:00")]  # no leq_rmse key at all, matches the real ingestion shape today
    result = processing_service_updated_2026.process_readings(pd.DataFrame(rows))

    assert len(result) == 1
    assert result.iloc[0]["leq_rmse"] is None


def test_leq_rmse_filters_when_present():
    rows = [
        _reading_row("2025-01-01T23:00:00", leq_rmse=0.75),  # at the cutoff, kept
        _reading_row("2025-01-01T23:15:00", leq_rmse=0.76),  # over the cutoff, dropped
        _reading_row("2025-01-01T23:30:00", leq_rmse=float("nan")),  # missing value, kept ("if it exists")
    ]
    result = processing_service_updated_2026.process_readings(pd.DataFrame(rows))

    assert list(result["datetime"]) == [
        pd.Timestamp("2025-01-01T23:00:00"),
        pd.Timestamp("2025-01-01T23:30:00"),
    ]


def test_leq_rmse_value_is_copied_through_for_surviving_rows():
    rows = [_reading_row("2025-01-01T23:00:00", leq_rmse=0.42)]
    result = processing_service_updated_2026.process_readings(pd.DataFrame(rows))

    assert result.iloc[0]["leq_rmse"] == 0.42


def test_processed_reading_columns_includes_leq_rmse():
    assert "leq_rmse" in processing_service_updated_2026.PROCESSED_READING_COLUMNS


def test_tone_excess_formula_is_unchanged():
    rows = [_reading_row("2025-01-01T23:00:00")]
    result = processing_service_updated_2026.process_readings(pd.DataFrame(rows))

    first = result.iloc[0]
    assert first["tone_100hz"] == 4.5  # 35 - (30+31)/2
    assert first["tone_200hz"] == 4.5  # 33 - (28+29)/2


def test_include_is_always_true():
    rows = [_reading_row("2025-01-01T23:00:00")]
    result = processing_service_updated_2026.process_readings(pd.DataFrame(rows))

    assert (result["include"] == True).all()  # noqa: E712

import pandas as pd

from transpower_conductor_noise_tool_2026.backend.domain import trends_service


def test_get_rain_rate_vs_level_is_a_placeholder_that_returns_empty():
    assert trends_service.get_rain_rate_vs_level() == []


def test_get_age_effects_is_a_placeholder_that_returns_empty():
    assert trends_service.get_age_effects() == []


def test_get_conductor_summary_is_a_placeholder_that_returns_empty():
    assert trends_service.get_conductor_summary() == []


def _rows(noise_site_id, detection_logic, l90_values, tone_100hz_values, tone_200hz_values):
    return [
        {
            "noise_site_id": noise_site_id,
            "detection_logic": detection_logic,
            "l90": l90,
            "tone_100hz": tone_100hz,
            "tone_200hz": tone_200hz,
        }
        for l90, tone_100hz, tone_200hz in zip(l90_values, tone_100hz_values, tone_200hz_values)
    ]


def test_summarize_conductor_readings_computes_hand_verifiable_stats():
    # site 51/"original": 5 evenly-spaced values per metric - clean, hand
    # checkable mean/median/quartiles under pandas' default linear
    # interpolation (h=(n-1)*p): q1 lands exactly on index 1, q3 on index 3.
    rows = _rows(
        51, "original",
        l90_values=[10, 20, 30, 40, 50],
        tone_100hz_values=[1.0, 2.0, 3.0, 4.0, 5.0],
        tone_200hz_values=[0.5, 1.5, 2.5, 3.5, 4.5],
    )
    # Same site, different detection_logic - must produce its own separate
    # row, not get blended with the "original" one above. n=3 exercises the
    # interpolated (non-exact-index) quartile case instead.
    rows += _rows(
        51, "updated_2026",
        l90_values=[100, 200, 300],
        tone_100hz_values=[10.0, 20.0, 30.0],
        tone_200hz_values=[1.0, 2.0, 3.0],
    )
    # A different site, single reading - n=1 edge case: every stat collapses
    # to that one value.
    rows += _rows(137, "original", l90_values=[42.0], tone_100hz_values=[2.2], tone_200hz_values=[1.1])

    df = pd.DataFrame(rows)

    result = trends_service.summarize_conductor_readings(df).set_index(
        ["noise_site_id", "detection_logic"]
    )

    assert len(result) == 3  # exactly the 3 groups present above, nothing invented

    site_51_original = result.loc[(51, "original")]
    assert site_51_original["sample_count"] == 5
    assert site_51_original["l90_mean"] == 30.0
    assert site_51_original["l90_max"] == 50.0
    assert site_51_original["l90_min"] == 10.0
    assert site_51_original["l90_median"] == 30.0
    assert site_51_original["l90_q1"] == 20.0
    assert site_51_original["l90_q3"] == 40.0
    assert site_51_original["tone_100hz_mean"] == 3.0
    assert site_51_original["tone_100hz_q1"] == 2.0
    assert site_51_original["tone_100hz_q3"] == 4.0
    assert site_51_original["tone_200hz_mean"] == 2.5
    assert site_51_original["tone_200hz_q1"] == 1.5
    assert site_51_original["tone_200hz_q3"] == 3.5

    site_51_updated = result.loc[(51, "updated_2026")]
    assert site_51_updated["sample_count"] == 3
    assert site_51_updated["l90_mean"] == 200.0
    assert site_51_updated["l90_median"] == 200.0
    assert site_51_updated["l90_q1"] == 150.0  # interpolated: halfway between 100 and 200
    assert site_51_updated["l90_q3"] == 250.0  # interpolated: halfway between 200 and 300

    site_137 = result.loc[(137, "original")]
    assert site_137["sample_count"] == 1
    for stat in ["mean", "max", "min", "median", "q1", "q3"]:
        assert site_137[f"l90_{stat}"] == 42.0
        assert site_137[f"tone_100hz_{stat}"] == 2.2
        assert site_137[f"tone_200hz_{stat}"] == 1.1


def test_summarize_conductor_readings_omits_combinations_not_present():
    df = pd.DataFrame(_rows(51, "original", [10, 20], [1.0, 2.0], [0.5, 1.0]))

    result = trends_service.summarize_conductor_readings(df)

    assert list(zip(result["noise_site_id"], result["detection_logic"])) == [(51, "original")]

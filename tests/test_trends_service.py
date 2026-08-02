from types import SimpleNamespace

import pandas as pd

from transpower_conductor_noise_tool_2026.backend.domain import trends_service
from transpower_conductor_noise_tool_2026.shared.contracts import ConductorSummaryFilters


def test_get_rain_rate_vs_level_is_a_placeholder_that_returns_empty():
    assert trends_service.get_rain_rate_vs_level() == []


def test_get_age_effects_is_a_placeholder_that_returns_empty():
    assert trends_service.get_age_effects() == []


def _rows(
    noise_site_id,
    detection_logic,
    l90_values,
    tone_100hz_values,
    tone_200hz_values,
    measurement_duration_minutes=15,
):
    return [
        {
            "noise_site_id": noise_site_id,
            "detection_logic": detection_logic,
            "measurement_duration_minutes": measurement_duration_minutes,
            "l90": l90,
            "tone_100hz": tone_100hz,
            "tone_200hz": tone_200hz,
        }
        for l90, tone_100hz, tone_200hz in zip(l90_values, tone_100hz_values, tone_200hz_values)
    ]


def test_summarize_conductor_readings_computes_hand_verifiable_stats():
    # site 51/"original"/15min: 5 evenly-spaced values per metric - clean,
    # hand checkable mean/median/quartiles under pandas' default linear
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
    # Same site+logic as the first group, but a different
    # measurement_duration_minutes - must also produce its own separate row,
    # not get blended with the 15-minute group.
    rows += _rows(
        51, "original",
        l90_values=[1000, 2000],
        tone_100hz_values=[100.0, 200.0],
        tone_200hz_values=[10.0, 20.0],
        measurement_duration_minutes=1,
    )
    # A different site, single reading - n=1 edge case: every stat collapses
    # to that one value.
    rows += _rows(137, "original", l90_values=[42.0], tone_100hz_values=[2.2], tone_200hz_values=[1.1])

    df = pd.DataFrame(rows)

    result = trends_service.summarize_conductor_readings(df).set_index(
        ["noise_site_id", "detection_logic", "measurement_duration_minutes"]
    )

    assert len(result) == 4  # exactly the 4 groups present above, nothing invented

    site_51_original_15min = result.loc[(51, "original", 15)]
    assert site_51_original_15min["sample_count"] == 5
    assert site_51_original_15min["l90_mean"] == 30.0
    assert site_51_original_15min["l90_max"] == 50.0
    assert site_51_original_15min["l90_min"] == 10.0
    assert site_51_original_15min["l90_median"] == 30.0
    assert site_51_original_15min["l90_q1"] == 20.0
    assert site_51_original_15min["l90_q3"] == 40.0
    assert site_51_original_15min["tone_100hz_mean"] == 3.0
    assert site_51_original_15min["tone_100hz_q1"] == 2.0
    assert site_51_original_15min["tone_100hz_q3"] == 4.0
    assert site_51_original_15min["tone_200hz_mean"] == 2.5
    assert site_51_original_15min["tone_200hz_q1"] == 1.5
    assert site_51_original_15min["tone_200hz_q3"] == 3.5

    site_51_updated_15min = result.loc[(51, "updated_2026", 15)]
    assert site_51_updated_15min["sample_count"] == 3
    assert site_51_updated_15min["l90_mean"] == 200.0
    assert site_51_updated_15min["l90_median"] == 200.0
    assert site_51_updated_15min["l90_q1"] == 150.0  # interpolated: halfway between 100 and 200
    assert site_51_updated_15min["l90_q3"] == 250.0  # interpolated: halfway between 200 and 300

    site_51_original_1min = result.loc[(51, "original", 1)]
    assert site_51_original_1min["sample_count"] == 2
    assert site_51_original_1min["l90_mean"] == 1500.0

    site_137 = result.loc[(137, "original", 15)]
    assert site_137["sample_count"] == 1
    for stat in ["mean", "max", "min", "median", "q1", "q3"]:
        assert site_137[f"l90_{stat}"] == 42.0
        assert site_137[f"tone_100hz_{stat}"] == 2.2
        assert site_137[f"tone_200hz_{stat}"] == 1.1


def test_summarize_conductor_readings_omits_combinations_not_present():
    df = pd.DataFrame(_rows(51, "original", [10, 20], [1.0, 2.0], [0.5, 1.0]))

    result = trends_service.summarize_conductor_readings(df)

    assert list(
        zip(result["noise_site_id"], result["detection_logic"], result["measurement_duration_minutes"])
    ) == [(51, "original", 15)]


def _summary_row(noise_site_id, detection_logic, measurement_duration_minutes, sample_count, stats):
    row = SimpleNamespace(
        noise_site_id=noise_site_id,
        detection_logic=detection_logic,
        measurement_duration_minutes=measurement_duration_minutes,
        sample_count=sample_count,
    )
    for metric, (mean, median, q1, q3, lo, hi) in stats.items():
        setattr(row, f"{metric}_mean", mean)
        setattr(row, f"{metric}_median", median)
        setattr(row, f"{metric}_q1", q1)
        setattr(row, f"{metric}_q3", q3)
        setattr(row, f"{metric}_min", lo)
        setattr(row, f"{metric}_max", hi)
    return row


class _FakeConductorSummaryRepository:
    def __init__(self, summaries):
        self._summaries = summaries

    def list_summaries(self, detection_logic=None, measurement_duration_minutes=None):
        return [
            s
            for s in self._summaries
            if (detection_logic is None or s.detection_logic == detection_logic)
            and (
                measurement_duration_minutes is None
                or s.measurement_duration_minutes == measurement_duration_minutes
            )
        ]


class _FakeSiteRepository:
    def __init__(self, sites):
        self._sites = sites

    def list_sites(self):
        return self._sites


def test_get_conductor_summary_builds_one_box_trace_per_metric():
    stats = {
        "l90": (40.0, 41.0, 38.0, 44.0, 35.0, 48.0),
        "tone_100hz": (1.0, 1.2, 0.8, 1.5, 0.5, 2.0),
        "tone_200hz": (0.9, 1.0, 0.7, 1.3, 0.4, 1.8),
    }
    summaries = [_summary_row(51, "original", 15, 23, stats)]
    filters = ConductorSummaryFilters(detection_logic="original", measurement_duration_minutes=15)

    figure = trends_service.get_conductor_summary(
        filters,
        repository=_FakeConductorSummaryRepository(summaries),
        site_repository=_FakeSiteRepository(
            [SimpleNamespace(noise_site_id=51, site_name="Test Site")]
        ),
    )

    assert len(figure["data"]) == 1  # a single chart, not one trace per metric
    trace = figure["data"][0]
    assert trace["orientation"] == "h"
    assert trace["q1"] == [38.0]
    assert trace["median"] == [41.0]
    assert trace["q3"] == [44.0]
    assert trace["lowerfence"] == [35.0]
    assert trace["upperfence"] == [48.0]
    assert trace["mean"] == [40.0]
    assert "Test Site" in trace["y"][0]  # sites on the y-axis, not x
    assert "n=23" in trace["y"][0]


def test_get_conductor_summary_metric_selects_which_stats_are_shown():
    stats = {
        "l90": (40.0, 41.0, 38.0, 44.0, 35.0, 48.0),
        "tone_100hz": (1.0, 1.2, 0.8, 1.5, 0.5, 2.0),
        "tone_200hz": (0.9, 1.0, 0.7, 1.3, 0.4, 1.8),
    }
    summaries = [_summary_row(51, "original", 15, 23, stats)]
    site_repository = _FakeSiteRepository([SimpleNamespace(noise_site_id=51, site_name="Test Site")])

    l90_figure = trends_service.get_conductor_summary(
        ConductorSummaryFilters(metric="l90"),
        repository=_FakeConductorSummaryRepository(summaries),
        site_repository=site_repository,
    )
    tone_100hz_figure = trends_service.get_conductor_summary(
        ConductorSummaryFilters(metric="tone_100hz"),
        repository=_FakeConductorSummaryRepository(summaries),
        site_repository=site_repository,
    )

    assert l90_figure["data"][0]["median"] == [41.0]
    assert tone_100hz_figure["data"][0]["median"] == [1.2]


def test_get_conductor_summary_filters_by_detection_logic_and_duration():
    stats = {
        "l90": (40.0, 41.0, 38.0, 44.0, 35.0, 48.0),
        "tone_100hz": (1.0, 1.2, 0.8, 1.5, 0.5, 2.0),
        "tone_200hz": (0.9, 1.0, 0.7, 1.3, 0.4, 1.8),
    }
    summaries = [
        _summary_row(51, "original", 15, 23, stats),
        _summary_row(51, "updated_2026", 15, 9, stats),
        _summary_row(51, "original", 1, 4, stats),
    ]
    filters = ConductorSummaryFilters(detection_logic="updated_2026", measurement_duration_minutes=15)

    figure = trends_service.get_conductor_summary(
        filters,
        repository=_FakeConductorSummaryRepository(summaries),
        site_repository=_FakeSiteRepository(
            [SimpleNamespace(noise_site_id=51, site_name="Test Site")]
        ),
    )

    assert "n=9" in figure["data"][0]["y"][0]


def test_get_conductor_summary_returns_empty_figure_with_message_when_no_data():
    filters = ConductorSummaryFilters(detection_logic="updated_2026", measurement_duration_minutes=1)

    figure = trends_service.get_conductor_summary(
        filters,
        repository=_FakeConductorSummaryRepository([]),
        site_repository=_FakeSiteRepository([]),
    )

    assert figure["data"] == []
    assert "No conductor summary data" in figure["layout"]["title"]["text"]

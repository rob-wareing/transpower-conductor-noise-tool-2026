from datetime import date
from types import SimpleNamespace

import pandas as pd
import pytest

from transpower_conductor_noise_tool_2026.backend.domain import trends_service
from transpower_conductor_noise_tool_2026.shared.contracts import (
    ConductorSummaryFilters,
    RainRateVsLevelFilters,
)


def test_get_age_effects_is_a_placeholder_that_returns_empty():
    assert trends_service.get_age_effects() == []


def _reading(noise_site_id, detection_logic, rain1, l90, tone_100hz, tone_200hz, is_wet=True):
    return SimpleNamespace(
        noise_site_id=noise_site_id,
        detection_logic=detection_logic,
        rain1=rain1,
        l90=l90,
        tone_100hz=tone_100hz,
        tone_200hz=tone_200hz,
        is_wet=is_wet,
    )


class _FakeProcessedReadingRepository:
    def __init__(self, readings):
        self._readings = readings

    def list_readings(self, site_ids=None, detection_logic=None, include=None, is_wet=None):
        return [
            r
            for r in self._readings
            if (not site_ids or r.noise_site_id in site_ids)
            and (detection_logic is None or r.detection_logic == detection_logic)
            and (is_wet is None or r.is_wet == is_wet)
        ]


def _fit(noise_site_id, detection_logic, metric, slope, intercept):
    return SimpleNamespace(
        noise_site_id=noise_site_id,
        detection_logic=detection_logic,
        metric=metric,
        slope=slope,
        intercept=intercept,
    )


class _FakeRainRateFitRepository:
    def __init__(self, fits=()):
        self._fits = list(fits)

    def list_fits(self, noise_site_id=None, detection_logic=None, metric=None):
        return [
            f
            for f in self._fits
            if (not noise_site_id or f.noise_site_id in noise_site_id)
            and (detection_logic is None or f.detection_logic == detection_logic)
            and (metric is None or f.metric == metric)
        ]


def test_get_rain_rate_vs_level_builds_one_trace_per_site():
    readings = [
        _reading(51, "original", rain1=0.0, l90=40.0, tone_100hz=1.0, tone_200hz=0.5),
        _reading(51, "original", rain1=2.0, l90=44.0, tone_100hz=1.5, tone_200hz=0.8),
        _reading(137, "original", rain1=1.0, l90=38.0, tone_100hz=2.0, tone_200hz=1.0),
    ]
    filters = RainRateVsLevelFilters(detection_logic="original", metric="l90")

    figure = trends_service.get_rain_rate_vs_level(
        filters,
        repository=_FakeProcessedReadingRepository(readings),
        site_repository=_FakeSiteRepository(
            [
                SimpleNamespace(noise_site_id=51, site_name="Site A"),
                SimpleNamespace(noise_site_id=137, site_name="Site B"),
            ]
        ),
        fit_repository=_FakeRainRateFitRepository(),
    )

    assert len(figure["data"]) == 2  # one trace per site
    site_51_trace = figure["data"][0]
    assert site_51_trace["mode"] == "markers"
    assert site_51_trace["x"] == [0.0, 2.0]  # rain1 values
    assert site_51_trace["y"] == [40.0, 44.0]  # l90 values
    assert "Site A" in site_51_trace["name"]

    site_137_trace = figure["data"][1]
    assert site_137_trace["x"] == [1.0]
    assert site_137_trace["y"] == [38.0]
    assert "Site B" in site_137_trace["name"]


def test_get_rain_rate_vs_level_metric_selects_which_values_are_plotted():
    readings = [_reading(51, "original", rain1=1.0, l90=40.0, tone_100hz=2.5, tone_200hz=1.5)]
    site_repository = _FakeSiteRepository([SimpleNamespace(noise_site_id=51, site_name="Site A")])

    l90_figure = trends_service.get_rain_rate_vs_level(
        RainRateVsLevelFilters(metric="l90"),
        repository=_FakeProcessedReadingRepository(readings),
        site_repository=site_repository,
        fit_repository=_FakeRainRateFitRepository(),
    )
    tone_figure = trends_service.get_rain_rate_vs_level(
        RainRateVsLevelFilters(metric="tone_100hz"),
        repository=_FakeProcessedReadingRepository(readings),
        site_repository=site_repository,
        fit_repository=_FakeRainRateFitRepository(),
    )

    assert l90_figure["data"][0]["y"] == [40.0]
    assert tone_figure["data"][0]["y"] == [2.5]


def test_get_rain_rate_vs_level_filters_by_site_and_detection_logic():
    readings = [
        _reading(51, "original", rain1=1.0, l90=40.0, tone_100hz=1.0, tone_200hz=0.5),
        _reading(51, "updated_2026", rain1=1.0, l90=41.0, tone_100hz=1.0, tone_200hz=0.5),
        _reading(137, "original", rain1=1.0, l90=42.0, tone_100hz=1.0, tone_200hz=0.5),
    ]
    filters = RainRateVsLevelFilters(noise_site_id=[51], detection_logic="updated_2026")

    figure = trends_service.get_rain_rate_vs_level(
        filters,
        repository=_FakeProcessedReadingRepository(readings),
        site_repository=_FakeSiteRepository([SimpleNamespace(noise_site_id=51, site_name="Site A")]),
        fit_repository=_FakeRainRateFitRepository(),
    )

    assert len(figure["data"]) == 1
    assert figure["data"][0]["y"] == [41.0]


def test_get_rain_rate_vs_level_excludes_dry_readings_by_default():
    readings = [
        _reading(51, "original", rain1=0.0, l90=40.0, tone_100hz=1.0, tone_200hz=0.5, is_wet=False),
        _reading(51, "original", rain1=2.0, l90=44.0, tone_100hz=1.5, tone_200hz=0.8, is_wet=True),
    ]
    site_repository = _FakeSiteRepository([SimpleNamespace(noise_site_id=51, site_name="Site A")])

    default_figure = trends_service.get_rain_rate_vs_level(
        RainRateVsLevelFilters(),  # include_dry defaults to False
        repository=_FakeProcessedReadingRepository(readings),
        site_repository=site_repository,
        fit_repository=_FakeRainRateFitRepository(),
    )
    assert default_figure["data"][0]["x"] == [2.0]  # only the wet reading

    include_dry_figure = trends_service.get_rain_rate_vs_level(
        RainRateVsLevelFilters(include_dry=True),
        repository=_FakeProcessedReadingRepository(readings),
        site_repository=site_repository,
        fit_repository=_FakeRainRateFitRepository(),
    )
    assert include_dry_figure["data"][0]["x"] == [0.0, 2.0]  # both


def test_get_rain_rate_vs_level_returns_empty_figure_with_message_when_no_data():
    filters = RainRateVsLevelFilters(detection_logic="updated_2026")

    figure = trends_service.get_rain_rate_vs_level(
        filters,
        repository=_FakeProcessedReadingRepository([]),
        site_repository=_FakeSiteRepository([]),
        fit_repository=_FakeRainRateFitRepository(),
    )

    assert figure["data"] == []
    assert "No processed reading data" in figure["layout"]["title"]["text"]


def test_get_rain_rate_vs_level_adds_a_dashed_fit_line_matching_marker_color():
    readings = [
        _reading(51, "original", rain1=1.0, l90=40.0, tone_100hz=1.0, tone_200hz=0.5),
        _reading(51, "original", rain1=2.0, l90=44.0, tone_100hz=1.0, tone_200hz=0.5),
    ]
    fits = [_fit(51, "original", "l90", slope=4.0, intercept=40.0)]
    filters = RainRateVsLevelFilters(detection_logic="original", metric="l90")

    figure = trends_service.get_rain_rate_vs_level(
        filters,
        repository=_FakeProcessedReadingRepository(readings),
        site_repository=_FakeSiteRepository([SimpleNamespace(noise_site_id=51, site_name="Site A")]),
        fit_repository=_FakeRainRateFitRepository(fits),
    )

    assert len(figure["data"]) == 2
    marker_trace, line_trace = figure["data"]
    assert marker_trace["mode"] == "markers"
    assert line_trace["mode"] == "lines"
    assert line_trace["showlegend"] is False
    assert line_trace["line"]["dash"] == "dash"
    assert line_trace["line"]["color"] == marker_trace["marker"]["color"]
    assert line_trace["legendgroup"] == marker_trace["legendgroup"]


def test_get_rain_rate_vs_level_omits_fit_line_when_no_fit_stored():
    readings = [_reading(51, "original", rain1=1.0, l90=40.0, tone_100hz=1.0, tone_200hz=0.5)]
    filters = RainRateVsLevelFilters(detection_logic="original", metric="l90")

    figure = trends_service.get_rain_rate_vs_level(
        filters,
        repository=_FakeProcessedReadingRepository(readings),
        site_repository=_FakeSiteRepository([SimpleNamespace(noise_site_id=51, site_name="Site A")]),
        fit_repository=_FakeRainRateFitRepository(),
    )

    assert len(figure["data"]) == 1  # marker trace only, no fit line


def test_get_rain_rate_vs_level_looks_up_fit_by_selected_metric():
    readings = [_reading(51, "original", rain1=1.0, l90=40.0, tone_100hz=1.0, tone_200hz=0.5)]
    fits = [_fit(51, "original", "tone_100hz", slope=1.0, intercept=1.0)]
    filters = RainRateVsLevelFilters(detection_logic="original", metric="l90")

    figure = trends_service.get_rain_rate_vs_level(
        filters,
        repository=_FakeProcessedReadingRepository(readings),
        site_repository=_FakeSiteRepository([SimpleNamespace(noise_site_id=51, site_name="Site A")]),
        fit_repository=_FakeRainRateFitRepository(fits),
    )

    # A fit exists, but only for tone_100hz - the l90-selected chart shouldn't
    # pick it up.
    assert len(figure["data"]) == 1


def test_compute_rain_rate_fits_recovers_a_known_logarithmic_relationship():
    import numpy as np

    rain1 = np.array([1.0, 2.0, 4.0, 8.0, 16.0])
    true_slope, true_intercept = 5.0, 30.0
    l90 = true_slope * np.log(rain1) + true_intercept
    df = pd.DataFrame(
        {
            "noise_site_id": [51] * 5,
            "detection_logic": ["original"] * 5,
            "rain1": rain1,
            "l90": l90,
            "tone_100hz": l90,
            "tone_200hz": l90,
        }
    )

    records = trends_service.compute_rain_rate_fits(df)
    l90_record = next(r for r in records if r["metric"] == "l90")

    assert l90_record["noise_site_id"] == 51
    assert l90_record["detection_logic"] == "original"
    assert l90_record["sample_count"] == 5
    assert l90_record["slope"] == pytest.approx(true_slope, abs=1e-6)
    assert l90_record["intercept"] == pytest.approx(true_intercept, abs=1e-6)
    assert l90_record["r_squared"] == pytest.approx(1.0, abs=1e-6)


def test_compute_rain_rate_fits_skips_groups_with_fewer_than_three_points():
    df = pd.DataFrame(
        {
            "noise_site_id": [51, 51],
            "detection_logic": ["original", "original"],
            "rain1": [1.0, 2.0],
            "l90": [40.0, 44.0],
            "tone_100hz": [1.0, 1.0],
            "tone_200hz": [0.5, 0.5],
        }
    )

    assert trends_service.compute_rain_rate_fits(df) == []


def test_compute_rain_rate_fits_excludes_zero_and_negative_rain1():
    df = pd.DataFrame(
        {
            "noise_site_id": [51, 51, 51, 51],
            "detection_logic": ["original"] * 4,
            "rain1": [0.0, 1.0, 2.0, 4.0],
            "l90": [40.0, 40.0, 44.0, 48.0],
            "tone_100hz": [1.0, 1.0, 1.0, 1.0],
            "tone_200hz": [0.5, 0.5, 0.5, 0.5],
        }
    )

    records = trends_service.compute_rain_rate_fits(df)
    l90_record = next(r for r in records if r["metric"] == "l90")

    assert l90_record["sample_count"] == 3  # the rain1=0.0 row excluded


def test_compute_rain_rate_fits_separates_detection_logic_groups():
    df = pd.DataFrame(
        {
            "noise_site_id": [51, 51, 51, 51, 51, 51],
            "detection_logic": ["original"] * 3 + ["updated_2026"] * 3,
            "rain1": [1.0, 2.0, 4.0] * 2,
            "l90": [40.0, 44.0, 48.0, 100.0, 110.0, 120.0],
            "tone_100hz": [1.0] * 6,
            "tone_200hz": [0.5] * 6,
        }
    )

    records = trends_service.compute_rain_rate_fits(df)
    l90_records = [r for r in records if r["metric"] == "l90"]

    assert {r["detection_logic"] for r in l90_records} == {"original", "updated_2026"}


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

    def list_summaries(self, noise_site_id=None, detection_logic=None, measurement_duration_minutes=None):
        return [
            s
            for s in self._summaries
            if (not noise_site_id or s.noise_site_id in noise_site_id)
            and (detection_logic is None or s.detection_logic == detection_logic)
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


def _reconductoring_event(noise_site_id, conductor_and_treatment, reconductoring_date):
    return SimpleNamespace(
        noise_site_id=noise_site_id,
        conductor_and_treatment=conductor_and_treatment,
        reconductoring_date=reconductoring_date,
    )


class _FakeReconductoringRepository:
    def __init__(self, events):
        # Real ReconductoringRepository.list_events() orders by
        # reconductoring_date descending - the fake must too, since
        # _latest_conductor_by_site relies on that ordering.
        self._events = sorted(events, key=lambda e: e.reconductoring_date, reverse=True)

    def list_events(self):
        return self._events


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
        reconductoring_repository=_FakeReconductoringRepository([]),
    )

    # No reconductoring event for site 51 -> falls into the "Unknown" colour
    # group - still a single trace/box since it's the only site.
    assert len(figure["data"]) == 1
    trace = figure["data"][0]
    assert trace["orientation"] == "h"
    assert trace["name"] == "Unknown"
    assert trace["fillcolor"] == trends_service.CONDUCTOR_COLORS["Unknown"]
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
    reconductoring_repository = _FakeReconductoringRepository([])

    l90_figure = trends_service.get_conductor_summary(
        ConductorSummaryFilters(metric="l90"),
        repository=_FakeConductorSummaryRepository(summaries),
        site_repository=site_repository,
        reconductoring_repository=reconductoring_repository,
    )
    tone_100hz_figure = trends_service.get_conductor_summary(
        ConductorSummaryFilters(metric="tone_100hz"),
        repository=_FakeConductorSummaryRepository(summaries),
        site_repository=site_repository,
        reconductoring_repository=reconductoring_repository,
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
        reconductoring_repository=_FakeReconductoringRepository([]),
    )

    assert "n=9" in figure["data"][0]["y"][0]


def test_get_conductor_summary_filters_by_site():
    stats = {
        "l90": (40.0, 41.0, 38.0, 44.0, 35.0, 48.0),
        "tone_100hz": (1.0, 1.2, 0.8, 1.5, 0.5, 2.0),
        "tone_200hz": (0.9, 1.0, 0.7, 1.3, 0.4, 1.8),
    }
    summaries = [
        _summary_row(51, "original", 15, 23, stats),
        _summary_row(137, "original", 15, 9, stats),
    ]
    filters = ConductorSummaryFilters(noise_site_id=[51])

    figure = trends_service.get_conductor_summary(
        filters,
        repository=_FakeConductorSummaryRepository(summaries),
        site_repository=_FakeSiteRepository(
            [
                SimpleNamespace(noise_site_id=51, site_name="Site A"),
                SimpleNamespace(noise_site_id=137, site_name="Site B"),
            ]
        ),
        reconductoring_repository=_FakeReconductoringRepository([]),
    )

    assert len(figure["data"]) == 1
    assert "Site A" in figure["data"][0]["y"][0]


def test_get_conductor_summary_returns_empty_figure_with_message_when_no_data():
    filters = ConductorSummaryFilters(detection_logic="updated_2026", measurement_duration_minutes=1)

    figure = trends_service.get_conductor_summary(
        filters,
        repository=_FakeConductorSummaryRepository([]),
        site_repository=_FakeSiteRepository([]),
        reconductoring_repository=_FakeReconductoringRepository([]),
    )

    assert figure["data"] == []
    assert "No conductor summary data" in figure["layout"]["title"]["text"]


def test_get_conductor_summary_colors_boxes_by_latest_conductor_type():
    stats = {
        "l90": (40.0, 41.0, 38.0, 44.0, 35.0, 48.0),
        "tone_100hz": (1.0, 1.2, 0.8, 1.5, 0.5, 2.0),
        "tone_200hz": (0.9, 1.0, 0.7, 1.3, 0.4, 1.8),
    }
    summaries = [
        _summary_row(51, "original", 15, 23, stats),
        _summary_row(137, "original", 15, 9, stats),
        _summary_row(142, "original", 15, 4, stats),  # no reconductoring event at all
    ]
    events = [
        _reconductoring_event(51, "Zebra emulsified fat drawn", date(2020, 1, 1)),
        _reconductoring_event(137, "goat treated", date(2019, 6, 1)),  # lowercase, still matches
    ]

    figure = trends_service.get_conductor_summary(
        ConductorSummaryFilters(),
        repository=_FakeConductorSummaryRepository(summaries),
        site_repository=_FakeSiteRepository(
            [
                SimpleNamespace(noise_site_id=51, site_name="Site A"),
                SimpleNamespace(noise_site_id=137, site_name="Site B"),
                SimpleNamespace(noise_site_id=142, site_name="Site C"),
            ]
        ),
        reconductoring_repository=_FakeReconductoringRepository(events),
    )

    traces_by_name = {trace["name"]: trace for trace in figure["data"]}
    assert set(traces_by_name) == {"Zebra", "Goat", "Unknown"}
    assert any("Site A" in label for label in traces_by_name["Zebra"]["y"])
    assert any("Site B" in label for label in traces_by_name["Goat"]["y"])
    assert any("Site C" in label for label in traces_by_name["Unknown"]["y"])
    assert traces_by_name["Zebra"]["fillcolor"] == trends_service.CONDUCTOR_COLORS["Zebra"]
    assert traces_by_name["Goat"]["fillcolor"] == trends_service.CONDUCTOR_COLORS["Goat"]

    # yaxis category order must list every site so the split-by-colour traces
    # still render in a single, consistent top-to-bottom site order.
    assert figure["layout"]["yaxis"]["categoryorder"] == "array"
    assert len(figure["layout"]["yaxis"]["categoryarray"]) == 3


def test_get_conductor_summary_uses_most_recent_reconductoring_event():
    stats = {
        "l90": (40.0, 41.0, 38.0, 44.0, 35.0, 48.0),
        "tone_100hz": (1.0, 1.2, 0.8, 1.5, 0.5, 2.0),
        "tone_200hz": (0.9, 1.0, 0.7, 1.3, 0.4, 1.8),
    }
    summaries = [_summary_row(51, "original", 15, 23, stats)]
    # Two events for the same site - the later date (Chukar) must win, not
    # whichever happens to be listed first.
    events = [
        _reconductoring_event(51, "Curlew treated", date(2018, 1, 1)),
        _reconductoring_event(51, "Chukar treated", date(2022, 1, 1)),
    ]

    figure = trends_service.get_conductor_summary(
        ConductorSummaryFilters(),
        repository=_FakeConductorSummaryRepository(summaries),
        site_repository=_FakeSiteRepository([SimpleNamespace(noise_site_id=51, site_name="Site A")]),
        reconductoring_repository=_FakeReconductoringRepository(events),
    )

    assert figure["data"][0]["name"] == "Chukar"


def test_conductor_group_matches_first_word_case_insensitively():
    assert trends_service._conductor_group("Sulphur treated conductor") == "Sulphur"
    assert trends_service._conductor_group("pheasant TREATED") == "Pheasant"


def test_conductor_group_falls_back_to_unknown():
    assert trends_service._conductor_group(None) == "Unknown"
    assert trends_service._conductor_group("") == "Unknown"
    assert trends_service._conductor_group("   ") == "Unknown"
    assert trends_service._conductor_group("Copper treated") == "Unknown"  # not one of the 6

import pandas as pd
import pytest

from cloudsim.analysis.comparison import delta_pp, relative_pct
from cloudsim.analysis.completeness import (
    completeness_pct,
    expected_sample_count,
    preview_completeness_pct,
)
from cloudsim.analysis.stats import (
    arithmetic_mean,
    interval_phrase,
    maximum,
    p95,
    percentile_linear,
    stat_bundle,
    stat_phrase,
)

HOUR = 3600


def test_p95_linear_interpolation_is_manually_verifiable():
    values = [10, 20, 30, 40]
    assert percentile_linear(values, 0.95) == pytest.approx(38.5)
    assert p95(values) == pytest.approx(38.5)
    assert p95([5]) == 5
    assert p95([]) is None


def test_p95_matches_pandas_and_excel_percentile_inc():
    values = [3, 7, 11, 19, 22, 31, 44, 57, 63, 70]
    expected = pd.Series(values).quantile(0.95, interpolation="linear")
    assert p95(values) == pytest.approx(expected)


def test_avg_and_max_reject_empty_data_instead_of_zero():
    assert arithmetic_mean([]) is None
    assert maximum([]) is None
    assert arithmetic_mean([10, 20, 30]) == pytest.approx(20)
    assert maximum([10, 20, 30]) == 30
    assert stat_bundle([]) == {"avg": None, "p95": None, "max": None}


def test_source_phrases_never_hide_source_statistic():
    assert interval_phrase(HOUR) == "per jam"
    assert interval_phrase(2 * HOUR) == "per 2 jam"
    assert interval_phrase(24 * HOUR) == "per hari"
    assert interval_phrase(None) == "interval tidak diketahui"
    assert stat_phrase("p95", "average", HOUR) == "P95 rata-rata per jam"
    assert stat_phrase("p95", "maximum", HOUR) == "P95 dari maksimum per jam"
    assert stat_phrase("avg", "maximum", HOUR) == "Rata-rata dari maksimum per jam"
    assert stat_phrase("p95", "other", HOUR, "median per jam") == (
        "P95 dari median per jam"
    )


def test_expected_sample_count_uses_half_open_window():
    assert expected_sample_count(0, 24 * HOUR, HOUR) == 24
    assert expected_sample_count(0, 24 * HOUR + HOUR, HOUR) == 25
    assert expected_sample_count(0, 0, HOUR) is None
    assert expected_sample_count(0, HOUR, None) is None
    assert expected_sample_count(0, HOUR, 0) is None


def test_completeness_is_unavailable_when_interval_unknown():
    assert completeness_pct(10, None) is None
    assert completeness_pct(10, 0) is None


def test_preview_completeness_uses_observed_range_only():
    assert preview_completeness_pct(4, 0, 3 * HOUR, HOUR) == pytest.approx(100)
    assert preview_completeness_pct(3, 0, 3 * HOUR, HOUR) == pytest.approx(75)
    assert preview_completeness_pct(3, 0, 3 * HOUR, None) is None
    assert preview_completeness_pct(0, None, None, HOUR) is None


def test_percentage_point_and_relative_percent_are_separate():
    assert delta_pp(20, 25) == pytest.approx(5)
    assert relative_pct(20, 25) == pytest.approx(25)
    assert delta_pp(None, 25) is None
    assert relative_pct(0, 25) is None
    assert relative_pct(-1, 25) is None

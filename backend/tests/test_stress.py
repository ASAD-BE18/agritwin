import pytest

from app.stress import score


@pytest.mark.parametrize(
    "current,expected_label",
    [
        (18.0, "ok"),  # optimal band lower boundary, inclusive
        (26.0, "ok"),  # optimal band upper boundary, inclusive
        (22.0, "ok"),  # middle of optimal band
        (17.99, "caution"),  # just below optimal -> caution
        (15.0, "caution"),  # caution/stress boundary, caution side (inclusive)
        (26.01, "caution"),  # just above optimal -> caution
        (30.0, "caution"),  # caution/stress boundary, caution side (inclusive)
        (14.99, "stress"),  # just below the stress threshold
        (30.01, "stress"),  # just above the stress threshold
        (5.0, "stress"),
        (40.0, "stress"),
    ],
)
def test_band_boundaries(current, expected_label):
    result = score(current=current, mean_10min=current, rate_c_per_min=0.0, minutes_above_30=0.0)
    assert result.risk_label == expected_label


@pytest.mark.parametrize("current", [17.99, 15.0, 26.01, 30.0, 14.99, 30.01, 5.0, 40.0])
def test_factors_non_empty_for_every_non_ok_label(current):
    result = score(current=current, mean_10min=current, rate_c_per_min=0.0, minutes_above_30=0.0)
    assert result.risk_label != "ok"
    assert len(result.factors) > 0


def test_ok_band_has_no_factors_when_nothing_else_is_wrong():
    result = score(current=22.0, mean_10min=22.0, rate_c_per_min=0.0, minutes_above_30=0.0)
    assert result.risk_label == "ok"
    assert result.factors == []


def test_rate_shock_adds_a_factor_even_within_the_optimal_band():
    result = score(current=22.0, mean_10min=22.0, rate_c_per_min=0.6, minutes_above_30=0.0)
    assert result.risk_label == "ok"
    assert any("°C/min" in f for f in result.factors)
    assert result.risk_score > 0


def test_sustained_high_temp_adds_a_factor_and_raises_score():
    brief = score(current=31.0, mean_10min=31.0, rate_c_per_min=0.0, minutes_above_30=0.0)
    sustained = score(current=31.0, mean_10min=31.0, rate_c_per_min=0.0, minutes_above_30=10.0)
    assert sustained.risk_score > brief.risk_score
    assert any("minutes" in f for f in sustained.factors)


def test_mean_10min_corroboration_factor_only_when_sustained():
    spike = score(current=31.0, mean_10min=20.0, rate_c_per_min=0.0, minutes_above_30=0.0)
    sustained = score(current=31.0, mean_10min=31.0, rate_c_per_min=0.0, minutes_above_30=0.0)
    assert not any("brief sensor spike" in f for f in spike.factors)
    assert any("brief sensor spike" in f for f in sustained.factors)


def test_risk_score_is_within_bounds():
    result = score(current=100.0, mean_10min=100.0, rate_c_per_min=5.0, minutes_above_30=60.0)
    assert 0 <= result.risk_score <= 100

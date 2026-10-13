"""Test multi-source rainfall fusion, accumulations, I-D thresholds, and advisory matrix."""

from datetime import datetime, timezone, timedelta
import pytest
from ewp_p1.common.types import (
    DataStatus,
    RainClass,
    SusceptibilityClass,
    AdvisoryLevel,
)
from ewp_p1.rain.fusion import RainFuser
from ewp_p1.rain.accumulations import RainfallAccumulator
from ewp_p1.rain.id_thresholds import IDThresholdEvaluator
from ewp_p1.rain.matrix import AdvisoryMatrixEngine, categorize_susceptibility


def test_rain_fusion_freshness_evaluation():
    """Verify rainfall staleness logic: > 6h staleness across feeds => UNKNOWN."""
    fuser = RainFuser(max_stale_hours=6.0)
    now = datetime(2026, 10, 13, 12, 0, tzinfo=timezone.utc)

    # 1. Fresh feeds
    fresh_gauge = now - timedelta(hours=1)
    fresh_imerg = now - timedelta(hours=2)
    res_fresh = fuser.evaluate_freshness(fresh_gauge, fresh_imerg, now=now)
    assert res_fresh["status"] == DataStatus.OK.value

    # 2. One feed stale (e.g. gauge stale by 8h, but satellite fresh) -> DEGRADED
    stale_gauge = now - timedelta(hours=8)
    res_degraded = fuser.evaluate_freshness(stale_gauge, fresh_imerg, now=now)
    assert res_degraded["status"] == DataStatus.DEGRADED.value

    # 3. All feeds stale (> 6h) -> UNKNOWN
    stale_imerg = now - timedelta(hours=9)
    res_unknown = fuser.evaluate_freshness(stale_gauge, stale_imerg, now=now)
    assert res_unknown["status"] == DataStatus.UNKNOWN.value


def test_rainfall_accumulations_and_api():
    """Verify rolling sums and API decay."""
    accum = RainfallAccumulator(api_window_days=14, api_decay=0.85)

    hourly = [2.0] * 72  # 2 mm every hour for 72 hours
    sums = accum.compute_rolling_accumulations(hourly)
    assert sums["1h"] == 2.0
    assert sums["3h"] == 6.0
    assert sums["6h"] == 12.0
    assert sums["24h"] == 48.0
    assert sums["72h"] == 144.0

    # API calculation test: 10 mm daily for 3 days
    daily = [10.0, 10.0, 10.0]
    # Day 1: 10 * 0.85^1 = 8.5
    # Day 2: 10 * 0.85^2 = 7.225
    # Day 3: 10 * 0.85^3 = 6.14125
    expected_api = 8.5 + 7.225 + 6.14125
    computed_api = accum.compute_api(daily)
    assert abs(computed_api - expected_api) < 0.1


def test_id_threshold_classification():
    """Verify I-D event classification against Caine 1980 curve."""
    evaluator = IDThresholdEvaluator(alpha=14.82, beta=0.39, watch_multiplier=0.7, extreme_multiplier=1.5)

    # Duration = 10 h -> I_crit = 14.82 * (10^-0.39) = ~6.04 mm/h
    crit_10h = evaluator.compute_threshold_intensity(10.0)
    assert 5.5 < crit_10h < 6.5

    # Low intensity (2 mm/h) -> NORMAL
    c_normal = evaluator.classify_event(10.0, 2.0)
    assert c_normal["rain_class"] == RainClass.NORMAL.value

    # Moderate intensity (5 mm/h) -> WATCH
    c_watch = evaluator.classify_event(10.0, 5.0)
    assert c_watch["rain_class"] == RainClass.WATCH.value

    # Exceeding intensity (7.5 mm/h) -> EXCEEDED
    c_exceeded = evaluator.classify_event(10.0, 7.5)
    assert c_exceeded["rain_class"] == RainClass.EXCEEDED.value

    # Extreme cloudburst (15 mm/h) -> EXTREME
    c_extreme = evaluator.classify_event(10.0, 15.0)
    assert c_extreme["rain_class"] == RainClass.EXTREME.value


def test_regional_advisory_matrix_logic():
    """Test matrix cells matching Section 5.6 Table."""
    engine = AdvisoryMatrixEngine(region_id="R01")

    # LOW susceptibility with NORMAL rain -> NONE
    assert engine.evaluate_cell(SusceptibilityClass.LOW, RainClass.NORMAL) == AdvisoryLevel.NONE

    # LOW susceptibility with EXCEEDED rain -> ADVISORY
    assert engine.evaluate_cell(SusceptibilityClass.LOW, RainClass.EXCEEDED) == AdvisoryLevel.ADVISORY

    # HIGH susceptibility with WATCH rain -> ADVISORY
    assert engine.evaluate_cell(SusceptibilityClass.HIGH, RainClass.WATCH) == AdvisoryLevel.ADVISORY

    # HIGH susceptibility with EXCEEDED rain -> WARNING_CANDIDATE
    assert engine.evaluate_cell(SusceptibilityClass.HIGH, RainClass.EXCEEDED) == AdvisoryLevel.WARNING_CANDIDATE

    # VERY_HIGH susceptibility with EXTREME rain -> WARNING_CANDIDATE
    assert engine.evaluate_cell(SusceptibilityClass.VERY_HIGH, RainClass.EXTREME) == AdvisoryLevel.WARNING_CANDIDATE

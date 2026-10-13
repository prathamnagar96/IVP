"""Test susceptibility training, spatial block CV, calibration, and explainability."""

import numpy as np
import pytest
from ewp_p1.models.susceptibility import SusceptibilityEngine
from ewp_p1.models.explain import check_for_leaky_features, compute_feature_importances
from ewp_p1.models.calibration import Calibrator, compute_reliability_curve


def test_susceptibility_engine_training_and_calibration():
    """Verify that SusceptibilityEngine trains with spatial CV and isotonic calibration."""
    n_samples = 120
    rng = np.random.RandomState(42)

    coords = rng.uniform(0, 30000.0, size=(n_samples, 2))
    unit_ids = [f"SU-R01-{i:06d}" for i in range(n_samples)]
    feature_names = ["slope_mean", "relative_relief", "twi_mean", "lithology_rating"]
    X = rng.normal(0, 1, size=(n_samples, 4))
    # Synthetic label correlated with slope_mean and lithology
    logits = 1.2 * X[:, 0] + 0.8 * X[:, 3] - 0.5
    probs = 1.0 / (1.0 + np.exp(-logits))
    y = (rng.uniform(0, 1, size=n_samples) < probs).astype(int)

    # Completeness mask: all negatives in complete mapped area
    is_complete = np.ones(n_samples, dtype=bool)

    engine = SusceptibilityEngine(
        model_type="logistic",
        cv_block_size_m=10000.0,
        n_splits=3,
        calibration_method="isotonic",
        recall_target=0.85,
        random_state=42,
    )

    result = engine.train_and_validate(
        X=X,
        y=y,
        coords=coords,
        unit_ids=unit_ids,
        feature_names=feature_names,
        is_mapped_complete=is_complete,
    )

    assert "metrics" in result
    metrics = result["metrics"]
    assert metrics["roc_auc"] >= 0.65
    assert metrics["brier_score"] <= 0.30
    assert metrics["operating_threshold"] > 0.0

    # Test predict with uncertainty intervals
    predictions = engine.predict(X[:10])
    assert len(predictions) == 10
    for p in predictions:
        assert 0.0 <= p["s"] <= 1.0
        assert p["s_lo"] <= p["s"] <= p["s_hi"]


def test_leaky_feature_detector():
    """Verify detection of forbidden target-leaking features."""
    clean_features = ["slope_mean", "twi_mean", "elevation_std", "pga_g"]
    assert len(check_for_leaky_features(clean_features)) == 0

    leaky_features = ["slope_mean", "distance_to_inventory", "post_event_ndvi"]
    leaks = check_for_leaky_features(leaky_features)
    assert "distance_to_inventory" in leaks
    assert "post_event_ndvi" in leaks

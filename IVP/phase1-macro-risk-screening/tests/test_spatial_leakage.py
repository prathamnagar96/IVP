"""Spatial leakage prevention and spatial block cross-validation test (Section 5.4, 9)."""

import numpy as np
import pytest
from ewp_p1.models.spatial_cv import SpatialBlockCV, verify_no_spatial_leakage


def test_spatial_block_cv_no_leakage():
    """Verify that SpatialBlockCV produces strictly disjoint train and test unit sets."""
    n_units = 200
    # Simulate coordinates over a 50 km x 50 km area (50000 m)
    rng = np.random.RandomState(42)
    coords = rng.uniform(0, 50000.0, size=(n_units, 2))
    unit_ids = [f"SU-R01-{i:06d}" for i in range(n_units)]
    X = rng.normal(0, 1, size=(n_units, 5))
    y = rng.choice([0, 1], size=n_units)

    cv = SpatialBlockCV(block_size_m=10000.0, n_splits=5, random_state=42)

    fold_count = 0
    tested_units = set()

    for train_idx, test_idx in cv.split(X, y, coords):
        # Assert no intersection between train and test
        assert verify_no_spatial_leakage(train_idx, test_idx, unit_ids) is True

        train_set = set(np.array(unit_ids)[train_idx])
        test_set = set(np.array(unit_ids)[test_idx])
        assert len(train_set.intersection(test_set)) == 0

        tested_units.update(test_set)
        fold_count += 1

    assert fold_count == 5
    # All units must have been evaluated in exactly one test fold
    assert len(tested_units) == n_units


def test_leakage_detector_catches_intersection():
    """Leakage verifier must raise AssertionError if overlapping unit IDs are passed."""
    unit_ids = ["SU-01", "SU-02", "SU-03", "SU-04"]
    train_idx = np.array([0, 1, 2])
    test_idx = np.array([2, 3])  # SU-03 overlaps!

    with pytest.raises(AssertionError, match="Spatial leakage detected"):
        verify_no_spatial_leakage(train_idx, test_idx, unit_ids)

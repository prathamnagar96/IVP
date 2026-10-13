"""Property-based and architectural invariant tests (Section 1, 9).

Invariants:
- I1: No hard '0% risk' class. Every unit gets a score and a data_status.
- I2: Missing or low-quality data => UNKNOWN, never 'safe'.
- Invariant property: data_status == UNKNOWN => lane != NONE.
- I5: Same inputs + seed => identical output hash.
"""

import numpy as np
import pytest
from ewp_p1.common.types import DataStatus, Lane
from ewp_p1.common.lineage import compute_hash
from ewp_p1.quality.unknown_logic import QualityEvaluator
from ewp_p1.queue.lanes import LaneAssigner
from ewp_p1.queue.capacity import CapacityManager


def test_invariant_i1_every_unit_has_score_and_status():
    """Invariant I1: Every slope unit must have a score and a data_status."""
    evaluator = QualityEvaluator()
    sample_qualities = {
        "deformation": {"status": "OK", "reason": ""},
        "optical": {"status": "OK", "reason": ""},
        "rainfall": {"status": "OK", "reason": ""},
        "structure": {"status": "OK", "reason": ""},
    }
    res = evaluator.evaluate_unit_data_status(sample_qualities)
    assert res["data_status"] in ["OK", "DEGRADED", "UNKNOWN"]
    assert res["data_status"] is not None


def test_invariant_i2_missing_data_never_safe():
    """Invariant I2: Missing critical data must yield UNKNOWN, never safe."""
    evaluator = QualityEvaluator()

    # Structure attitude data is missing entirely
    qualities_missing_struct = {
        "deformation": {"status": "OK", "reason": ""},
        "optical": {"status": "OK", "reason": ""},
        "rainfall": {"status": "OK", "reason": ""},
        # Structure omitted
    }

    res = evaluator.evaluate_unit_data_status(qualities_missing_struct)
    assert res["data_status"] == DataStatus.UNKNOWN.value
    assert any("structure" in r for r in res["unknown_reasons"])


def test_property_unknown_implies_lane_not_none():
    """Property test: For ANY simulated unit with data_status == UNKNOWN, assigned lane is NEVER NONE."""
    lane_assigner = LaneAssigner()
    capacity_mgr = CapacityManager()

    rng = np.random.RandomState(42)

    # Test 500 randomly simulated scenarios where data_status is UNKNOWN
    for i in range(500):
        risk = float(rng.uniform(0.0, 1.0))
        s = float(rng.uniform(0.0, 1.0))
        exposure = float(rng.uniform(0.0, 1.0))
        has_ada = bool(rng.choice([True, False]))

        initial_lane = lane_assigner.evaluate_initial_lane(
            risk=risk,
            susceptibility=s,
            exposure=exposure,
            has_ada=has_ada,
            data_status=DataStatus.UNKNOWN,
        )

        assert initial_lane != Lane.NONE, (
            f"Failed on initial assignment: risk={risk}, s={s}, exp={exposure}"
        )

        # Also test after capacity manager quota enforcement
        candidate_item = {
            "unit_id": f"SU-TEST-{i}",
            "risk": risk,
            "lane": initial_lane,
            "data_status": DataStatus.UNKNOWN,
        }

        quota_result = capacity_mgr.enforce_quotas([candidate_item])
        final_lane = quota_result[0]["lane"]

        assert final_lane != Lane.NONE, (
            f"Failed after capacity enforcement: final_lane={final_lane}"
        )


def test_invariant_i5_reproducibility_hash():
    """Invariant I5: Same inputs + seed must produce identical output hash."""
    dataset_a = {
        "unit_id": "SU-R01-000100",
        "features": [0.45, 12.5, 120.0, 0.85],
        "seed": 42,
    }
    dataset_b = {
        "unit_id": "SU-R01-000100",
        "features": [0.45, 12.5, 120.0, 0.85],
        "seed": 42,
    }

    hash_a = compute_hash(dataset_a)
    hash_b = compute_hash(dataset_b)

    assert hash_a == hash_b
    assert len(hash_a) == 64  # SHA-256

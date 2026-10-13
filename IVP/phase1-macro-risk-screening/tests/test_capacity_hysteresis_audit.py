"""Test capacity quotas, hysteresis smoothing, and audit sampling."""

import pytest
from ewp_p1.common.types import Lane, DataStatus
from ewp_p1.queue.capacity import CapacityManager
from ewp_p1.queue.hysteresis import HysteresisManager
from ewp_p1.queue.audit import AuditSampler, estimate_miss_rate


def test_capacity_quotas_and_spillover():
    """Verify lane quota capping (INSTRUMENT <= 20, DRONE_BASELINE <= 50)."""
    quotas = {"INSTRUMENT": 5, "DRONE_BASELINE": 10, "RESCREEN": 20}
    mgr = CapacityManager(quotas)

    # 15 units all qualified for INSTRUMENT
    candidates = []
    for i in range(15):
        candidates.append({
            "unit_id": f"SU-{i:03d}",
            "risk": 0.90 - i * 0.02,
            "lane": Lane.INSTRUMENT,
            "data_status": DataStatus.OK,
        })

    assigned = mgr.enforce_quotas(candidates)

    inst_count = sum(1 for u in assigned if u["lane"] == Lane.INSTRUMENT)
    drone_count = sum(1 for u in assigned if u["lane"] == Lane.DRONE_BASELINE)

    # Top 5 must get INSTRUMENT
    assert inst_count == 5
    # Next 10 spillover into DRONE_BASELINE
    assert drone_count == 10


def test_hysteresis_smoothing_and_event_bypass():
    """Test multi-cycle persistence requirement and event trigger bypass."""
    h_mgr = HysteresisManager(persistence_cycles=2)
    unit_id = "SU-001"

    # Cycle 1: Currently NONE, proposed DRONE_BASELINE -> needs 2 cycles, so stays NONE
    lane_c1 = h_mgr.apply_hysteresis(
        unit_id=unit_id,
        current_lane=Lane.NONE,
        proposed_lane=Lane.DRONE_BASELINE,
        event_trigger_active=False,
    )
    assert lane_c1 == Lane.NONE

    # Cycle 2: Proposed DRONE_BASELINE again (2nd cycle) -> Promoted!
    lane_c2 = h_mgr.apply_hysteresis(
        unit_id=unit_id,
        current_lane=Lane.NONE,
        proposed_lane=Lane.DRONE_BASELINE,
        event_trigger_active=False,
    )
    assert lane_c2 == Lane.DRONE_BASELINE

    # Acute event trigger active: bypasses hysteresis immediately
    unit_id2 = "SU-002"
    lane_bypass = h_mgr.apply_hysteresis(
        unit_id=unit_id2,
        current_lane=Lane.NONE,
        proposed_lane=Lane.INSTRUMENT,
        event_trigger_active=True,
    )
    assert lane_bypass == Lane.INSTRUMENT


def test_audit_sampling_and_miss_rate_estimation():
    """Test audit sampling of NONE units and Wilson score interval."""
    sampler = AuditSampler(sample_pct=10.0, random_seed=42)

    none_units = [{"unit_id": f"SU-N-{i}", "lane": Lane.NONE, "risk": 0.05} for i in range(100)]
    audit_sample, remaining_none = sampler.draw_audit_sample(none_units)

    assert len(audit_sample) == 10
    assert len(remaining_none) == 90
    assert all(u["lane"] == Lane.AUDIT for u in audit_sample)

    # Miss rate calculation: out of 50 audited units, 2 had signs of creep/failure
    stats = estimate_miss_rate(audited_count=50, false_negatives_found=2)
    assert stats["miss_rate"] == 0.04
    assert stats["ci_lower"] < 0.04 < stats["ci_upper"]
    assert stats["ci_lower"] >= 0.0

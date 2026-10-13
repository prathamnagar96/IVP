"""Audit loop, stratified sampling, and miss-rate estimation (Section 5.10, 9).

Draws a stratified random sample of unflagged (NONE) units to inspect for false negatives,
estimating regional miss rate with Wilson score confidence intervals.
"""

from typing import List, Dict, Any, Tuple
import numpy as np
from ..common.types import Lane


class AuditSampler:
    def __init__(self, sample_pct: float = 5.0, random_seed: int = 42):
        self.sample_pct = sample_pct
        self.seed = random_seed

    def draw_audit_sample(
        self, candidate_none_units: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Draw stratified random sample from units assigned to NONE lane.

        Returns (audit_units, remaining_none_units).
        """
        if not candidate_none_units:
            return [], []

        n_total = len(candidate_none_units)
        n_sample = max(1, int(np.round(n_total * (self.sample_pct / 100.0))))
        n_sample = min(n_sample, n_total)

        rng = np.random.RandomState(self.seed)
        shuffled_indices = rng.permutation(n_total)

        audit_indices = set(shuffled_indices[:n_sample])

        audit_units = []
        remaining_none = []

        for i, u in enumerate(candidate_none_units):
            if i in audit_indices:
                u_audit = dict(u)
                u_audit["lane"] = Lane.AUDIT
                audit_units.append(u_audit)
            else:
                remaining_none.append(u)

        return audit_units, remaining_none


def estimate_miss_rate(
    audited_count: int, false_negatives_found: int, confidence: float = 0.95
) -> Dict[str, Any]:
    """Calculate empirical miss rate and Wilson score 95% confidence interval."""
    if audited_count == 0:
        return {"miss_rate": 0.0, "ci_lower": 0.0, "ci_upper": 0.0, "audited_count": 0}

    p_hat = false_negatives_found / audited_count
    z = 1.96  # for 95% confidence
    n = audited_count

    # Wilson score interval
    denominator = 1.0 + (z**2) / n
    center_adj = p_hat + (z**2) / (2.0 * n)
    margin = z * np.sqrt((p_hat * (1.0 - p_hat) / n) + (z**2) / (4.0 * (n**2)))

    ci_lower = max(0.0, (center_adj - margin) / denominator)
    ci_upper = min(1.0, (center_adj + margin) / denominator)

    return {
        "miss_rate": round(float(p_hat), 4),
        "ci_lower": round(float(ci_lower), 4),
        "ci_upper": round(float(ci_upper), 4),
        "audited_count": audited_count,
        "false_negatives": false_negatives_found,
    }

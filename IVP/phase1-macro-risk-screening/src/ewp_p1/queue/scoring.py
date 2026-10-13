"""Hazard and Risk scoring engine (Section 5.10).

H = S                       if no ADA
H = max(S, h_active)        if ADA present
R = H * E * V               (Risk used for priority ranking only)
"""

from typing import Dict, Any, Tuple
import numpy as np


class RiskScoringEngine:
    def __init__(self, h_active: float = 0.60):
        self.h_active = h_active

    def compute_hazard(self, s_score: float, has_ada: bool) -> float:
        """Calculate hazard score H from susceptibility and active deformation evidence."""
        if has_ada:
            return float(max(s_score, self.h_active))
        return float(s_score)

    def compute_risk(
        self,
        hazard: float,
        exposure: float,
        vulnerability: float,
        s_lo: float,
        s_hi: float,
        has_ada: bool,
    ) -> Dict[str, Any]:
        """Compute point risk and risk uncertainty interval [r_lo, r_hi]."""
        risk = hazard * exposure * vulnerability

        h_lo = self.compute_hazard(s_lo, has_ada)
        h_hi = self.compute_hazard(s_hi, has_ada)

        r_lo = h_lo * exposure * vulnerability
        r_hi = h_hi * exposure * vulnerability

        return {
            "hazard": round(float(hazard), 4),
            "risk": round(float(np.clip(risk, 0.0, 1.0)), 4),
            "risk_interval": [
                round(float(np.clip(r_lo, 0.0, 1.0)), 4),
                round(float(np.clip(r_hi, 0.0, 1.0)), 4),
            ],
        }

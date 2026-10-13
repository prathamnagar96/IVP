"""Probability calibration (Isotonic and Platt scaling) and reliability evaluation."""

from typing import Dict, Any, Tuple
import numpy as np
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.calibration import calibration_curve


class Calibrator:
    def __init__(self, method: str = "isotonic"):
        self.method = method
        self.calibrator = None

    def fit(self, y_raw_scores: np.ndarray, y_true: np.ndarray) -> "Calibrator":
        """Fit isotonic regression or sigmoid (Platt) on out-of-fold raw probability scores."""
        y_raw = np.clip(y_raw_scores, 1e-6, 1.0 - 1e-6)
        if self.method == "isotonic":
            self.calibrator = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0)
            self.calibrator.fit(y_raw, y_true)
        elif self.method == "sigmoid":
            self.calibrator = LogisticRegression(C=1.0, solver="lbfgs")
            self.calibrator.fit(y_raw.reshape(-1, 1), y_true)
        else:
            raise ValueError(f"Unknown calibration method: {self.method}")
        return self

    def predict_proba(self, y_raw_scores: np.ndarray) -> np.ndarray:
        """Calibrate raw probability scores into true well-calibrated probabilities."""
        if self.calibrator is None:
            return np.clip(y_raw_scores, 0.0, 1.0)

        y_raw = np.clip(y_raw_scores, 1e-6, 1.0 - 1e-6)
        if self.method == "isotonic":
            calibrated = self.calibrator.predict(y_raw)
        else:
            calibrated = self.calibrator.predict_proba(y_raw.reshape(-1, 1))[:, 1]
        return np.clip(calibrated, 0.0, 1.0)


def compute_reliability_curve(
    y_true: np.ndarray, y_prob: np.ndarray, n_bins: int = 10
) -> Dict[str, Any]:
    """Compute reliability diagram bins and Expected Calibration Error (ECE)."""
    prob_true, prob_pred = calibration_curve(y_true, y_prob, n_bins=n_bins, strategy="uniform")

    # Brier score
    brier_score = float(np.mean((y_prob - y_true) ** 2))

    # ECE approximation
    bin_edges = np.linspace(0.0, 1.0, n_bins + 1)
    ece = 0.0
    for i in range(n_bins):
        mask = (y_prob >= bin_edges[i]) & (y_prob < bin_edges[i + 1])
        if np.sum(mask) > 0:
            bin_acc = np.mean(y_true[mask])
            bin_conf = np.mean(y_prob[mask])
            ece += np.sum(mask) * np.abs(bin_acc - bin_conf)
    ece = float(ece / len(y_prob)) if len(y_prob) > 0 else 0.0

    return {
        "brier_score": round(brier_score, 4),
        "expected_calibration_error": round(ece, 4),
        "fraction_of_positives": [round(float(p), 4) for p in prob_true],
        "mean_predicted_value": [round(float(p), 4) for p in prob_pred],
    }

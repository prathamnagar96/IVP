"""Model evaluation metrics and operating point determination (Section 5.4, Acceptance Criteria)."""

from typing import Dict, Any, List, Tuple, Optional
import numpy as np
from sklearn.metrics import roc_auc_score, precision_recall_curve, auc, brier_score_loss


def calculate_metrics(
    y_true: np.ndarray,
    y_pred_proba: np.ndarray,
    unit_areas: Optional[np.ndarray] = None,
    recall_target: float = 0.85,
) -> Dict[str, Any]:
    """Calculate ROC-AUC, PR-AUC, Brier score, and find the operating point threshold meeting target recall R."""
    # ROC-AUC
    try:
        roc_auc = float(roc_auc_score(y_true, y_pred_proba))
    except Exception:
        roc_auc = 0.0

    # PR-AUC
    precision, recall, thresholds = precision_recall_curve(y_true, y_pred_proba)
    pr_auc = float(auc(recall, precision))

    # Brier score
    brier = float(brier_score_loss(y_true, y_pred_proba))

    # Operating point: find the highest threshold (smallest flagged set) that still satisfies recall >= recall_target
    sorted_indices = np.argsort(y_pred_proba)[::-1]
    sorted_labels = y_true[sorted_indices]
    sorted_scores = y_pred_proba[sorted_indices]

    total_positives = np.sum(y_true)
    cumulative_positives = np.cumsum(sorted_labels)
    recalls = cumulative_positives / max(1, total_positives)

    operating_idx = np.where(recalls >= recall_target)[0]
    if len(operating_idx) > 0:
        opt_i = operating_idx[0]
        operating_threshold = float(sorted_scores[opt_i])
        actual_recall = float(recalls[opt_i])
        flagged_count = opt_i + 1
        flagged_fraction = float(flagged_count / len(y_true))
    else:
        operating_threshold = 0.0
        actual_recall = 1.0
        flagged_count = len(y_true)
        flagged_fraction = 1.0

    # Area-based flagged calculation if unit areas provided
    if unit_areas is not None:
        sorted_areas = unit_areas[sorted_indices]
        flagged_area = float(np.sum(sorted_areas[:flagged_count]))
        total_area = float(np.sum(unit_areas))
        flagged_area_fraction = flagged_area / total_area if total_area > 0 else flagged_fraction
    else:
        flagged_area_fraction = flagged_fraction

    return {
        "roc_auc": round(roc_auc, 4),
        "pr_auc": round(pr_auc, 4),
        "brier_score": round(brier, 4),
        "recall_target": recall_target,
        "operating_threshold": round(operating_threshold, 4),
        "actual_recall_at_operating_point": round(actual_recall, 4),
        "flagged_units_fraction": round(flagged_fraction, 4),
        "flagged_area_fraction": round(flagged_area_fraction, 4),
    }

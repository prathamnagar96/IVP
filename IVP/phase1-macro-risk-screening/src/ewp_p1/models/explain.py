"""Model explainability, driver ranking, and data leakage detection (Section 5.4)."""

from typing import List, Dict, Any, Tuple
import numpy as np


FORBIDDEN_LEAKY_PATTERNS = [
    "dist_inventory",
    "distance_to_inventory",
    "landslide_dist",
    "post_event",
    "post_failure",
    "scar_dist",
]


def check_for_leaky_features(feature_names: List[str]) -> List[str]:
    """Audit feature set for known target-leaking features.

    E.g., distance to historical inventory, post-event imagery, or scar identifiers.
    """
    leaks_found = []
    for f in feature_names:
        f_lower = f.lower()
        for pattern in FORBIDDEN_LEAKY_PATTERNS:
            if pattern in f_lower:
                leaks_found.append(f)
                break
    return leaks_found


def compute_feature_importances(
    model: Any, feature_names: List[str]
) -> List[Dict[str, Any]]:
    """Extract and sort feature importances from linear, tree, or ensemble model."""
    importances = None
    if hasattr(model, "feature_importances_"):
        importances = model.feature_importances_
    elif hasattr(model, "coef_"):
        importances = np.abs(model.coef_[0])

    if importances is None:
        # Fallback uniform
        importances = np.ones(len(feature_names)) / len(feature_names)

    # Normalize to 1.0 sum
    total = np.sum(importances)
    if total > 0:
        norm_importances = importances / total
    else:
        norm_importances = importances

    ranking = []
    for name, imp in zip(feature_names, norm_importances):
        ranking.append({"feature": name, "importance": round(float(imp), 4)})

    ranking.sort(key=lambda x: x["importance"], reverse=True)
    return ranking

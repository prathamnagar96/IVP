"""Susceptibility model training, out-of-fold cross-validation, and scoring (Section 5.4)."""

from typing import List, Dict, Any, Optional, Tuple
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
try:
    from xgboost import XGBClassifier
    HAS_XGBOOST = True
except ImportError:
    HAS_XGBOOST = False

from .spatial_cv import SpatialBlockCV, verify_no_spatial_leakage
from .calibration import Calibrator, compute_reliability_curve
from .uncertainty import estimate_uncertainty_interval
from .metrics import calculate_metrics
from .explain import check_for_leaky_features, compute_feature_importances


class SusceptibilityEngine:
    def __init__(
        self,
        model_type: str = "xgboost",
        cv_block_size_m: float = 10000.0,
        n_splits: int = 5,
        calibration_method: str = "isotonic",
        recall_target: float = 0.85,
        random_state: int = 42,
    ):
        self.model_type = model_type
        self.cv_block_size_m = cv_block_size_m
        self.n_splits = n_splits
        self.calibration_method = calibration_method
        self.recall_target = recall_target
        self.random_state = random_state

        self.model = None
        self.calibrator = None
        self.feature_names = []
        self.metrics = {}
        self.feature_importances = []

    def _create_base_model(self):
        if self.model_type == "logistic":
            return LogisticRegression(
                C=1.0, solver="lbfgs", max_iter=1000, random_state=self.random_state
            )
        elif self.model_type == "random_forest":
            return RandomForestClassifier(
                n_estimators=100, max_depth=8, random_state=self.random_state, n_jobs=-1
            )
        elif self.model_type == "xgboost":
            if HAS_XGBOOST:
                return XGBClassifier(
                    n_estimators=100,
                    max_depth=4,
                    learning_rate=0.05,
                    subsample=0.8,
                    colsample_bytree=0.8,
                    eval_metric="logloss",
                    random_state=self.random_state,
                    n_jobs=-1,
                )
            else:
                return RandomForestClassifier(
                    n_estimators=100, max_depth=8, random_state=self.random_state, n_jobs=-1
                )
        else:
            raise ValueError(f"Unsupported model type: {self.model_type}")

    def train_and_validate(
        self,
        X: np.ndarray,
        y: np.ndarray,
        coords: np.ndarray,
        unit_ids: List[str],
        feature_names: List[str],
        is_mapped_complete: Optional[np.ndarray] = None,
        unit_areas: Optional[np.ndarray] = None,
    ) -> Dict[str, Any]:
        """Train susceptibility model with spatial block CV, strict negative filtering, and calibration."""
        self.feature_names = feature_names

        # Leakage check
        leaks = check_for_leaky_features(feature_names)
        if leaks:
            raise ValueError(f"Leaky features detected in dataset: {leaks}")

        # Invariant: Negatives ONLY from complete areas, never from unmapped ones
        if is_mapped_complete is not None:
            valid_mask = (y == 1) | ((y == 0) & is_mapped_complete)
            X_clean = X[valid_mask]
            y_clean = y[valid_mask]
            coords_clean = coords[valid_mask]
            unit_ids_clean = [u for u, m in zip(unit_ids, valid_mask) if m]
            areas_clean = unit_areas[valid_mask] if unit_areas is not None else None
        else:
            X_clean, y_clean, coords_clean = X, y, coords
            unit_ids_clean = unit_ids
            areas_clean = unit_areas

        # Spatial Block Cross Validation
        cv = SpatialBlockCV(
            block_size_m=self.cv_block_size_m,
            n_splits=self.n_splits,
            random_state=self.random_state,
        )

        oof_raw_preds = np.zeros(len(y_clean))
        fold_count = 0

        for train_idx, test_idx in cv.split(X_clean, y_clean, coords_clean):
            verify_no_spatial_leakage(train_idx, test_idx, unit_ids_clean)

            fold_model = self._create_base_model()
            fold_model.fit(X_clean[train_idx], y_clean[train_idx])
            oof_raw_preds[test_idx] = fold_model.predict_proba(X_clean[test_idx])[:, 1]
            fold_count += 1

        # Fit Calibrator on out-of-fold predictions
        self.calibrator = Calibrator(method=self.calibration_method)
        self.calibrator.fit(oof_raw_preds, y_clean)
        calibrated_oof = self.calibrator.predict_proba(oof_raw_preds)

        # Fit final model on full clean dataset
        self.model = self._create_base_model()
        self.model.fit(X_clean, y_clean)

        # Compute metrics & reliability curve
        self.metrics = calculate_metrics(
            y_clean, calibrated_oof, unit_areas=areas_clean, recall_target=self.recall_target
        )
        reliability = compute_reliability_curve(y_clean, calibrated_oof)
        self.metrics.update(reliability)

        # Explainability
        self.feature_importances = compute_feature_importances(self.model, self.feature_names)

        return {
            "metrics": self.metrics,
            "feature_importances": self.feature_importances[:5],
            "cv_folds_evaluated": fold_count,
        }

    def predict(
        self, X: np.ndarray, data_status_list: Optional[List[Any]] = None
    ) -> List[Dict[str, float]]:
        """Predict calibrated susceptibility S and uncertainty bounds [s_lo, s_hi]."""
        if self.model is None or self.calibrator is None:
            raise RuntimeError("Model must be trained before predicting.")

        raw_scores = self.model.predict_proba(X)[:, 1]
        calibrated_scores = self.calibrator.predict_proba(raw_scores)

        results = []
        for i, s in enumerate(calibrated_scores):
            status = data_status_list[i] if data_status_list else None
            s_lo, s_hi = estimate_uncertainty_interval(s, data_status=status)
            results.append({
                "s": round(float(s), 4),
                "s_lo": round(float(s_lo), 4),
                "s_hi": round(float(s_hi), 4),
            })

        return results

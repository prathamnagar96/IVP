"""Inverse-Velocity Module (IVM) for tertiary creep failure forecasting (Section 7.2).

Empirical Fukuzono (1985) / Voight (1988) tertiary creep forecasting:
y = v^(1 - alpha) (where alpha=2 -> y = 1/v).
When y -> 0, failure occurs at time tf.
"""

from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta, timezone
import numpy as np
from scipy import stats

from ..common.types import IVMStatus, IVMValidityGrade, IVMForecast


class IVMEngine:
    def __init__(
        self,
        alpha: float = 2.0,
        n_min: int = 5,
        v_min_threshold_mm_day: float = 2.0,
        snr_min: float = 2.5,
    ):
        self.alpha = alpha
        self.n_min = n_min
        self.v_min = v_min_threshold_mm_day
        self.snr_min = snr_min

    def is_accelerating(
        self, velocities_mm_day: np.ndarray, v_sigmas: np.ndarray
    ) -> Tuple[bool, bool]:
        """Check if velocity series exhibits sustained tertiary acceleration.

        Returns (is_accelerating, snr_ok).
        """
        if len(velocities_mm_day) < self.n_min:
            return False, False

        mean_v = np.mean(velocities_mm_day)
        mean_sigma = np.mean(v_sigmas) if len(v_sigmas) > 0 else 1.0

        if mean_v < self.snr_min * mean_sigma or mean_v < self.v_min:
            return False, False

        # Monotonic upward trend test (Kendall Tau)
        t = np.arange(len(velocities_mm_day))
        res = stats.kendalltau(t, velocities_mm_day)
        is_accel = res.correlation is not None and res.correlation > 0.4 and (res.pvalue is None or res.pvalue < 0.10)

        return bool(is_accel), True

    def run_ivm_forecast(
        self,
        time_days: np.ndarray,
        velocities_mm_day: np.ndarray,
        v_sigmas: np.ndarray,
        rain_pulse_active: bool = False,
        current_time: Optional[datetime] = None,
    ) -> IVMForecast:
        """Execute Fukuzono/Voight tertiary creep forecast with bootstrap window and guardrails."""
        if current_time is None:
            current_time = datetime.now(timezone.utc)

        time_days = np.asarray(time_days, dtype=float)
        velocities_mm_day = np.asarray(velocities_mm_day, dtype=float)
        v_sigmas = np.asarray(v_sigmas, dtype=float)
        if len(time_days) != len(velocities_mm_day) or len(v_sigmas) != len(velocities_mm_day):
            raise ValueError("time, velocity, and sigma arrays must have equal lengths")
        if not np.all(np.isfinite(time_days)) or not np.all(np.isfinite(velocities_mm_day)):
            raise ValueError("time and velocity arrays must contain only finite values")
        if np.any(~np.isfinite(v_sigmas)) or np.any(v_sigmas < 0):
            raise ValueError("velocity sigmas must be finite and non-negative")
        order = np.argsort(time_days)
        time_days = time_days[order]
        velocities_mm_day = velocities_mm_day[order]
        v_sigmas = v_sigmas[order]
        if len(time_days) > 1 and np.any(np.diff(time_days) <= 0):
            raise ValueError("time values must be strictly increasing")

        n = len(velocities_mm_day)
        if n < self.n_min:
            return IVMForecast(status=IVMStatus.NOT_ACCELERATING, flags=["INSUFFICIENT_POINTS"])

        # Check noise floor and acceleration
        is_accel, snr_ok = self.is_accelerating(velocities_mm_day, v_sigmas)

        if not snr_ok:
            return IVMForecast(status=IVMStatus.BELOW_NOISE_FLOOR, flags=["NOISE_DOMINATED"])

        if not is_accel:
            return IVMForecast(status=IVMStatus.NOT_ACCELERATING)

        # Rain pulse guardrail (Section 7.2)
        if rain_pulse_active:
            return IVMForecast(
                status=IVMStatus.RAIN_PULSE,
                flags=["RAIN_PULSE_CORRELATED", "TRANSIENT_CREEP_SUPPRESSED"],
            )

        # Compute y = v^(1 - alpha) = 1/v
        safe_v = np.clip(velocities_mm_day, 1e-4, None)
        y = safe_v ** (1.0 - self.alpha)

        # Theil-Sen fit on y[-n:]
        res = stats.theilslopes(y, time_days, alpha=0.90)
        slope = float(res.slope)
        intercept = float(res.intercept)

        # Monotone decrease condition: slope must be negative for 1/v -> 0 in the future
        if slope >= 0:
            return IVMForecast(status=IVMStatus.NO_CONVERGENCE, flags=["POSITIVE_SLOPE"])

        # Failure time: from current time t_now, remaining time to failure dt_f = -y_now / slope
        y_now = y[-1]
        days_to_failure = -y_now / slope
        t_now = time_days[-1]
        tf_day = t_now + days_to_failure

        if days_to_failure <= 0 or days_to_failure > 365:
            return IVMForecast(status=IVMStatus.NO_CONVERGENCE, flags=["TF_OUT_OF_BOUNDS"])

        # Bootstrap percentiles for (p5, p95) failure window
        n_boot = 50
        boot_days = []
        rng = np.random.RandomState(42)
        for _ in range(n_boot):
            sample_idx = rng.choice(n, size=n, replace=True)
            if len(np.unique(time_days[sample_idx])) < 3:
                continue
            sampled_time = time_days[sample_idx]
            sampled_y = y[sample_idx]
            sampled_order = np.argsort(sampled_time)
            b_res = stats.theilslopes(
                sampled_y[sampled_order], sampled_time[sampled_order], alpha=0.90
            )
            if b_res.slope < 0:
                b_dt = -y_now / b_res.slope
                if b_dt > 0:
                    boot_days.append(b_dt)

        if len(boot_days) >= 10:
            p5 = float(np.percentile(boot_days, 5))
            p95 = float(np.percentile(boot_days, 95))
        else:
            p5 = max(0.1, days_to_failure * 0.7)
            p95 = days_to_failure * 1.4

        tf_dt_lo = current_time + timedelta(days=p5)
        tf_dt_hi = current_time + timedelta(days=p95)

        # Validity grade
        spread_ratio = (p95 - p5) / max(0.1, days_to_failure)
        if spread_ratio < 0.4 and n >= 8:
            validity = IVMValidityGrade.HIGH
        elif spread_ratio < 0.9:
            validity = IVMValidityGrade.MEDIUM
        else:
            validity = IVMValidityGrade.LOW

        return IVMForecast(
            status=IVMStatus.VALID,
            tf_window_utc=[tf_dt_lo.isoformat(), tf_dt_hi.isoformat()],
            validity=validity,
            flags=["TERTIARY_CREEP_CONFIRMED"],
        )

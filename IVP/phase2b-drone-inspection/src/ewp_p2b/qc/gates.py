"""QC gates for release of drone products."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class QCStatus(str, Enum):
    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"


@dataclass(frozen=True)
class QCGates:
    rmse_xy_m: float
    rmse_z_m: float
    coverage_pct: float = 98.0
    ground_density_ppm2: float = 3.0
    registration_rmse_m: float = 0.1
    lod95_target_m: float | None = None


def evaluate_qc(
    *,
    rmse_xy_m: float,
    rmse_z_m: float,
    coverage_pct: float,
    ground_density_ppm2: float,
    registration_rmse_m: float,
    lod95_m: float,
    gates: QCGates,
) -> dict[str, object]:
    """Evaluate all release gates and return status plus machine-readable reasons."""
    failures: list[str] = []
    warnings: list[str] = []
    if rmse_xy_m > gates.rmse_xy_m:
        failures.append("check_point_rmse_xy")
    if rmse_z_m > gates.rmse_z_m:
        failures.append("check_point_rmse_z")
    if coverage_pct < gates.coverage_pct:
        failures.append("coverage")
    if ground_density_ppm2 < gates.ground_density_ppm2:
        warnings.append("ground_density")
    if registration_rmse_m > gates.registration_rmse_m:
        failures.append("registration_residual")
    if gates.lod95_target_m is not None and lod95_m > gates.lod95_target_m:
        warnings.append("lod95_target")
    status = QCStatus.FAIL if failures else QCStatus.WARN if warnings else QCStatus.PASS
    return {
        "qc_status": status.value,
        "failures": failures,
        "warnings": warnings,
        "release_blocked": status is QCStatus.FAIL,
    }

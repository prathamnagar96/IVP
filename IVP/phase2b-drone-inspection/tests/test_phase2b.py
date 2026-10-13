from datetime import datetime, timezone
import numpy as np
import pytest

from planner.mission import WeatherLimits, evaluate_go_no_go
from ewp_p2b.change.dod import dem_of_difference, lod95, volume_change_m3
from ewp_p2b.qc.gates import QCGates, evaluate_qc
from ewp_p2b.stac.item import build_drone_product, validate_drone_product


def test_grounded_mission_remains_queued():
    result = evaluate_go_no_go(
        permit_valid=True, crew_available=True, batteries_available=True,
        wind_ms=4, gust_ms=8, visibility_m=5000, precipitation=True,
        limits=WeatherLimits(10, 15, 1000),
    )
    assert result["state"] == "QUEUED"
    assert "precipitation" in result["reasons"]


def test_dod_suppresses_changes_below_lod():
    change, stats = dem_of_difference(
        np.zeros((2, 2)), np.array([[0.01, 0.2], [np.nan, -0.2]]),
        0.03, 0.03, 0.01,
    )
    assert stats["lod95_m"] == pytest.approx(lod95(0.03, 0.03, 0.01))
    assert np.isnan(change[0, 0])
    assert change[0, 1] == pytest.approx(0.2)
    assert volume_change_m3(change, 4.0) == pytest.approx(0.0)


def test_fail_qc_blocks_release():
    result = evaluate_qc(
        rmse_xy_m=0.2, rmse_z_m=0.2, coverage_pct=90,
        ground_density_ppm2=1, registration_rmse_m=0.2, lod95_m=0.1,
        gates=QCGates(0.1, 0.1),
    )
    assert result["qc_status"] == "FAIL"
    assert result["release_blocked"] is True


def test_stac_item_validates_against_shared_contract():
    item = build_drone_product(
        site_id="SITE-0007",
        observed_at=datetime(2026, 10, 2, 5, 40, tzinfo=timezone.utc),
        mission_type="PERIODIC",
        assets={"dtm": "dtm_cog.tif", "pointcloud": "cloud.copc.laz"},
        ground_density_ppm2=14.2,
        registration_rmse_m=0.03,
        lod95_m=0.08,
        qc_status="PASS",
    )
    validate_drone_product(item)
    assert item["id"] == "SITE-0007_2026-10-02_periodic"

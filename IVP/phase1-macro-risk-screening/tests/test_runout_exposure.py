"""Test empirical runout propagation and exposure calculation."""

import pytest
from ewp_p1.runout.propagation import RunoutPropagator
from ewp_p1.features.exposure import ExposureCalculator


def test_runout_propagation_energy_line():
    """Verify that uphill source units propagate runout downhill to receiving units."""
    propagator = RunoutPropagator(source_s_threshold=0.65)

    # 3 slope units in a line along a hillside:
    # SU-01 (Ridge top, elev 1500m, high susceptibility source S=0.8)
    # SU-02 (Mid-slope, elev 1200m, horiz dist 500m)
    # SU-03 (Valley floor, elev 900m, horiz dist 1500m from SU-01)
    unit_scores = {"SU-01": 0.80, "SU-02": 0.40, "SU-03": 0.20}
    unit_centroids = {
        "SU-01": (0.0, 0.0, 1500.0),
        "SU-02": (500.0, 0.0, 1200.0),
        "SU-03": (1500.0, 0.0, 900.0),
    }
    unit_adjacencies = {
        "SU-01": ["SU-02"],
        "SU-02": ["SU-03"],
        "SU-03": [],
    }

    res = propagator.propagate_hazard(
        source_units=["SU-01"],
        unit_centroids=unit_centroids,
        unit_adjacencies=unit_adjacencies,
        process_class="shallow_debris",  # reach angle ~ 14 deg => tan(14) ~ 0.25
    )

    # SU-02 delta_z = 300, dist = 500 => delta_z/dist = 0.60 > 0.25 => In runout!
    # SU-03 delta_z = 600, dist = 1500 => delta_z/dist = 0.40 > 0.25 => In runout!
    inherited = res["inherited_runout_by_unit"]
    assert "SU-01" in inherited.get("SU-02", [])
    assert "SU-01" in inherited.get("SU-03", [])


def test_exposure_includes_runout_footprint():
    """Verify Section 5.3 requirement: exposure of a unit counts elements inside unit AND in runout."""
    calc = ExposureCalculator()

    internal = {
        "population": 10.0,
        "buildings": 3,
        "critical_facilities": 0,
        "road_km": 0.5,
    }
    runout_downslope = {
        "population": 500.0,
        "buildings": 120,
        "critical_facilities": 2,  # hospital/school downslope
        "road_km": 5.0,
    }

    # Exposure without runout
    exp_alone = calc.compute_unit_exposure(internal_elements=internal)

    # Exposure with downslope runout elements included
    exp_with_runout = calc.compute_unit_exposure(
        internal_elements=internal, runout_elements=runout_downslope
    )

    # Downslope assets must significantly increase the exposure score
    assert exp_with_runout["exposure"] > exp_alone["exposure"]
    assert exp_with_runout["total_population"] == 510.0
    assert exp_with_runout["total_critical"] == 2
    assert exp_with_runout["vulnerability"] == 1.0  # default conservative

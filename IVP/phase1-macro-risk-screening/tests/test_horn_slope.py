"""Test Horn (1981) slope algorithm on synthetic planar surfaces.

Regression test specified in Section 9:
Horn slope on a synthetic 30° plane returns 30.0° ± 0.05°
(regression test against the un-normalised Sobel mistake).
"""

import numpy as np
import pytest
from ewp_p1.terrain.horn import compute_slope_aspect, create_synthetic_plane


def test_horn_slope_on_synthetic_30_degree_plane():
    """Verify that Horn slope on a synthetic 30-degree plane returns 30.0 deg +/- 0.05 deg."""
    # Test across multiple aspects (East, North, West, South, oblique)
    test_aspects = [0.0, 45.0, 90.0, 135.0, 180.0, 225.0, 270.0, 315.0]

    for aspect in test_aspects:
        dem = create_synthetic_plane(
            slope_deg=30.0,
            aspect_deg=aspect,
            shape=(60, 60),
            cell_size=10.0,
            base_elevation=1500.0,
        )

        slope_deg, aspect_calc = compute_slope_aspect(dem, cell_size_x=10.0, cell_size_y=10.0)

        # Slice interior cells away from 1-pixel borders
        interior = slope_deg[2:-2, 2:-2]

        mean_slope = float(np.mean(interior))
        max_err = float(np.max(np.abs(interior - 30.0)))

        # Target tolerance: 30.0 +/- 0.05 deg
        assert abs(mean_slope - 30.0) < 0.05, (
            f"Mean slope {mean_slope:.4f} exceeds tolerance on aspect {aspect}"
        )
        assert max_err < 0.05, (
            f"Max slope error {max_err:.4f} exceeds tolerance on aspect {aspect}"
        )


def test_horn_slope_flat_plane():
    """Flat terrain must yield 0.0 deg slope."""
    flat_dem = np.full((30, 30), 1000.0, dtype=np.float64)
    slope_deg, aspect_deg = compute_slope_aspect(flat_dem, cell_size_x=10.0)

    interior = slope_deg[2:-2, 2:-2]
    assert np.allclose(interior, 0.0, atol=1e-5)

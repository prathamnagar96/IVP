"""Regional empirical runout propagation model (Section 5.5).

Multiple Flow Direction (MFD) spreading with persistence + energy line (angle of reach).
Transfers hazard to downslope receiving units and links footprints.
"""

from typing import List, Dict, Any, Optional, Tuple, Set
import numpy as np


class RunoutPropagator:
    # Calibrated friction angles (reach angle tan phi = delta_H / L) per process class
    DEFAULT_REACH_ANGLES = {
        "rockfall": 32.0,       # High reach angle / short runout
        "deep_seated": 20.0,    # Intermediate reach angle
        "shallow_debris": 14.0, # Low reach angle / long runout
        "debris_flow": 11.0,    # Channelized long runout
    }

    def __init__(
        self,
        source_s_threshold: float = 0.65,
        reach_angles: Optional[Dict[str, float]] = None,
    ):
        self.source_s_threshold = source_s_threshold
        self.reach_angles = reach_angles or self.DEFAULT_REACH_ANGLES

    def identify_sources(
        self, unit_scores: Dict[str, float]
    ) -> List[str]:
        """Identify slope units acting as potential landslide sources based on susceptibility threshold."""
        return [uid for uid, s in unit_scores.items() if s >= self.source_s_threshold]

    def propagate_hazard(
        self,
        source_units: List[str],
        unit_centroids: Dict[str, Tuple[float, float, float]],  # (x, y, z_elev)
        unit_adjacencies: Dict[str, List[str]],  # topological downhill neighbors
        process_class: str = "shallow_debris",
    ) -> Dict[str, Any]:
        """Compute downhill propagation using angle-of-reach energy line criterion.

        Returns:
            - runout_links: dict mapping receiving_unit -> list of source_units it inherited from
            - footprint_associations: dict mapping source_unit -> list of receiving_units in its runout
        """
        reach_angle_deg = self.reach_angles.get(process_class, 14.0)
        tan_phi = np.tan(np.radians(reach_angle_deg))

        runout_links: Dict[str, Set[str]] = {}
        footprint_associations: Dict[str, Set[str]] = {}

        for src in source_units:
            if src not in unit_centroids:
                continue
            src_x, src_y, src_z = unit_centroids[src]
            footprint_associations[src] = set()

            # BFS / downhill propagation
            visited = {src}
            queue = [src]

            while queue:
                current = queue.pop(0)
                neighbors = unit_adjacencies.get(current, [])

                for nbr in neighbors:
                    if nbr not in unit_centroids or nbr in visited:
                        continue

                    nbr_x, nbr_y, nbr_z = unit_centroids[nbr]
                    delta_z = src_z - nbr_z
                    if delta_z <= 0:
                        # Cannot run out uphill
                        continue

                    # Planar horizontal distance L
                    horiz_dist = np.hypot(nbr_x - src_x, nbr_y - src_y)
                    if horiz_dist == 0:
                        continue

                    # Energy line condition: delta_z / horiz_dist >= tan_phi
                    if (delta_z / horiz_dist) >= tan_phi:
                        visited.add(nbr)
                        queue.append(nbr)

                        footprint_associations[src].add(nbr)
                        if nbr not in runout_links:
                            runout_links[nbr] = set()
                        runout_links[nbr].add(src)

        # Convert sets to sorted lists
        clean_links = {k: sorted(list(v)) for k, v in runout_links.items()}
        clean_footprints = {k: sorted(list(v)) for k, v in footprint_associations.items()}

        return {
            "inherited_runout_by_unit": clean_links,
            "footprints_by_source": clean_footprints,
            "reach_angle_deg": reach_angle_deg,
        }

"""Master screening pipeline orchestrator for Phase 1 Macro-Risk Screening."""

from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
import json
from pathlib import Path
import numpy as np

from .common.config import ConfigLoader
from .common.lineage import LineageRecord, generate_run_id, compute_hash
from .common.types import (
    DataStatus,
    Lane,
    ProcessClass,
    SusceptibilityClass,
    RainClass,
    QueueItem,
    RegionalAdvisory,
)
from .features.exposure import ExposureCalculator
from .runout.propagation import RunoutPropagator
from .quality.unknown_logic import QualityEvaluator
from .queue.scoring import RiskScoringEngine
from .queue.lanes import LaneAssigner
from .queue.capacity import CapacityManager
from .queue.hysteresis import HysteresisManager
from .queue.audit import AuditSampler
from .queue.builder import QueueBuilder
from .rain.fusion import RainFuser
from .rain.accumulations import RainfallAccumulator
from .rain.id_thresholds import IDThresholdEvaluator
from .rain.matrix import AdvisoryMatrixEngine, categorize_susceptibility


class Phase1Pipeline:
    def __init__(self, config_dir: Optional[Path] = None):
        self.config_loader = ConfigLoader(config_dir)
        configs = self.config_loader.load_all()
        self.region_cfg = configs["region"]
        self.capacity_cfg = configs["capacity"]
        self.thresholds_cfg = configs["thresholds"]

        # Initialize sub-engines
        self.exposure_calc = ExposureCalculator()
        self.runout_propagator = RunoutPropagator(
            source_s_threshold=self.region_cfg.get("queue", {}).get("thresholds", {}).get("s_high", 0.70)
        )
        self.quality_evaluator = QualityEvaluator()

        q_thresh = self.region_cfg.get("queue", {}).get("thresholds", {})
        self.risk_engine = RiskScoringEngine(
            h_active=q_thresh.get("h_active", 0.60)
        )
        self.lane_assigner = LaneAssigner(
            e_min=q_thresh.get("e_min", 0.30),
            s_high=q_thresh.get("s_high", 0.70),
            s_med=q_thresh.get("s_med", 0.40),
            r_drone=q_thresh.get("r_drone", 0.15),
        )

        lane_quotas = self.capacity_cfg.get("queue_limits", {})
        self.capacity_mgr = CapacityManager(lane_quotas)
        self.hysteresis_mgr = HysteresisManager(
            persistence_cycles=self.region_cfg.get("queue", {}).get("hysteresis_cycles", 2)
        )
        audit_pct = self.region_cfg.get("queue", {}).get("lanes", {}).get("AUDIT", {}).get("sample_pct", 5.0)
        self.audit_sampler = AuditSampler(sample_pct=audit_pct)
        self.queue_builder = QueueBuilder()

        # Rain engines
        self.rain_fuser = RainFuser(
            max_stale_hours=self.region_cfg.get("unknown", {}).get("rainfall", {}).get("max_stale_h", 6.0)
        )
        api_cfg = self.region_cfg.get("rainfall", {}).get("api", {})
        self.rain_accum = RainfallAccumulator(
            api_window_days=api_cfg.get("window_d", 14),
            api_decay=api_cfg.get("decay", 0.85),
        )
        self.id_evaluator = IDThresholdEvaluator()
        self.advisory_engine = AdvisoryMatrixEngine(region_id=self.region_cfg.get("region", "R01"))

    def run_screening_cycle(
        self,
        slope_units_data: List[Dict[str, Any]],
        rainfall_feed_data: Optional[Dict[str, Any]] = None,
        run_timestamp: Optional[datetime] = None,
        event_trigger_active: bool = False,
    ) -> Dict[str, Any]:
        """Execute end-to-end Phase 1 macro-risk screening cycle.

        Input:
            slope_units_data: list of dicts with unit features, coordinates, deformation, and exposure.
            rainfall_feed_data: optional rain observations and time series.
        Output:
            dict containing lineage, queue_items, advisories, audit_samples, and metrics.
        """
        run_id = generate_run_id(run_timestamp)
        input_hash = compute_hash(slope_units_data)
        lineage = LineageRecord(
            run_id=run_id,
            input_hash=input_hash,
            config_snapshot=self.region_cfg,
        )

        # 1. Map Unit centroids and adjacencies for runout
        unit_centroids = {}
        unit_scores_map = {}
        unit_adjacencies = {}
        for u in slope_units_data:
            uid = u["unit_id"]
            unit_centroids[uid] = u.get("centroid_3d", (0.0, 0.0, 1000.0))
            unit_scores_map[uid] = u.get("susceptibility", 0.5)
            unit_adjacencies[uid] = u.get("downhill_neighbors", [])

        # 2. Runout Propagation
        sources = self.runout_propagator.identify_sources(unit_scores_map)
        propagation = self.runout_propagator.propagate_hazard(
            sources, unit_centroids, unit_adjacencies, process_class="shallow_debris"
        )
        inherited_links = propagation["inherited_runout_by_unit"]
        footprints = propagation["footprints_by_source"]

        # 3. Process Each Unit
        candidate_records = []
        for u in slope_units_data:
            uid = u["unit_id"]
            s = float(u.get("susceptibility", 0.5))
            s_lo = float(u.get("s_lo", max(0.0, s - 0.1)))
            s_hi = float(u.get("s_hi", min(1.0, s + 0.1)))

            # Exposure calculation (internal + runout)
            runout_exposure = u.get("runout_exposure_elements", None)
            exp_res = self.exposure_calc.compute_unit_exposure(
                internal_elements=u.get("internal_exposure_elements", {}),
                runout_elements=runout_exposure,
                vulnerability_override=u.get("vulnerability", 1.0),
            )
            exposure = exp_res["exposure"]
            vulnerability = exp_res["vulnerability"]

            # Deformation info
            def_dict = u.get("deformation", {})
            has_ada = bool(def_dict.get("ada", False))
            def_status = def_dict.get("status", "OK")

            # Data Quality assessment
            qual_res = self.quality_evaluator.evaluate_unit_data_status(
                u.get("feature_qualities", {})
            )
            data_status_str = qual_res["data_status"]
            data_status = DataStatus(data_status_str)
            unknown_reasons = qual_res["unknown_reasons"]

            # Invariant: UNKNOWN data_status widens uncertainty
            if data_status == DataStatus.UNKNOWN:
                s_lo = max(0.0, s_lo - 0.15)
                s_hi = min(1.0, s_hi + 0.15)

            # Hazard and Risk scoring
            hazard = self.risk_engine.compute_hazard(s, has_ada)
            risk_res = self.risk_engine.compute_risk(
                hazard, exposure, vulnerability, s_lo, s_hi, has_ada
            )
            risk = risk_res["risk"]
            risk_interval = risk_res["risk_interval"]

            # Initial lane assignment
            initial_lane = self.lane_assigner.evaluate_initial_lane(
                risk, s, exposure, has_ada, data_status
            )

            # Hysteresis smoothing
            current_lane = Lane(u.get("previous_lane", Lane.NONE.value))
            stable_lane = self.hysteresis_mgr.apply_hysteresis(
                uid, current_lane, initial_lane, event_trigger_active=event_trigger_active
            )

            # Footprint ID
            footprint_id = f"RO-{uid}" if uid in sources else None

            candidate_records.append({
                "unit_id": uid,
                "process": u.get("process", ["shallow_debris"]),
                "scores": {
                    "susceptibility": s,
                    "hazard": hazard,
                    "exposure": exposure,
                    "vulnerability": vulnerability,
                    "risk": risk,
                    "risk_interval": risk_interval,
                },
                "deformation": {
                    "status": def_status,
                    "coverage_pct": def_dict.get("coverage_pct", 50.0),
                    "v_downslope_mm_yr": def_dict.get("v_downslope_mm_yr", 0.0),
                    "v_sigma_mm_yr": def_dict.get("v_sigma_mm_yr", 2.0),
                    "ada": has_ada,
                },
                "data_status": data_status,
                "unknown_reasons": unknown_reasons,
                "runout": {
                    "inherited_from": inherited_links.get(uid, []),
                    "footprint_id": footprint_id,
                },
                "lane": stable_lane,
                "risk": risk,
            })

        # 4. Enforce Capacity Quotas
        quota_assigned = self.capacity_mgr.enforce_quotas(candidate_records)

        # 5. Stratified Audit Sampling on NONE lane units
        none_candidates = [u for u in quota_assigned if u["lane"] == Lane.NONE]
        non_none_units = [u for u in quota_assigned if u["lane"] != Lane.NONE]

        audit_units, remaining_none = self.audit_sampler.draw_audit_sample(none_candidates)
        all_final_units = non_none_units + audit_units + remaining_none

        # 6. Build and Validate Official QueueItems
        queue_items = self.queue_builder.build_queue_items(
            all_final_units, run_id=run_id, validate=True
        )

        # 7. Regional Rain Advisories
        advisories = []
        if rainfall_feed_data:
            hourly_rain = rainfall_feed_data.get("hourly_rain_mm", [0.0] * 24)
            daily_rain = rainfall_feed_data.get("daily_rain_mm", [0.0] * 14)
            duration_h = rainfall_feed_data.get("duration_h", 6.0)
            intensity = rainfall_feed_data.get("intensity_mm_h", 15.0)

            api = self.rain_accum.compute_api(daily_rain)
            id_res = self.id_evaluator.classify_event(duration_h, intensity)
            rain_class = RainClass(id_res["rain_class"])

            # Regional representative susceptibility class
            mean_s = float(np.mean([u.scores.susceptibility for u in queue_items])) if queue_items else 0.5
            s_class = categorize_susceptibility(mean_s)

            adv_candidate = self.advisory_engine.generate_advisory_candidate(
                s_class=s_class,
                r_class=rain_class,
                rainfall_summary={
                    "api_mm": api,
                    "max_intensity_mm_h": intensity,
                    "duration_h": duration_h,
                    "id_exceedance_ratio": id_res["exceedance_ratio"],
                },
                affected_units_count=len(queue_items),
                now=run_timestamp,
            )
            advisories.append(adv_candidate)

        return {
            "lineage": lineage.to_dict(),
            "queue_items": queue_items,
            "advisories": advisories,
            "summary": {
                "total_units": len(queue_items),
                "instrument_lane": sum(1 for q in queue_items if q.lane == Lane.INSTRUMENT.value),
                "drone_baseline_lane": sum(1 for q in queue_items if q.lane == Lane.DRONE_BASELINE.value),
                "rescreen_lane": sum(1 for q in queue_items if q.lane == Lane.RESCREEN.value),
                "audit_lane": sum(1 for q in queue_items if q.lane == Lane.AUDIT.value),
                "none_lane": sum(1 for q in queue_items if q.lane == Lane.NONE.value),
                "unknown_count": sum(1 for q in queue_items if q.data_status == DataStatus.UNKNOWN.value),
            },
        }

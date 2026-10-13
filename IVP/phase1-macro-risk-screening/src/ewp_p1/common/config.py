"""Configuration loader and schema validator for Phase 1."""

import os
from pathlib import Path
from typing import Dict, Any, Optional
import yaml


class ConfigLoader:
    def __init__(self, config_dir: Optional[Path] = None):
        if config_dir is None:
            # Default to phase1 config directory
            base_dir = Path(__file__).resolve().parents[3]
            config_dir = base_dir / "config"
        self.config_dir = Path(config_dir)

    def load_region_config(self, filename: str = "region.yaml") -> Dict[str, Any]:
        path = self.config_dir / filename
        if not path.exists():
            raise FileNotFoundError(f"Region config file not found: {path}")
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    def load_capacity_config(self, filename: str = "capacity.yaml") -> Dict[str, Any]:
        path = self.config_dir / filename
        if not path.exists():
            raise FileNotFoundError(f"Capacity config file not found: {path}")
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    def load_thresholds(self, filename: str) -> Dict[str, Any]:
        path = self.config_dir / "thresholds" / filename
        if not path.exists():
            raise FileNotFoundError(f"Threshold config file not found: {path}")
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    def load_all(self) -> Dict[str, Any]:
        region = self.load_region_config()
        capacity = self.load_capacity_config()
        thresholds = {}
        thresh_dir = self.config_dir / "thresholds"
        if thresh_dir.exists():
            for f in thresh_dir.glob("*.yaml"):
                thresholds[f.stem] = self.load_thresholds(f.name)
        return {
            "region": region,
            "capacity": capacity,
            "thresholds": thresholds,
        }

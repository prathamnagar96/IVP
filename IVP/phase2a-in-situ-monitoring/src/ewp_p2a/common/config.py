"""Configuration loader for Phase 2A site and TARP configurations."""

from pathlib import Path
from typing import Dict, Any, Optional
import yaml


class SiteConfigLoader:
    def __init__(self, sites_dir: Optional[Path] = None):
        if sites_dir is None:
            # Default to config/sites directory in phase2a package
            base_dir = Path(__file__).resolve().parents[3]
            sites_dir = base_dir / "config" / "sites"
        self.sites_dir = Path(sites_dir)

    def load_site_config(self, site_id: str) -> Dict[str, Any]:
        path = self.sites_dir / site_id / "site.yaml"
        if not path.exists():
            raise FileNotFoundError(f"Site config not found: {path}")
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    def load_tarp_config(self, site_id: str) -> Dict[str, Any]:
        path = self.sites_dir / site_id / "tarp.yaml"
        if not path.exists():
            raise FileNotFoundError(f"TARP config not found: {path}")
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    def load_site_bundle(self, site_id: str) -> Dict[str, Any]:
        return {
            "site": self.load_site_config(site_id),
            "tarp": self.load_tarp_config(site_id),
        }

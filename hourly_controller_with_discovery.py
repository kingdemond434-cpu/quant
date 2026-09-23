"""Hourly controller with external discovery integration.

This adds PHASE 2.5 - EXTERNAL DISCOVERY to the pipeline.
"""

import sys
import os
import time
import json
from datetime import datetime, timezone
from pathlib import Path

# Add paths
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'desks', 'mt5'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'desks', 'mt5', 'side_channels'))

# Import existing phases
from hourly_controller import HourlyController

# Import external discovery
from run_all_miners import run_all_miners


class HourlyControllerWithDiscovery(HourlyController):
    """Extended controller with external discovery phase."""

    def phase_external_discovery(self) -> None:
        """PHASE 2.5: Run all external discovery channels."""
        start = time.time()
        self.log("=== PHASE 2.5: EXTERNAL DISCOVERY ===")

        try:
            results = run_all_miners()
            summary = results.get("summary", {})

            self.log(f"Discovery complete: {summary.get('total_discoveries', 0)} discoveries from {summary.get('successful_miners', 0)} miners")

            # Save discovery results
            discovery_file = self.data_dir / "intelligence" / "latest_discoveries.json"
            discovery_file.parent.mkdir(parents=True, exist_ok=True)
            discovery_file.write_text(json.dumps(results, indent=2), encoding="utf-8")

        except Exception as e:
            self.log(f"Discovery failed: {e}")

        self.stats["external_discovery"] = time.time() - start

    def run_all_phases(self) -> None:
        """Run all phases including external discovery."""
        self.phase_setup()
        self.phase_data_refresh()
        self.phase_shadow_sync()
        self.phase_external_discovery()  # NEW PHASE
        self.phase_system_health()
        self.phase_shadow_evaluation()
        self.phase_hunt()
        self.phase_deep_analysis()
        self.phase_promotion()
        self.phase_gating()
        self.phase_reporting()


def main():
    """Main entry point with --once mode."""
    controller = HourlyControllerWithDiscovery()
    
    if "--once" in sys.argv:
        controller.run_all_phases()
    else:
        # Default: run once
        controller.run_all_phases()


if __name__ == "__main__":
    main()

"""Hourly controller integration with external discovery.

This adds the external discovery phase to the existing hourly controller.
Import this in hourly_controller.py to add the phase.
"""

import time
import json
from pathlib import Path

# Import the miner runner and hypothesis converter
import sys
import os
_side = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'side_channels')
if _side not in sys.path:
    sys.path.insert(0, _side)

from run_all_miners import run_all_miners
from convert_to_hypotheses import convert_discoveries


def phase_external_discovery(log_fn=None, data_dir=None) -> dict:
    """Run all external discovery channels and generate hypotheses.

    Returns:
        dict with keys: discoveries_count, hypotheses_count, elapsed, results
    """
    _log = log_fn or (lambda msg: print(msg))
    _log("=== PHASE 2.5: EXTERNAL DISCOVERY ===")
    start = time.time()

    # Step 1: Run all miners
    _log("Running 11 discovery channels...")
    miner_results = run_all_miners()
    summary = miner_results.get("summary", {})
    disc_count = summary.get("total_discoveries", 0)
    _log(f"  -> {disc_count} raw discoveries from {summary.get('successful_miners', 0)} channels")

    # Step 2: Save raw discoveries
    if data_dir:
        intel_dir = Path(data_dir) / "intelligence"
        intel_dir.mkdir(parents=True, exist_ok=True)
        (intel_dir / "latest_discoveries.json").write_text(
            json.dumps(miner_results, indent=2, default=str), encoding="utf-8"
        )

    # Step 3: Convert to hypotheses
    hypotheses = convert_discoveries()
    _log(f"  -> {len(hypotheses)} testable hypotheses generated")

    # Step 4: Save hypotheses
    if data_dir:
        hyp_dir = Path(data_dir) / "hypotheses"
        hyp_dir.mkdir(parents=True, exist_ok=True)
        (hyp_dir / "latest_external.json").write_text(
            json.dumps(hypotheses, indent=2, default=str), encoding="utf-8"
        )

    elapsed = time.time() - start
    _log(f"  -> Completed in {elapsed:.1f}s")

    return {
        "discoveries_count": disc_count,
        "hypotheses_count": len(hypotheses),
        "elapsed": elapsed,
        "results": miner_results,
    }

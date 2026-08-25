"""Pipeline Stage 3: Shadow — forward evidence collection on venue-native bars."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

BASE = Path(__file__).resolve().parent.parent.parent
SHADOW_DIR = BASE / "reports" / "shadow"
REPORTS_DIR = BASE / "reports"


@dataclass
class ShadowVerdict:
    """Forward shadow verdict for a hypothesis."""
    hypothesis_id: str
    status: str  # ACTIVE | NO_DATA | PROMOTION_CANDIDATE | KILL | PROXY_SHADOW
    n: int
    exp_r: float
    max_dd_r: float
    days_active: int
    bar_source: str
    bar_source_stale: bool
    promotion_authority: bool
    gate_admission: str  # FULL_10_PASS | VALIDITY_PASS_POWER_DEFICIENT | OPEN_FORWARD_MEASUREMENT
    power_deficiencies: list[str] = None


def run_shadow(hypothesis_ids: list[str]) -> list[ShadowVerdict]:
    """Run forward shadow validation for validated hypotheses.

    Delegates to shadow_forward.main() for actual computation.
    """
    # This integrates with existing shadow_forward.py
    # The actual work happens there; this is the pipeline interface
    verdicts = []
    for hid in hypothesis_ids:
        # Load shadow state
        state_path = SHADOW_DIR / "shadow_state.json"
        if state_path.exists():
            import json
            with open(state_path, "r", encoding="utf-8") as f:
                state = json.load(f)
            # Find matching key for this hypothesis
            for key, st in state.items():
                if isinstance(st, dict) and hid in key:
                    verdicts.append(ShadowVerdict(
                        hypothesis_id=hid,
                        status=st.get("status", "UNKNOWN"),
                        n=st.get("n", 0),
                        exp_r=st.get("exp_r", 0.0),
                        max_dd_r=st.get("max_dd_r", 0.0),
                        days_active=st.get("days_active", 0),
                        bar_source=st.get("bar_source", "UNKNOWN"),
                        bar_source_stale=st.get("bar_source_stale", False),
                        promotion_authority=st.get("promotion_authority", False),
                        gate_admission=st.get("gate_admission", "UNKNOWN"),
                        power_deficiencies=st.get("power_deficiencies", []),
                    ))
                    break
    return verdicts


if __name__ == "__main__":
    import sys
    ids = sys.argv[1:] if len(sys.argv) > 1 else []
    for v in run_shadow(ids):
        print(f"{v.hypothesis_id}: {v.status} (n={v.n}, exp={v.exp_r:.3f}R)")
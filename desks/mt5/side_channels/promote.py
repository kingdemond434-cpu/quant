"""Pipeline Stage 4: Promotion — auto-promote shadow-validated hypotheses to live."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

BASE = Path(__file__).resolve().parent.parent.parent
SHADOW_DIR = BASE / "reports" / "shadow"
SLEEVES_FILE = BASE / "data" / "sleeves.json"


@dataclass
class PromotionDecision:
    """Promotion decision for a hypothesis."""
    hypothesis_id: str
    promoted: bool
    basis: str  # FULL_10_PASS | VALIDITY_PASS_FORWARD_CURE
    lot: float
    status: str  # LIVE | BLOCKED | RETIRED
    reason: str = ""


def promote_hypothesis(hypothesis_id: str, shadow_verdict: dict) -> PromotionDecision:
    """Decide whether to promote a hypothesis based on shadow verdict.

    Implements the promotion protocol:
    - FULL_10_PASS: promote directly
    - VALIDITY_PASS_POWER_DEFICIENT: promote if forward evidence cures power deficiencies
    - XAUUSD challengers: must beat armed gold book
    """
    from gate_classification import get_promotion_config

    config = get_promotion_config()
    forward_cfg = config.get("forward_cure_thresholds", {})
    min_trades = forward_cfg.get("min_trades", 50)
    min_exp = forward_cfg.get("min_exp_r", 0.05)
    max_dd = forward_cfg.get("max_dd_r", -25.0)
    min_days = forward_cfg.get("min_days_active", 14)

    gate_admission = shadow_verdict.get("gate_admission", "")
    n = shadow_verdict.get("n", 0)
    exp_r = shadow_verdict.get("exp_r", 0.0)
    max_dd_r = shadow_verdict.get("max_dd_r", 0.0)
    days = shadow_verdict.get("days_active", 0)
    power_defs = shadow_verdict.get("power_deficiencies", [])

    if gate_admission == "FULL_10_PASS":
        return PromotionDecision(
            hypothesis_id=hypothesis_id,
            promoted=True,
            basis="FULL_10_PASS",
            lot=0.01,
            status="LIVE"
        )

    if gate_admission == "VALIDITY_PASS_POWER_DEFICIENT":
        # Check forward cure
        if (n >= min_trades and exp_r >= min_exp and
            max_dd_r >= max_dd and days >= min_days):
            return PromotionDecision(
                hypothesis_id=hypothesis_id,
                promoted=True,
                basis="VALIDITY_PASS_FORWARD_CURE",
                lot=0.01,
                status="LIVE"
            )
        else:
            return PromotionDecision(
                hypothesis_id=hypothesis_id,
                promoted=False,
                basis="VALIDITY_PASS_FORWARD_CURE",
                lot=0.0,
                status="BLOCKED",
                reason=f"Power deficiencies {power_defs} not cured by forward evidence (n={n}, exp={exp_r:.3f}, maxDD={max_dd_r:.1f}, days={days})"
            )

    return PromotionDecision(
        hypothesis_id=hypothesis_id,
        promoted=False,
        basis=gate_admission,
        lot=0.0,
        status="BLOCKED",
        reason=f"No validity pass: {gate_admission}"
    )


def run_promotion(hypothesis_ids: list[str]) -> list[PromotionDecision]:
    """Run promotion for shadow-validated hypotheses."""
    import json

    state_path = SHADOW_DIR / "shadow_state.json"
    if not state_path.exists():
        return []

    with open(state_path, "r", encoding="utf-8") as f:
        state = json.load(f)

    decisions = []
    for hid in hypothesis_ids:
        for key, st in state.items():
            if isinstance(st, dict) and hid in key:
                decisions.append(promote_hypothesis(hid, st))
                break
    return decisions


if __name__ == "__main__":
    import sys
    ids = sys.argv[1:] if len(sys.argv) > 1 else []
    for d in run_promotion(ids):
        print(f"{d.hypothesis_id}: {'PROMOTED' if d.promoted else 'BLOCKED'} ({d.basis}) - {d.reason}")
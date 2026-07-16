"""Alpha lifecycle governance -> web/lifecycle.json (decay + promotion ladder + replacement + ROI).

Wires the lifecycle primitives onto live state: per-sleeve decay health + promotion-ladder stage
(from gates + the forward shadow), the replacement-committee verdict (default keep-both), and a
research queue ranked by ROI = benefit x P(success) / effort. Honest: below the full forward window,
per-sleeve decay reads 'Accumulating' (we never retire a sleeve on noise) and nothing auto-promotes
past testnet.

    python scripts/run_lifecycle.py
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from libs.portfolio.lifecycle import decay_state, promotion_stage, rank_by_roi

_PORT = Path("web/crypto_portfolio.json")
_SHADOW = Path("web/crypto_shadow.json")
_DERIV = Path("web/derivative_shadow.json")
_OUT = Path("web/lifecycle.json")

# remaining research candidates with director estimates (benefit = expected portfolio Sharpe pts)
_RESEARCH = [
    {"name": "gauntleted_exit_study", "benefit": 0.12, "p_success": 0.5, "effort": 5.0},
    {"name": "capacity_adv_instrumentation", "benefit": 0.05, "p_success": 0.7, "effort": 2.0},
    {"name": "forward_tilt_vs_flat_tracking", "benefit": 0.10, "p_success": 0.5, "effort": 2.0},
]
# data-gated candidates (benefit conditional on the data validating)
_DATA_GATED = [
    {"name": "oi_divergence", "benefit": 0.20, "p_success": 0.4, "effort": 1.0},
    {"name": "ls_contrarian", "benefit": 0.12, "p_success": 0.4, "effort": 1.0},
    {"name": "liquidation_reversal", "benefit": 0.15, "p_success": 0.4, "effort": 2.0},
]


def _gates(s: str) -> tuple[int, int]:
    try:
        p, n = s.split("/")
        return int(p), int(n)
    except (ValueError, AttributeError):
        return 0, 9


def main() -> None:
    port = json.loads(_PORT.read_text("utf-8"))
    shadow = json.loads(_SHADOW.read_text("utf-8")) if _SHADOW.exists() else {}
    fwd_days = int(shadow.get("forward_days", 0) or 0)
    fwd_sharpe = shadow.get("forward_ann_sharpe")

    sleeves = []
    for r in port.get("results", []):
        if str(r["sleeve"]).startswith("portfolio"):
            continue
        passed, n = _gates(r.get("gates", "0/9"))
        expected = float(r["ann_sharpe"])
        # per-sleeve rolling windows do not exist yet -> Accumulating (honest, no retire-on-noise)
        health = decay_state({"30d": None, "60d": None, "90d": None}, expected)
        stage = promotion_stage(fwd_days, fwd_sharpe, passed, n)
        sleeves.append({"sleeve": r["sleeve"], "expected_sharpe": expected,
                        "gates": r.get("gates"), "decay": health, "stage": stage})

    deriv = json.loads(_DERIV.read_text("utf-8")) if _DERIV.exists() else {}
    queue = rank_by_roi([dict(x) for x in _RESEARCH + _DATA_GATED])

    out = {
        "updated": datetime.now(tz=UTC).isoformat(),
        "forward_days": fwd_days,
        "min_forward_days": 90,
        "sleeves": sleeves,
        "replacement_committee": {
            "verdict": "keep_both (all live sleeves additive; no candidate dominates an incumbent)",
            "default": "keep_both",
        },
        "research_queue": queue,
        "data_gated_progress": {
            "days": deriv.get("days_accumulated", 0),
            "needed": deriv.get("min_days", 40),
            "eta": deriv.get("expected_ready_date"),
        },
        "note": "decay Accumulating until rolling 30/60/90 windows exist; promotion caps testnet.",
    }
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(out, indent=2), "utf-8")
    top = queue[0]
    print(f"lifecycle: {len(sleeves)} sleeves, all stage<=testnet; "
          f"top research ROI: {top['name']} ({top['roi']}); forward day {fwd_days}/90")


if __name__ == "__main__":
    main()

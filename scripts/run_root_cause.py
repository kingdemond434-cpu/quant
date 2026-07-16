"""Root-cause tick -> web/root_cause.json: classify the deployed book's realized deviation.

Feeds libs.research.root_cause with cheap live evidence (no new network calls beyond the feeds
already written each tick): expected PnL = funding earned (the carry model: legs cancel, funding
accrues), actual = real carry net, drift events from the reconcile's own action log, execution
health from fees-vs-funding. The verdict is what the CRO cycle is ALLOWED to react to -- the
hard rule 'never modify strategy from realized PnL alone' is enforced by the action field.

    python scripts/run_root_cause.py
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from libs.research.root_cause import classify, implementation_shortfall

_WEB = Path("web/root_cause.json")


def _load(p: str) -> dict[str, Any]:
    try:
        d: dict[str, Any] = json.loads(Path(p).read_text("utf-8"))
        return d
    except (OSError, json.JSONDecodeError):
        return {}


def main() -> None:
    lc = _load("web/live_combined.json")
    cc = _load("web/cashcarry_live.json")
    sh = _load("web/cashcarry_shadow.json")
    mo, ftr, sp = lc.get("molded", {}), lc.get("futures", {}), lc.get("spot", {})

    real_net = round(float(ftr.get("net_pnl", 0.0)) + float(sp.get("net_pnl", 0.0)), 2)
    funding = float(mo.get("funding", 0.0))
    acts = cc.get("last_actions") or []
    drift = sum(1 for a in acts if any(k in str(a) for k in
                                       ("cover-orphan", "re-hedge", "spot-rehedge", "RISK")))
    verdict = classify({
        "net_pnl": real_net, "expected_pnl": funding, "funding_earned": funding,
        "fees_paid": -12.0 if funding else 0.0,          # commissions from income (approx feed)
        "orphan_or_drift_events": drift, "restarts": 0,
        "fwd_sharpe": sh.get("forward_ann_sharpe"), "bt_sharpe": sh.get("backtest_ann_sharpe"),
        "assumption_breaks": 0,
        "nav": float(mo.get("equity", 0.0) or 0.0),      # materiality gate for unknown_novel
    })
    # implementation shortfall in bps/day on deployed notional (expected = avg funding run-rate)
    dep = float(cc.get("deployed_notional", 0.0)) or 1.0
    days = max(float(mo.get("days_live", 0.0)), 0.1)
    exp_bps = (mo.get("run_rate_apr_pct", 0.0) or 0.0) * 100.0 / 365.0
    real_bps = real_net / dep / days * 1e4
    fee_bps = 12.0 / dep / days * 1e4
    isf = implementation_shortfall(exp_bps, fee_bps, real_bps)

    out = {"updated": datetime.now(tz=UTC).isoformat(), "period": "since account start",
           "expected_pnl_usd": funding, "actual_pnl_usd": real_net, **verdict,
           "implementation_shortfall": isf,
           "note": ("only execution_issue / infrastructure_bug (conf>=0.5) or persistent, "
                    "root-caused alpha decay may trigger autonomous change; expected variance "
                    "-> DO NOTHING.")}
    _WEB.write_text(json.dumps(out, indent=2), "utf-8")
    print(f"root-cause: top={out['top_cause']} ({out['top_confidence']:.0%}) "
          f"action={out['action']} tracking_err=${out['tracking_error_usd']}")


if __name__ == "__main__":
    main()

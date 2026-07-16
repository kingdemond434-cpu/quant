"""Dynamic capital allocator (items 1-3,5,9 of the build) -> web/allocation.json.

Turns the per-sleeve Sharpes + correlation matrix the portfolio engine already produces into a
capital allocation across sleeves, comparing equal-weight / max-Sharpe / risk-parity and a
RECOMMENDED book that is: max-Sharpe, 50/50 anti-overfit-blended with equal-weight, then 35%
concentration-capped and regime-tilted (blend with regime_alloc.json). Reports each scheme's
expected portfolio Sharpe, per-sleeve marginal contribution, capacity flag, and turnover vs the
current live target -- plus whether a WEEKLY rebalance is due. SHADOW: this is advisory; it does not
auto-resize live capital (unvalidated). Promotion needs it to beat flat in the forward shadow.

    python scripts/run_allocation.py
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from libs.portfolio.construction import (
    blend,
    concentration_cap,
    marginal_sharpe,
    max_sharpe_weights,
    portfolio_sharpe,
    turnover,
)
from libs.portfolio.covariance import erc_weights
from libs.portfolio.hrp import hrp_weights
from libs.portfolio.risk_parity import risk_parity_weights

_PORT = Path("web/crypto_portfolio.json")
_REGALLOC = Path("web/regime_alloc.json")
_STATE = Path("data/allocation_state.json")
_OUT = Path("web/allocation.json")
_CAP = 0.35
_REBALANCE_DAYS = 7


def _wmap(sleeves: list[str], w: np.ndarray) -> dict[str, float]:
    return {s: round(float(x), 4) for s, x in zip(sleeves, w, strict=True)}


def main() -> None:
    port = json.loads(_PORT.read_text("utf-8"))
    rows = [r for r in port.get("results", []) if not str(r["sleeve"]).startswith("portfolio")]
    sleeves = [r["sleeve"] for r in rows]
    sharpes = np.array([float(r["ann_sharpe"]) for r in rows])
    cmap = port.get("correlations", {})
    n = len(sleeves)
    corr = np.array([[float(cmap.get(a, {}).get(b, 1.0 if a == b else 0.0))
                      for b in sleeves] for a in sleeves])

    eq = np.full(n, 1.0 / n)
    ms = max_sharpe_weights(sharpes, corr)
    rp = risk_parity_weights(corr)
    hrp = hrp_weights(corr)                                  # hierarchical risk parity (de Prado)
    erc = erc_weights(corr)                                  # equal risk contribution
    # recommended: max-Sharpe, anti-overfit blended 50/50 with equal, then concentration-capped
    rec = concentration_cap(blend(ms, eq, 0.5), _CAP)
    # regime tilt: blend 70/30 with the regime allocator's tilt if available and aligned
    regime = "—"
    try:
        ra = json.loads(_REGALLOC.read_text("utf-8"))
        tilt = np.array([float(ra.get("tilt_weights", {}).get(s, 0.0)) for s in sleeves])
        if tilt.sum() > 0:
            rec = concentration_cap(blend(rec, tilt / tilt.sum(), 0.7), _CAP)
            regime = ra.get("regime", "—")
    except (OSError, ValueError):
        pass

    schemes = {"equal_weight": eq, "max_sharpe": ms, "risk_parity": rp,
               "hrp": hrp, "erc": erc, "recommended": rec}
    sharpe_by = {k: round(portfolio_sharpe(v, sharpes, corr), 3) for k, v in schemes.items()}
    mc = marginal_sharpe(rec, sharpes, corr)

    # weekly rebalance gate
    prev = json.loads(_STATE.read_text("utf-8")) if _STATE.exists() else {}
    last = prev.get("last_rebalance")
    now = datetime.now(tz=UTC)
    due = True
    if last:
        try:
            due = (now - datetime.fromisoformat(last)).days >= _REBALANCE_DAYS
        except ValueError:
            due = True
    prev_w = prev.get("weights", {})
    tnover = round(turnover(prev_w, _wmap(sleeves, rec)), 4) if prev_w else None
    if due:
        _STATE.parent.mkdir(parents=True, exist_ok=True)
        _STATE.write_text(json.dumps({"last_rebalance": now.isoformat(),
                                      "weights": _wmap(sleeves, rec)}, indent=2), "utf-8")

    out = {
        "updated": now.isoformat(),
        "status": "SHADOW",
        "regime": regime,
        "concentration_cap": _CAP,
        "rebalance_due": bool(due),
        "rebalance_every_days": _REBALANCE_DAYS,
        "turnover_vs_prev": tnover,
        "sleeves": sleeves,
        "expected_sharpe_theoretical": sharpe_by,
        "uplift_vs_equal": round(sharpe_by["recommended"] - sharpe_by["equal_weight"], 3),
        "realized_flat_sharpe": port.get("headline_sharpe"),
        "weights": {k: _wmap(sleeves, v) for k, v in schemes.items()},
        "marginal_contribution": _wmap(sleeves, mc),
        "capacity_note": "capacity hook present; per-sleeve $ ADV not yet measured (neutral)",
        "honesty": ("expected_sharpe is the THEORETICAL quadrature of standalone in-sample Sharpes "
                    f"-- optimistic vs realized {port.get('headline_sharpe')} (fails DSR). Only "
                    "the RELATIVE uplift vs equal is actionable, after shadow."),
    }
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(out, indent=2), "utf-8")
    print(f"allocation: recommended Sharpe {sharpe_by['recommended']} vs equal "
          f"{sharpe_by['equal_weight']} (uplift {out['uplift_vs_equal']}); "
          f"rebalance {'DUE' if due else 'not due'}; regime {regime}")


if __name__ == "__main__":
    main()

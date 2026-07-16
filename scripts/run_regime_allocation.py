"""Regime-aware capital allocation (SHADOW — advisory, never auto-applied to live capital).

Tilts sleeve weights toward the sleeves with the best Sharpe IN THE CURRENT REGIME, read from the
live regime tag (data/crypto_regime.json) and the per-regime sleeve-Sharpe table that the portfolio
engine already produces (web/crypto_portfolio.json -> regimes). The regime Sharpes are IN-SAMPLE, so
this blends the tilt 50/50 with equal-weight (a hard anti-overfit cap) and is published as a SHADOW
recommendation only -- real capital is never auto-allocated to an unvalidated tilt. Writes
web/regime_alloc.json. Promotion to live requires the tilt to beat flat in the forward shadow.

    python scripts/run_regime_allocation.py
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

_PORT = Path("web/crypto_portfolio.json")
_REG = Path("data/crypto_regime.json")
_OUT = Path("web/regime_alloc.json")
_SLEEVES = ["funding_carry", "basis_carry", "taker_flow", "xsec_price_mom", "ts_trend"]


def main() -> None:
    port = json.loads(_PORT.read_text("utf-8"))
    regimes = port.get("regimes", {})
    reg = json.loads(_REG.read_text("utf-8")) if _REG.exists() else {}
    trend, vol = reg.get("trend", "bull"), reg.get("vol", "low_vol")
    keys = [f"trend:{trend}", f"vol:{vol}"]

    acc = dict.fromkeys(_SLEEVES, 0.0)
    cnt = 0
    for k in keys:
        if k in regimes:
            cnt += 1
            for s in _SLEEVES:
                acc[s] += float(regimes[k].get(s, 0.0))
    in_regime = {s: (acc[s] / cnt if cnt else 0.0) for s in _SLEEVES}

    pos = {s: max(0.0, in_regime[s]) for s in _SLEEVES}      # only positive in-regime edge tilts
    tot = sum(pos.values()) or 1.0
    tilt = {s: pos[s] / tot for s in _SLEEVES}
    eq = 1.0 / len(_SLEEVES)
    blended = {s: round(0.5 * tilt[s] + 0.5 * eq, 4) for s in _SLEEVES}  # 50% cap vs equal-weight

    flat_sharpe = port.get("portfolio_flat_sharpe")
    out = {
        "updated": datetime.now(tz=UTC).isoformat(),
        "regime": reg.get("regime", "—"),
        "regime_keys": keys,
        "in_regime_sharpe": {s: round(in_regime[s], 2) for s in _SLEEVES},
        "equal_weight": round(eq, 4),
        "tilt_weights": blended,
        "flat_portfolio_sharpe": flat_sharpe,
        "status": "SHADOW",
        "note": ("in-sample regime Sharpe; 50% tilt / 50% equal-weight anti-overfit cap; "
                 "advisory only -- not auto-applied to live capital; must beat flat in shadow"),
    }
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(out, indent=2), "utf-8")
    top = max(blended, key=lambda s: blended[s])
    print(f"regime {out['regime']} -> tilt top: {top} {blended[top]:.0%} "
          f"(in-regime Sharpe {out['in_regime_sharpe'][top]}); SHADOW only")


if __name__ == "__main__":
    main()

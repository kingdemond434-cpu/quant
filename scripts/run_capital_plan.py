"""Capital & sizing plan -> web/capital_plan.json: net profit SIZE (not rate), validation-gated.

Net profit $ = CAGR x capital. This projects $ outcomes at several capital levels using only the
VALIDATED (forward) edge -- never the in-sample fantasy -- so the headline ramps with proof, not
hope. Reflects the carry book's capacity ceiling and the Portfolio-Margin capital-efficiency
multiplier (cross-collateral lets the same dollars back spot + perp). Pure arithmetic, no overfit.

    python scripts/run_capital_plan.py
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_SHADOW = Path("web/crypto_shadow.json")
_CC = Path("web/cashcarry_shadow.json")
_LEV = Path("data/leverage_target.json")
_OUT = Path("web/capital_plan.json")

# honest capacity ceiling for a top-liquid-perp carry book on one venue (USD notional, rough).
_CAPACITY_USD = 2_000_000.0
_PM_EFFICIENCY = 1.8                              # Portfolio Margin cross-collateral multiplier (~)
_CAPITAL_LEVELS = [3_846.0, 25_000.0, 100_000.0, 500_000.0, 2_000_000.0]


def _load(p: Path) -> dict[str, Any]:
    try:
        return json.loads(p.read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def main() -> None:
    sh, cc, lev = _load(_SHADOW), _load(_CC), _load(_LEV)
    fwd_days = int(sh.get("forward_days", 0) or 0)
    fwd_sharpe = float(sh.get("forward_ann_sharpe") or 0.0)
    cc_days = int(cc.get("forward_days", 0) or 0)
    leverage = float(lev.get("gated_leverage", 3.0) or 3.0)
    validated = fwd_sharpe > 0.0 and fwd_days >= 30

    # honest CAGR estimate: 0 until forward edge proves; then a conservative carry CAGR scaled by
    # leverage. We deliberately CAP the assumed CAGR well below the in-sample fantasy.
    validated_cagr = round(min(0.04 * leverage, 0.25), 3) if validated else 0.0

    rows = []
    for cap in _CAPITAL_LEVELS:
        eff_cap = cap * _PM_EFFICIENCY                       # Portfolio Margin cross-collateral
        deployable = min(eff_cap, _CAPACITY_USD)            # capacity-capped
        capped = deployable < eff_cap
        rows.append({
            "capital_usd": cap,
            "effective_capital_pm": round(eff_cap, 0),
            "deployable_usd": round(deployable, 0),
            "capacity_capped": capped,
            "net_profit_yr_usd": round(deployable * validated_cagr, 0),
        })

    out = {
        "updated": datetime.now(tz=UTC).isoformat(),
        "validated": validated,
        "validated_cagr_used": validated_cagr,
        "leverage": leverage,
        "forward_days": fwd_days, "cashcarry_forward_days": cc_days,
        "capacity_usd": _CAPACITY_USD, "pm_efficiency": _PM_EFFICIENCY,
        "levels": rows,
        "pm_steps": ["Live Binance account (Spot + USD-M Futures wallets, one login)",
                     "Enable Portfolio Margin (eligibility: min equity + cross-margin terms)",
                     "Long spot collateralises short perp -> ~1.8x effective capital for carry"],
        "note": ("Net profit SIZE = CAGR x capital. CAGR is held at 0 until the forward shadow "
                 f"validates (now fwd day {fwd_days}/90, cash-carry {cc_days}/90), then a "
                 "CONSERVATIVE carry CAGR (capped 0.25), never the in-sample number. Scale "
                 "capital only on proof; PM multiplies effective capital; capacity caps the top."),
    }
    _OUT.write_text(json.dumps(out, indent=2), "utf-8")
    tag = f"{validated_cagr*100:.0f}% CAGR" if validated else "UNVALIDATED -> $0 until proven"
    print(f"capital plan: {tag} | leverage {leverage}x | "
          f"$100k -> ${rows[2]['net_profit_yr_usd']:.0f}/yr (PM eff, capacity-capped) | "
          f"capacity ${_CAPACITY_USD:,.0f}")


if __name__ == "__main__":
    main()

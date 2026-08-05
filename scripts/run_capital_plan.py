"""Capital & sizing plan -> web/capital_plan.json: net profit SIZE (not rate), validation-gated.

Net profit $ = CAGR x capital. This projects $ outcomes at several capital levels using only the
VALIDATED (forward) edge -- never the in-sample fantasy -- so the headline ramps with proof, not
hope. Reflects the carry book's capacity ceiling and the Portfolio-Margin capital-efficiency
multiplier (cross-collateral lets the same dollars back spot + perp). Pure arithmetic, no overfit.

    python scripts/run_capital_plan.py
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from libs.research.event_density import t_from_annual_sharpe  # noqa: E402
from libs.research.evidence_clock import MIN_OBS, MIN_T  # noqa: E402

_SHADOW = Path("web/crypto_shadow.json")
#: Annualisation used by the producer of _SHADOW (run_crypto_shadow.py `_PPY`). Kept beside the
#: path it belongs to: a Sharpe is only invertible to a t if you know what annualised it.
_SHADOW_PPY = 365.0
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

    # EVIDENCE, NOT CALENDAR (L1.48). The gate here was `fwd_sharpe > 0.0 and fwd_days >= 30`, and
    # on 2026-08-05 it was publishing validated=True on a forward Sharpe of 0.29 over 33 days --
    # a t-statistic of 0.105, indistinguishable from zero -- while the shadow runner reading THE
    # SAME artifact published "ACCUMULATING (33/90+ days)". Two consumers of one file disagreeing,
    # with the looser one driving the capital headline.
    #
    # An annualised Sharpe is a RATE and carries no sample size, so `sharpe > 0` cannot tell 0.29
    # on 33 observations from 0.29 on 3,300. Asking for the t-statistic is what the day-count was
    # standing in for, and asking it directly is both TIGHTER here and faster for a book that
    # actually accrues: a fast sleeve clears on evidence rather than waiting out a calendar.
    # _SHADOW is written by run_crypto_shadow.py, which annualises with sqrt(365) -- so the
    # inversion must use 365 too. Inverting a 365-annualised Sharpe with the 252 default would
    # inflate every t by sqrt(365/252) = 1.20, loosening this gate by arithmetic nobody re-reads.
    fwd_t = t_from_annual_sharpe(fwd_sharpe, fwd_days, periods_per_year=_SHADOW_PPY)
    validated = bool(fwd_sharpe > 0.0 and fwd_days >= MIN_OBS and fwd_t >= MIN_T)

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
        "validation_basis": (
            f"t={fwd_t:.2f} vs bar {MIN_T} on {fwd_days} forward observations "
            f"(annualised Sharpe {fwd_sharpe:.2f}); evidence, not elapsed days (L1.48)"),
        "forward_tstat": round(fwd_t, 3),
        "validation_bar_t": MIN_T,
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

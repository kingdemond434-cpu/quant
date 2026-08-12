"""Historical backtest of the derivative-data sleeves on REAL Binance history (no waiting).

Binance serves ~30 days of open-interest and long/short history (openInterestHist /
globalLongShortAccountRatio). At HOURLY frequency that is ~480 points -> enough samples to run the
full gauntlet now (CPCV/DSR/PBO/Reality-Check via the existing validator), net of cost. Builds:
  * oi_divergence -- the price/OI confirmation-vs-divergence thesis (reduces to cross-sectional OI
                     direction: long rising-OI, short falling-OI), market-neutral.
  * ls_contrarian -- fade crowded retail positioning, -zscore(long/short), market-neutral.
LIQUIDATION REVERSAL IS NOT BACKTESTED: Binance has NO liquidation REST history, so it remains
forward-only (see liquidation_listener). HONESTY: the sample is ~20-30 days = ONE regime, so even a
pass is low-confidence; forward validation is still required before production. Nothing fabricated.

    python scripts/run_derivative_backtest.py
"""

from __future__ import annotations

import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

_ROOT = Path("/home/quant/quant-platform")
if not _ROOT.exists():
    _ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from libs.autodiscovery.models import Family, Hypothesis  # noqa: E402
from libs.autodiscovery.validation import campaign_gate_stats, validate  # noqa: E402
from libs.data.crypto_source import (  # noqa: E402
    fetch_klines,
    fetch_long_short_hist,
    fetch_open_interest_hist,
    list_liquid_perps,
)
from libs.validation.dsr import sharpe_ratio  # noqa: E402
from libs.validation.economic_prior import MechanismType  # noqa: E402

_OUT = Path("web/derivative_backtest.json")
_PPY = 24 * 365.0                      # hourly annualisation
_COST = 0.0005                         # 5 bps per unit one-way turnover (taker + slippage)
_FAIL = ["edge crowds/decays", "regime shift", "thin sample (~1 regime)", "cost exceeds edge"]


def _panels(symbols: list[str]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    px, oi, ls = {}, {}, {}
    start_ms = int((time.time() - 27 * 86400) * 1000)
    for s in symbols:
        try:
            o = fetch_open_interest_hist(s, period="1h", limit=500)
            lsd = fetch_long_short_hist(s, period="1h", limit=500)
            k = fetch_klines(s, interval="1h", start_ms=start_ms)
        except Exception:
            continue
        if o.empty or lsd.empty or k.empty:
            continue
        px[s] = k.set_index("timestamp")["close"].astype(float)
        oi[s] = o.set_index("timestamp")["open_interest"].astype(float)
        ls[s] = lsd.set_index("timestamp")["ls_ratio"].astype(float)
        time.sleep(0.15)               # be gentle on the data endpoints
    p = pd.DataFrame(px).sort_index()
    o = pd.DataFrame(oi).reindex(p.index).ffill()
    la = pd.DataFrame(ls).reindex(p.index).ffill()
    return p, o, la


def _neutral_weights(signal: pd.DataFrame) -> pd.DataFrame:
    w = signal.sub(signal.mean(axis=1), axis=0)            # cross-sectional demean (neutral)
    return w.div(w.abs().sum(axis=1) + 1e-9, axis=0)       # gross 1 each bar


def _sleeve_return(weights: pd.DataFrame, fwd: pd.DataFrame) -> np.ndarray:
    gross = (weights * fwd).sum(axis=1)
    cost = _COST * weights.diff().abs().sum(axis=1)        # turnover cost (hourly => material)
    return (gross - cost).dropna().to_numpy()


def main() -> None:
    syms = list_liquid_perps(top_n=30)
    px, oi, ls = _panels(syms)
    if px.shape[1] < 8:
        raise SystemExit("insufficient derivative history panel")
    fwd = px.pct_change().shift(-1)                        # next-hour return, no lookahead
    d_oi = oi.pct_change()
    oi_w = _neutral_weights(np.sign(d_oi))                 # divergence thesis -> OI direction
    ls_z = ls.sub(ls.mean(axis=1), axis=0).div(ls.std(axis=1) + 1e-9, axis=0)
    ls_w = _neutral_weights(-ls_z)                         # fade the crowd

    sleeves = {"oi_divergence": _sleeve_return(oi_w, fwd),
               "ls_contrarian": _sleeve_return(ls_w, fwd)}
    n = min(len(v) for v in sleeves.values())
    matrix = np.column_stack([v[-n:] for v in sleeves.values()])
    sharpes = np.array([sharpe_ratio(v[v != 0.0]) for v in sleeves.values()])
    # per-candidate gates (gap #87 flip, principal-ruled 2026-07-29); thresholds unchanged
    campaign = campaign_gate_stats(matrix)
    corr = float(np.corrcoef(matrix[:, 0], matrix[:, 1])[0, 1])

    results = []
    # enumerate order == column_stack order over `sleeves`, so `col` is the sleeve's matrix column
    for col, (name, r) in enumerate(sleeves.items()):
        active = r[r != 0.0]
        ann = round(float(sharpe_ratio(active) * np.sqrt(_PPY)), 2) if len(active) > 5 else 0.0
        v = (validate(active, hypothesis=Hypothesis(
            family=Family.CARRY, subtype=name, symbol="CRYPTO", params={},
            mechanism=MechanismType.RISK_PREMIUM, edge_source=name, failure_modes=_FAIL),
            periods_per_year=_PPY,        # 1h bars, 24/7 (R0086)
            n_trials=2, sharpe_estimates=sharpes, returns_matrix=matrix,
            campaign=campaign, column=col)
            if len(active) >= 250 else None)
        gates = f"{sum(v.gates.values())}/{len(v.gates)}" if v else "n<250"
        results.append({"sleeve": name, "ann_sharpe": ann, "n_obs": len(active),
                        "gates": gates,
                        "pbo": round(float(v.metrics.pbo), 3) if v else None,
                        "rc_p": round(float(v.metrics.reality_p), 3) if v else None,
                        "survived": bool(v.survived) if v else False,
                        "failed_gates": [k for k, ok in v.gates.items() if not ok] if v else []})

    span_h = int(px.shape[0])
    out = {
        "updated": datetime.now(tz=UTC).isoformat(),
        "frequency": "1h", "symbols": int(px.shape[1]),
        "bars": span_h, "calendar_days": round(span_h / 24, 1),
        "cost_bps_per_turn": _COST * 1e4,
        # campaign-level legacy PBO/RC kept as SEARCH-PROCEDURE diagnostics (gap #87); the gate
        # values are per-sleeve now -- see results[*].pbo / results[*].rc_p.
        "pbo": (round(float(campaign.legacy_pbo.pbo), 3)
                if campaign is not None and campaign.legacy_pbo is not None else None),
        "reality_check_p": (round(float(campaign.legacy_rc.p_value), 3)
                            if campaign is not None and campaign.legacy_rc is not None else None),
        "oi_ls_correlation": round(corr, 3),
        "results": results,
        "liquidation_reversal": "NOT backtested -- no REST history; forward-only (listener up)",
        "honesty": ("~20-30 day sample = ONE regime; low statistical power. A pass here is "
                    "PRELIMINARY -- forward validation (40-90d) still required before production. "
                    "Hourly turnover makes cost decisive; results are net of 5bps/turn."),
    }
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(out, indent=2), "utf-8")
    for r in results:
        print(f"  {r['sleeve']:15} annSharpe~{r['ann_sharpe']:5} n={r['n_obs']:4} "
              f"gates={r['gates']:5} pbo={r['pbo']} rc_p={r['rc_p']} survived={r['survived']}")
    print(f"campaign diagnostics pbo={out['pbo']} rc_p={out['reality_check_p']} (gates per-sleeve) "
          f"corr(oi,ls)={out['oi_ls_correlation']} "
          f"over {out['calendar_days']}d -- PRELIMINARY (one regime)")


if __name__ == "__main__":
    main()

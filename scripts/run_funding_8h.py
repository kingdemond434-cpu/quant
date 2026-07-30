"""Funding carry at NATIVE 8h frequency -- the honest shot at a real survivor.

Funding settles every 8h; testing it on daily-aggregated bars (what we did) discards 2/3 of the
observations and blurs the timing. Funding carry is the program's pre-registered #1 edge (ranked
before any testing), so running it at its native resolution -- with ~3x the independent observations
-- is the correct test, not a new trial. More observations = far more power for the deflated-Sharpe
gate that has blocked everything. Reported straight: survivor or not.

    python scripts/run_funding_8h.py
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from libs.autodiscovery.models import Family, Hypothesis
from libs.autodiscovery.validation import campaign_gate_stats, validate
from libs.data.crypto_source import bars_with_funding, list_liquid_perps
from libs.research.crypto_xsec import xsec_funding_returns
from libs.validation.dsr import sharpe_ratio
from libs.validation.economic_prior import MechanismType

_OUT = Path("reports/funding_8h")
_PPY = 365.0 * 3.0          # 8h bars -> 1095 periods/year
_FAIL = ["funding dispersion compresses", "leverage/borrow constraints",
         "correlated crypto crash", "edge decay"]


def _panels(universe: list[str]) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, float]]:
    closes, fundings, adv = {}, {}, {}
    for s in universe:
        try:
            bars = bars_with_funding(s, interval="8h", start="2020-01-01")
        except Exception:  # transient symbol
            continue
        if bars.empty or len(bars) < 750:
            continue
        bars = bars.set_index("timestamp")
        closes[s] = bars["close"]
        fundings[s] = bars["funding"]
        adv[s] = float((bars["close"] * bars["volume"]).tail(540).mean())
    close = pd.DataFrame(closes).sort_index()
    return close, pd.DataFrame(fundings).reindex(close.index), adv


def main() -> None:
    universe = list_liquid_perps(top_n=70)
    print(f"fetching 8h bars+funding for {len(universe)} perps (native funding resolution)...")
    close, funding, adv = _panels(universe)
    if close.shape[1] < 12:
        raise SystemExit("need a liquid 8h panel")
    print(f"8h panel: {close.shape[1]} perps x {close.shape[0]} bars "
          f"({close.index[0].date()}..{close.index[-1].date()})  ~{close.shape[0] // 3} days")

    # lookbacks in 8h periods: 21 = 7 days, 9 = 3 days (the frozen daily variants at 8h resolution)
    variants = [("lb21_q20", 21, 0.2, 0.02), ("lb9_q20", 9, 0.2, 0.02), ("lb42_q20", 42, 0.2, 0.02)]
    series = [(n, xsec_funding_returns(close, funding, adv, lookback=lb, q=q, band=b))
              for n, lb, q, b in variants]
    min_len = min(len(r) for _, r in series)
    matrix = np.column_stack([r[-min_len:] for _, r in series])
    sharpes = np.array([sharpe_ratio(r[r != 0.0]) for _, r in series])
    # per-candidate gates (gap #87 flip, principal-ruled 2026-07-29); thresholds unchanged
    campaign = campaign_gate_stats(matrix)

    survivors, results = 0, []
    # enumerate order == column_stack order over `series`, so `col` is the variant's matrix column
    for col, ((name, r), spr) in enumerate(zip(series, sharpes, strict=True)):
        active = r[r != 0.0]
        v = validate(active, hypothesis=Hypothesis(
            family=Family.CARRY, subtype=f"funding8h_{name}", symbol="CRYPTO_8H", params={},
            mechanism=MechanismType.RISK_PREMIUM, edge_source="funding carry @ native 8h",
            failure_modes=_FAIL), n_trials=len(series), sharpe_estimates=sharpes,
            returns_matrix=matrix, campaign=campaign, column=col) if len(active) >= 250 else None
        survived = bool(v.survived) if v else False
        survivors += int(survived)
        gates = v.gates if v else {}
        results.append({"variant": name, "bars": len(active),
                        "ann_sharpe": round(float(spr) * np.sqrt(_PPY), 2), "survived": survived,
                        "gates": f"{sum(gates.values())}/{len(gates)}" if gates else "n<250",
                        "fails": [k for k, ok in gates.items() if not ok]})

    _OUT.mkdir(parents=True, exist_ok=True)
    (_OUT / "report.json").write_text(json.dumps(
        {"perps": close.shape[1], "bars": close.shape[0], "survivors": survivors,
         "variants": results}, indent=2), "utf-8")
    print(f"\n[funding @ 8h] tested={len(series)} survivors={survivors}")
    for r in results:
        print(f"  {r['variant']:10} bars={r['bars']:5} ann_sharpe~{r['ann_sharpe']:6} "
              f"gates={r['gates']:5} survived={r['survived']}  fails={r['fails']}")
    if survivors:
        print("\n*** SURVIVOR(S) at native 8h funding resolution. ***")
    else:
        print("\nstill 0 survivors at 8h (honest).")


if __name__ == "__main__":
    main()

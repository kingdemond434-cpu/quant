"""Autonomous edge-discovery loop -- the self-expanding factory.

Tests a LIBRARY of economically-distinct crypto sleeves (not parameter sweeps -- that would p-hack
the DSR gate) through the full institutional gauntlet, measures each candidate's standalone Sharpe,
its correlation to the rest of the book, and its incremental portfolio-Sharpe contribution, then
classifies it through the promotion pipeline. Genuinely orthogonal, positive sleeves are surfaced as
shadow-eligible automatically; the rest are recorded as candidates or rejected (with the reason).
Data-gated mechanisms (OI/long-short divergence) are listed as PENDING until their forward archive
matures. Re-run daily: as archives grow, new edges light up on their own. Writes web/discovery.json.

    python scripts/run_discovery.py
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from libs.autodiscovery.models import Family, Hypothesis
from libs.autodiscovery.validation import (
    blocking_constant_gates,
    campaign_gate_stats,
    counterfactual_survivors,
    gate_discrimination,
    validate,
)
from libs.data.crypto_source import list_liquid_perps
from libs.data.instruments import AssetClass, InstrumentSpec, register_instrument
from libs.data.lake import Layer, ParquetLake
from libs.data.timeframe import Timeframe
from libs.data.universe import RESEARCH_TOP_N
from libs.research.crossasset import trend_basket_returns, xsec_momentum_returns
from libs.research.crypto_sleeves import (
    basis_carry_returns,
    funding_momentum_returns,
    taker_flow_returns,
    xsec_lowvol_returns,
)
from libs.research.crypto_xsec import adv_tier_cost, xsec_funding_returns
from libs.validation.dsr import sharpe_ratio
from libs.validation.economic_prior import MechanismType

_CRYPTO = Path("data/lake/bronze/crypto")
_METRICS = Path("data/crypto_metrics.parquet")
_WEB = Path("web/discovery.json")
_PPY = 365.0
_ORTHO = 0.40                 # max |corr| to the rest of the book to count as orthogonal
_FAIL = ["edge crowds/decays", "regime shift", "correlated crash", "cost exceeds edge"]
# Data-gated mechanisms that turn on once their forward archive is deep enough.
_PENDING = [
    ("oi_divergence", "open interest", 40),
    ("ls_contrarian", "long/short ratio", 40),
    ("liquidation_reversal", "liquidations", 40),
]


def _panels() -> tuple[pd.DataFrame, ...]:
    lake = ParquetLake("data/lake")
    closes, funding, basis, taker, adv = {}, {}, {}, {}, {}
    for s in list_liquid_perps(top_n=RESEARCH_TOP_N):
        if not (_CRYPTO / s / Timeframe.D1.value).exists():
            continue
        register_instrument(InstrumentSpec(symbol=s, asset_class=AssetClass.CRYPTO, description=s))
        df = lake.read_bars(Layer.BRONZE, s, Timeframe.D1).set_index("timestamp")
        if "funding" not in df.columns or len(df) < 250:
            continue
        closes[s] = df["close"]
        funding[s] = df["funding"]
        adv[s] = float((df["close"] * df["volume"]).tail(180).mean())
        if "basis" in df.columns:
            basis[s] = df["basis"]
        if "taker_buy_frac" in df.columns:
            taker[s] = df["taker_buy_frac"]
    c = pd.DataFrame(closes).sort_index()
    f = pd.DataFrame(funding).reindex(c.index)
    b = pd.DataFrame(basis).reindex(c.index) if basis else pd.DataFrame()
    t = pd.DataFrame(taker).reindex(c.index) if taker else pd.DataFrame()
    return c, f, b, t, adv


def _ann(r: np.ndarray) -> float:
    a = r[r != 0.0]
    return round(float(sharpe_ratio(a) * np.sqrt(_PPY)), 2) if len(a) > 5 else 0.0


def _candidates(close, funding, basis, taker, adv, cost) -> dict[str, np.ndarray]:  # type: ignore
    """The economically-distinct sleeve library (each a different mechanism, not a tuned sweep)."""
    lib: dict[str, np.ndarray] = {
        "funding_carry": xsec_funding_returns(close, funding, adv, lookback=7, q=0.2, band=0.02),
        "funding_momentum": funding_momentum_returns(close, funding, adv, lookback=7, q=0.2,
                                                     band=0.02),
        "xsec_price_mom": xsec_momentum_returns(close, cost, lookback=20, q=0.3, band=0.05),
        "ts_trend": trend_basket_returns(close, cost, lookback=30, band=0.05),
        "xsec_reversal": xsec_momentum_returns(close, cost, lookback=3, q=0.3, band=0.05,
                                               long_high=False),
        "xsec_lowvol": xsec_lowvol_returns(close, funding, adv, lookback=20, q=0.3, band=0.05),
    }
    if not basis.empty and basis.shape[1] >= 12:
        lib["basis_carry"] = basis_carry_returns(close[basis.columns], funding[basis.columns],
                                                 basis, adv, lookback=3, q=0.2, band=0.02)
    if not taker.empty and taker.shape[1] >= 12:
        lib["taker_flow"] = taker_flow_returns(close[taker.columns], funding[taker.columns],
                                               taker, adv, lookback=5, q=0.2, band=0.02)
    return {k: v for k, v in lib.items() if np.isfinite(v).all()}


# --- COST TRUTH (gap #45, 2026-07-22) -------------------------------------------------------
# adv_tier_cost GUESSES 5/8/15 bps per side by ADV tier. The measured cost model
# (run_cost_model.py, real recorded books) shows that guess is wrong in BOTH directions:
# majors overcharged (BTC pair-slippage 0.009 bps vs 5 bps/side assumed -- a daily-turnover
# sleeve pays ~3%/yr of phantom cost, enough to kill real 0.6-0.9-Sharpe candidates), thin
# names undercharged (NOMUSDT realized -149 bps vs 15 assumed). Screening candidates against
# a mis-measured cost is a silent thumb on the scale either way. Per-side here = maker-first
# futures fee (2 bps VIP0 maker, taker fallback -> 3 bps blended, documented constant) +
# MEASURED per-leg book-walk at $500. Unmeasured symbols keep the tier guess -- and the
# recorder now records the traded universe, so measurement coverage grows on its own.
_FEE_SIDE = 3e-4
_COST_MODEL = Path("data/cost_model.json")


def _measured_side_cost(sym: str, adv_usd: float) -> float:
    try:
        m = json.loads(_COST_MODEL.read_text("utf-8"))["symbols"][sym]
        slip = m["fut_sell"]["500"]["median_bps"]
        if slip is None:
            return adv_tier_cost(adv_usd)
        return max(2.5e-4, _FEE_SIDE + float(slip) / 1e4)
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        return adv_tier_cost(adv_usd)


def main() -> None:
    close, funding, basis, taker, adv = _panels()
    if close.shape[1] < 12:
        raise SystemExit("need a liquid perp panel")
    cost = {s: _measured_side_cost(s, a) for s, a in adv.items()}
    n_meas = sum(1 for s2, a in adv.items()
                 if abs(cost[s2] - adv_tier_cost(a)) > 1e-9)
    print(f"cost truth: {n_meas}/{len(cost)} symbols on MEASURED cost, "
          f"rest on tier fallback")
    lib = _candidates(close, funding, basis, taker, adv, cost)

    df = pd.DataFrame(lib, index=close.index)
    corr = df.replace(0.0, np.nan).corr()
    matrix = np.column_stack([lib[k] for k in lib])
    sharpes = np.array([sharpe_ratio(lib[k][lib[k] != 0.0]) for k in lib])
    # PER-CANDIDATE campaign statistics (R0044, closing defect #71 on this path). campaign_pbo_rc
    # broadcast ONE matrix-level PBO/RC verdict to every sleeve regardless of merit -- and this
    # file is the row's top-EV target (the only DEPLOYABLE tier). campaign_gate_stats keeps the
    # SAME thresholds but each sleeve earns its verdict on its own column: CSCV candidate-PBO +
    # Romano-Wolf stepdown, family-wise error still controlled over all N (multiplicity paid once,
    # per R0224). Power-restoring, not bar-moving.
    campaign = campaign_gate_stats(matrix)

    results = []
    gate_rows: list[dict[str, bool]] = []          # gap #71: per-gate discrimination evidence
    for i, (name, r) in enumerate(lib.items()):
        # R0044 ACCEPTANCE TEST (mandatory per file): column i must be THIS sleeve's own series
        # under the column_stack order above (dict insertion order both times) -- a mis-mapped
        # index hands one candidate another's verdict, which is worse than the weld it replaces.
        assert np.array_equal(matrix[:, i], r), f"column {i} is not {name}'s own series"
        active = r[r != 0.0]
        sh = _ann(r)
        others = corr[name].drop(labels=[name], errors="ignore").abs()
        max_corr = round(float(others.max()), 2) if not others.empty else 0.0
        orthogonal = max_corr < _ORTHO
        v = (validate(active, hypothesis=Hypothesis(
            family=Family.CARRY, subtype=name, symbol="CRYPTO", params={},
            mechanism=MechanismType.RISK_PREMIUM, edge_source=name, failure_modes=_FAIL),
            periods_per_year=_PPY,        # D1 crypto bars, 24/7 (R0086)
            n_trials=len(lib), sharpe_estimates=sharpes, returns_matrix=matrix,
            campaign=campaign, column=i)
            if len(active) >= 250 else None)
        gates = f"{sum(v.gates.values())}/{len(v.gates)}" if v else "n<250"
        survived = bool(v.survived) if v else False
        if survived:
            status = "DEPLOYABLE (gauntlet pass)"
        elif sh > 0.5 and orthogonal:
            status = "SHADOW (orthogonal +edge)"
        elif sh > 0.4:
            status = "CANDIDATE"
        else:
            status = "REJECTED"
        results.append({"sleeve": name, "sharpe": sh, "gates": gates, "max_corr": max_corr,
                        "orthogonal": orthogonal, "status": status})
        if v is not None:
            gate_rows.append(dict(v.gates))

    def _rank(d: dict[str, object]) -> tuple[bool, float]:
        promoted = str(d["status"]).startswith(("SHADOW", "DEPLOY"))
        return (promoted, float(d["sharpe"]))                # type: ignore[arg-type]
    results.sort(key=_rank, reverse=True)
    archive_days = (int(pd.read_parquet(_METRICS)["ts"].dt.date.nunique())
                    if _METRICS.exists() else 0)
    pending = [{"sleeve": n, "dataset": ds, "needs_days": d, "have_days": archive_days,
                "status": f"PENDING ({archive_days}/{d}d archived)"} for n, ds, d in _PENDING]

    shadow = [r["sleeve"] for r in results if r["status"].startswith(("SHADOW", "DEPLOY"))]
    payload = {"updated": datetime.now(tz=UTC).isoformat(), "tested": len(results),
               "shadow_eligible": shadow, "results": results, "pending": pending,
               "ortho_threshold": _ORTHO}
    _WEB.parent.mkdir(parents=True, exist_ok=True)
    _WEB.write_text(json.dumps(payload, indent=2, default=str), "utf-8")
    print(f"discovery: tested {len(results)} sleeves; shadow-eligible (orthogonal +edge): {shadow}")
    for r in results:
        print(f"  {r['sleeve']:18} sharpe~{r['sharpe']:5} gates={r['gates']:5} "
              f"corr={r['max_corr']:5} {r['status']}")
    print(f"pending (data-gated): {[p['sleeve'] for p in pending]} (archive {archive_days}d)")

    # GAP #71: ZERO SURVIVORS IS AMBIGUOUS, AND THE AMBIGUITY IS THE PROBLEM. It reads either
    # "nothing here was good enough" or "a campaign-level gate vetoed everything regardless of
    # merit". Those demand opposite responses -- generate better candidates, versus fix the
    # gate -- and the desk was reporting the first while (per its own numbers: 420 tested, 0
    # survivors, campaign PBO 0.6159) living the second. Reports only; no bar is moved.
    disc = gate_discrimination(gate_rows)
    blocking = blocking_constant_gates(gate_rows)
    payload["gate_discrimination"] = disc
    payload["blocking_constant_gates"] = blocking
    _WEB.write_text(json.dumps(payload, indent=2, default=str), "utf-8")
    if disc:
        print("\ngate discrimination (gap #71):")
        for g, d in sorted(disc.items(), key=lambda kv: kv[1]["pass_rate"]):
            flag = "  <-- CONSTANT" if not d["discriminates"] else ""
            print(f"  {g:20} pass {d['passed']}/{d['n']} ({d['pass_rate']:.0%}){flag}")
    if blocking:
        # AND THE QUESTION A RULING ACTUALLY NEEDS: would waiving them promote anyone? Measured
        # on the desk's real 420 the answer was ZERO -- every candidate also failed a gate that
        # genuinely discriminates ("sole-cause failures EMPTY"). Computing it every run means the
        # ruling is made against current evidence, not a probe someone ran once.
        cf = counterfactual_survivors(gate_rows, blocking)
        payload["counterfactual_if_waived"] = cf
        _WEB.write_text(json.dumps(payload, indent=2, default=str), "utf-8")
        print(f"\n  {len(blocking)} gate(s) FAILED EVERY CANDIDATE: {', '.join(blocking)}")
        print(f"  IF WAIVED -> {cf['survivors']} survivor(s) of {cf['n']} "
              f"(naive independent estimate {cf['independent_estimate']})")
        print(f"  {cf['note']}")
        print("  A gate that rejects all N carries zero information about any individual one --")
        print("  that is a campaign-level verdict wearing a per-candidate costume. Whether it is")
        print("  correct (the campaign really is overfit) or miscalibrated is a PRINCIPAL ruling;")
        print("  the standing directive forbids relaxing a statistical bar to make it pass.")


if __name__ == "__main__":
    main()

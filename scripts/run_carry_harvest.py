"""Delta-neutral crypto funding-CARRY harvest -- the last economically-distinct niche test.

Mechanism: perp funding is a leverage-demand RISK PREMIUM (persistently positive). Harvest it
market-neutral: short perp + long spot when funding>0 (receive funding), reverse when funding<0.
The price legs cancel EXCEPT the perp-spot basis -- which blows out in crashes. That basis term is
included on purpose, so this is an HONEST test (a funding-income-only model would hide the crash
risk and manufacture a false survivor). Validated through the existing gauntlet (CPCV/PBO/DSR/RC/
walk-forward/fragility/capacity), net of fees. Survivors reported honestly.

    python scripts/run_carry_harvest.py
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from libs.autodiscovery.models import Family, Hypothesis
from libs.autodiscovery.validation import stratified_campaign_gates, validate
from libs.data.crypto_source import fetch_spot_klines
from libs.data.instruments import AssetClass, InstrumentSpec, register_instrument
from libs.data.lake import Layer, ParquetLake
from libs.data.timeframe import Timeframe
from libs.validation.dsr import sharpe_ratio
from libs.validation.economic_prior import MechanismType

_CRYPTO = Path("data/lake/bronze/crypto")
_OUT = Path("reports/carry_harvest")
_FEE_PER_FLIP_LEG = 8e-4          # taker on perp+spot, one-way per unit |delta position|
_THRESHOLDS = (0.0, 0.0001, 0.0003)  # harvest when |funding| exceeds (0, ~11%/yr, ~33%/yr)
# NATIVE 8h FUNDING BARS -> 1095 a year. Until R0086 these verdicts were annualised with the
# validator's hourly constant (6240), inflating every reported ann_sharpe by sqrt(6240/1095) =
# 2.387x. The report below is regenerated on each run, so it self-corrects; nothing is rewritten.
_PPY = 3 * 365.0
_FAIL_MODES = ["basis blowout in crash", "funding regime flip negative", "exchange/counterparty"]


def _symbols() -> list[str]:
    if not _CRYPTO.exists():
        return []
    return sorted(d.name for d in _CRYPTO.iterdir() if (d / Timeframe.H8.value).exists())


def _carry_returns(perp: np.ndarray, spot: np.ndarray, funding: np.ndarray,
                   threshold: float) -> np.ndarray:
    n = len(perp)
    perp_ret = np.zeros(n)
    perp_ret[1:] = perp[1:] / perp[:-1] - 1.0
    spot_ret = np.zeros(n)
    spot_ret[1:] = spot[1:] / spot[:-1] - 1.0
    # Decision at t uses funding known at t; applied to the NEXT bar (no look-ahead).
    h = np.where(np.abs(funding) > threshold, np.sign(funding), 0.0)
    hd = np.zeros(n)
    hd[1:] = h[:-1]                              # lag-1 position
    flips = np.abs(np.diff(hd, prepend=0.0))
    # short perp + long spot when hd>0 -> receive funding, pay the basis move (perp-spot return)
    return hd * (funding - (perp_ret - spot_ret)) - flips * _FEE_PER_FLIP_LEG


def main() -> None:
    symbols = _symbols()
    if not symbols:
        raise SystemExit("no crypto H8 data; run scripts/ingest_crypto.py --interval 8h first")
    for s in symbols:
        register_instrument(InstrumentSpec(symbol=s, asset_class=AssetClass.CRYPTO, description=s))
    lake = ParquetLake("data/lake")

    prepared: list[tuple[str, str, np.ndarray]] = []
    for sym in symbols:
        df = lake.read_bars(Layer.BRONZE, sym, Timeframe.H8).set_index("timestamp")
        if "funding" not in df.columns or len(df) < 500:
            continue
        start_ms = int(df.index[0].timestamp() * 1000)
        spot_df = fetch_spot_klines(sym, interval="8h", start_ms=start_ms).set_index("timestamp")
        if spot_df.empty:
            continue
        joined = df.join(spot_df["close"].rename("spot"), how="inner").dropna()
        if len(joined) < 500:
            continue
        perp = joined["close"].to_numpy("float64")
        spot = joined["spot"].to_numpy("float64")
        funding = joined["funding"].to_numpy("float64")
        for thr in _THRESHOLDS:
            rets = _carry_returns(perp, spot, funding, thr)
            prepared.append((sym, f"thr={thr}", rets))
        print(f"  {sym}: {len(joined)} aligned 8h bars")

    if not prepared:
        raise SystemExit("no aligned perp/spot series")

    # STRATIFIED, NOT MIN-LENGTH (R0271). This built its campaign matrix with `r[-min_len:]`, so
    # the SHORTEST perp/spot inner-join truncated every other symbol -- and the lengths here
    # genuinely differ, because each symbol's join spans a different listing history. The gate
    # audit measured history length as THE binding constraint on the whole funnel (T=310->2500
    # takes power at true Sharpe 2.0 from 0.00% to 19.58%) while cohort size buys nothing.
    # Truncation spent observations to keep candidates aligned, which is exactly the wrong trade.
    # This RAISES POWER and lowers no bar: each stratum is its own family at CAMPAIGN_ALPHA/k, a
    # STRICTER per-family level than the 5% the single campaign used, and plan_strata partitions
    # on LENGTHS ALONE -- it never sees a return, a Sharpe or a p-value.
    gates_by_candidate, strata_plan = stratified_campaign_gates([r for _, _, r in prepared])
    min_len = min(len(r) for _, _, r in prepared)
    matrix = np.column_stack([r[-min_len:] for _, _, r in prepared])  # legacy diagnostics only
    sharpes = np.array([sharpe_ratio(r) for _, _, r in prepared], dtype="float64")
    n_trials = len(prepared)

    survivors = 0
    untested = 0
    gate_fail: dict[str, int] = {}
    rows = []
    # enumerate order == column_stack order over `prepared`, so `col` indexes the candidate.
    for col, ((sym, sub, rets), spr) in enumerate(zip(prepared, sharpes, strict=True)):
        # UNTESTED IS NOT REJECTED. A candidate no stratum supports has no campaign statistics.
        # Falling through to the legacy campaign-constant path would be fail-CLOSED but would
        # file a DATA-AVAILABILITY exclusion under a statistical mechanism of death, corrupting
        # the family survival statistics that steer future search (L1.17) -- and this is the
        # CARRY family, the desk's only repeat survivor. Say what actually happened instead.
        stratum = gates_by_candidate[col]
        if stratum is None:
            untested += 1
            rows.append({"symbol": sym, "variant": sub, "sharpe_per_bar": round(float(spr), 4),
                         "ann_sharpe": None, "survived": False,
                         "reason": f"not tested: no stratum supports {len(rets)} obs"})
            continue
        gates, gcol = stratum
        hyp = Hypothesis(family=Family.CARRY, subtype=f"funding_carry_{sub}", symbol=sym,
                         params={}, mechanism=MechanismType.RISK_PREMIUM,
                         edge_source="perp funding carry delta-neutral", failure_modes=_FAIL_MODES)
        v = validate(rets, hypothesis=hyp, periods_per_year=_PPY,
                     n_trials=n_trials, sharpe_estimates=sharpes,
                     returns_matrix=matrix, campaign=gates, column=gcol)
        survivors += int(v.survived)
        for g, ok in v.gates.items():
            if not ok:
                gate_fail[g] = gate_fail.get(g, 0) + 1
        rows.append({"symbol": sym, "variant": sub, "sharpe_per_bar": round(float(spr), 4),
                     "ann_sharpe": round(float(v.metrics.annual_sharpe), 2),
                     "survived": v.survived, "reason": v.rejection_reason})

    _OUT.mkdir(parents=True, exist_ok=True)
    (_OUT / "carry_report.json").write_text(
        json.dumps({"n_trials": n_trials, "survivors": survivors,
                    # NO SILENT CAPS: an unreported exclusion reads downstream as "the campaign
                    # covered everything". obs_retained vs obs_available is the truncation this
                    # migration recovered, in the artifact rather than in a log nobody opens.
                    "n_untested": untested,
                    "strata": {"k": len(strata_plan.strata),
                               "n_tested": strata_plan.n_tested,
                               "obs_retained": strata_plan.obs_retained,
                               "obs_available": strata_plan.obs_available,
                               "retained_fraction": round(strata_plan.retained_fraction, 4),
                               "why": strata_plan.why},
                    "rejection_by_gate": gate_fail, "candidates": rows}, indent=2), "utf-8")
    print(f"\n[carry] tested={n_trials} survivors={survivors}")
    print(f"rejection_by_gate={gate_fail}")
    best = max(rows, key=lambda r: r["sharpe_per_bar"])
    print(f"best raw sharpe/bar: {best['symbol']} {best['variant']} "
          f"sharpe={best['sharpe_per_bar']} survived={best['survived']}")
    if survivors == 0:
        print("ZERO survivors net-of-cost (honest) -- funding-carry niche does not clear.")


if __name__ == "__main__":
    main()

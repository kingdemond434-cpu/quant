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
from libs.autodiscovery.validation import campaign_gate_stats, validate
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

    min_len = min(len(r) for _, _, r in prepared)
    matrix = np.column_stack([r[-min_len:] for _, _, r in prepared])
    sharpes = np.array([sharpe_ratio(r) for _, _, r in prepared], dtype="float64")
    n_trials = len(prepared)
    # per-candidate gates (gap #87 flip, principal-ruled 2026-07-29); thresholds unchanged
    campaign = campaign_gate_stats(matrix)

    survivors = 0
    gate_fail: dict[str, int] = {}
    rows = []
    # enumerate order == column_stack order over `prepared`, so `col` is the matrix column.
    for col, ((sym, sub, rets), spr) in enumerate(zip(prepared, sharpes, strict=True)):
        hyp = Hypothesis(family=Family.CARRY, subtype=f"funding_carry_{sub}", symbol=sym,
                         params={}, mechanism=MechanismType.RISK_PREMIUM,
                         edge_source="perp funding carry delta-neutral", failure_modes=_FAIL_MODES)
        v = validate(rets, hypothesis=hyp, n_trials=n_trials, sharpe_estimates=sharpes,
                     returns_matrix=matrix, campaign=campaign, column=col)
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

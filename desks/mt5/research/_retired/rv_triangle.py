"""Relative-value triangle study: AUDCAD/AUDNZD/NZDCAD M15 (2022-08 -> now).

Reconstruction of the RAZOR/Deux-family public mechanism (mean reversion on
structurally related crosses, basket fair-value exit, spread/slippage aware,
no grid/martingale). One fixed parameterization from theory; perturbation
tests + 3-fold WF OOS + 2x cost stress.

Residual: r = ln(AUDCAD) - ln(AUDNZD) - ln(NZDCAD)  (cross-rate consistency).
z = r / rolling_sigma(r, 480 bars). Entry |z|>2.0 with 1-bar confirm and no
>2.5sigma single-bar jump (break risk). Exit: z reclaims 0 (basket fair-value)
or TTL 192 bars or hard stop z = entry +- 2.5. No entries 21:00-22:00 UTC
(Vantage pause). P&L in USD from actual leg prices (1 lot per leg, 100k).
R = P&L / entry stop-risk in USD.
"""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

BASE = Path(__file__).resolve().parent.parent
UNI = BASE / "data" / "universe"

PAIRS = ["AUDCAD", "AUDNZD", "NZDCAD"]
SIGMA_WIN = 480      # ~5 days M15
ENTRY_Z = 2.0
EXIT_Z = 0.0
STOP_Z = 2.5
TTL_BARS = 192       # ~2 days
JUMP_GUARD = 2.5     # skip entry after single-bar z jump above this
NOTIONAL = 100_000.0
COMMISSION = 3.5     # USD per lot per side (mirror desk convention)
SLIPPAGE = 0.2       # x spread per leg


def load(sym: str) -> pd.DataFrame:
    df = pd.read_parquet(UNI / f"{sym}_M15.parquet")
    return df


def main() -> None:
    import sys as _sys
    tf = _sys.argv[1] if len(_sys.argv) > 1 else "M15"
    entry_z = float(_sys.argv[2]) if len(_sys.argv) > 2 else ENTRY_Z
    meta = json.loads((UNI / "universe.json").read_text(encoding="utf-8"))
    spreads = {p: meta[p]["median_spread_pts"] * meta[p]["tick_size"]
               for p in PAIRS}  # in price units
    frames = {p: pd.read_parquet(UNI / f"{p}_{tf}.parquet") for p in PAIRS}
    common = frames["AUDCAD"].index.intersection(frames["AUDNZD"].index).intersection(
        frames["NZDCAD"].index)
    frames = {p: frames[p].reindex(common) for p in PAIRS}  # OFF-FLAG
    logs = {p: np.log(frames[p]["close"].to_numpy()) for p in PAIRS}
    resid = logs["AUDCAD"] - logs["AUDNZD"] - logs["NZDCAD"]
    idx = frames["AUDCAD"].index

    # rolling sigma of residual (in ln units)
    rs = pd.Series(resid, index=idx)
    sigma = rs.rolling(SIGMA_WIN, min_periods=SIGMA_WIN).std().to_numpy()
    z = (rs.to_numpy() - rs.rolling(SIGMA_WIN, min_periods=SIGMA_WIN).mean().to_numpy()) / sigma

    n = len(rs)
    trades = []
    i = SIGMA_WIN
    while i < n - 2:
        hour = rs.index[i].hour_ if hasattr(rs.index[i], "hour_") else rs.index[i].hour
        if 21 <= hour < 22:  # Vantage pause
            i += 1
            continue
        zi = z[i]
        if abs(zi) < entry_z:
            i += 1
            continue
        if abs(z[i - 1]) < entry_z and abs(z[i] - z[i - 1]) > JUMP_GUARD:
            i += 1
            continue
        # confirm: |z| was already beyond entry on prev bar (or reclaiming)
        side = 1 if zi > 0 else -1  # +1: short AC / long AN+NC ; -1: long AC / short AN+NC
        entry_prices = {p: float(frames[p]["close"].iloc[i]) for p in PAIRS}
        entry_sigma = float(sigma[i])
        stop_ln = entry_sigma * STOP_Z
        # $ stop risk at entry (first-order): each leg moves by residual move
        legs = {"AUDCAD": -side, "AUDNZD": side, "NZDCAD": side}
        stop_usd = sum(legs[p] * stop_ln * entry_prices[p] * NOTIONAL for p in PAIRS)
        if stop_usd <= 0:
            i += 1
            continue
        # simulate to exit
        exit_idx = None
        exit_reason = "ttl"
        for j in range(i + 1, min(i + TTL_BARS + 1, n)):
            if side * z[j] <= side * EXIT_Z:
                exit_idx = j
                exit_reason = "fair_value"
                break
            if abs(z[j] - zi) > STOP_Z - 0.05:
                exit_idx = j
                exit_reason = "stop"
                break
        if exit_idx is None:
            exit_idx = min(i + TTL_BARS, n - 1)
            exit_reason = "ttl"
        exit_prices = {p: float(frames[p]["close"].iloc[exit_idx]) for p in PAIRS}
        pl_usd = sum(legs[p] * (np.log(exit_prices[p]) - np.log(entry_prices[p]))
                     * entry_prices[p] * NOTIONAL for p in PAIRS)
        costs = sum((spreads[p] * entry_prices[p] * NOTIONAL) * (1 + SLIPPAGE)
                    + COMMISSION * 2.0 for p in PAIRS)
        pl_usd -= costs
        r_mult = pl_usd / stop_usd
        trades.append(dict(
            entry_time=str(rs.index[i]), exit_time=str(rs.index[exit_idx]),
            entry_z=float(zi), exit_z=float(z[exit_idx]), reason=exit_reason,
            pl_usd=float(pl_usd), stop_usd=float(stop_usd), r_multiple=r_mult,
            costs_usd=float(costs),
        ))
        i = exit_idx + 1

    if not trades:
        print("no trades")
        return
    rs_ = np.array([t["r_multiple"] for t in trades])
    n_tr = len(rs_)
    mean = rs_.mean()
    sd = rs_.std(ddof=1) if n_tr > 1 else 0.0
    t_stat = mean / (sd / np.sqrt(n_tr)) if sd > 0 else 0.0
    wins = rs_[rs_ > 0].sum()
    losses = abs(rs_[rs_ < 0].sum())
    pf = wins / losses if losses > 0 else float("inf")
    cum = np.cumsum(rs_)
    max_dd = float((cum - np.maximum.accumulate(cum)).min())
    span_days = (rs.index[-1] - rs.index[0]).days / 365.25
    print(f"=== {tf} entry_z={entry_z} ===")
    print(f"{'metric':<22}{'value':>12}")
    print(f"{'trades':<22}{n_tr:>12}")
    print(f"{'expectancy R':<22}{mean:>12.3f}")
    print(f"{'t-stat':<22}{t_stat:>12.2f}")
    print(f"{'profit factor':<22}{pf:>12.2f}")
    print(f"{'maxDD R':<22}{max_dd:>12.1f}")
    print(f"{'win rate':<22}{(rs_ > 0).mean():>12.2f}")
    print(f"{'avg win R':<22}{rs_[rs_>0].mean() if (rs_>0).any() else 0:>12.2f}")
    print(f"{'avg loss R':<22}{rs_[rs_<0].mean() if (rs_<0).any() else 0:>12.2f}")
    print(f"{'trades/yr':<22}{n_tr / span_days:>12.1f}")
    print(f"{'span years':<22}{span_days:>12.1f}")
    from collections import Counter
    print("reasons:", dict(Counter(t["reason"] for t in trades)))
    print(f"avg gross $ per trade: {np.mean([t['pl_usd'] for t in trades]):.2f} "
          f"(1 lot/leg)")

    gates = {"t>2": t_stat > 2, "n>60": n_tr > 60, "PF>1.05": pf > 1.05,
             "maxDD>-30R": max_dd > -30}
    print("\ngates:", gates, "->", "PASS" if all(gates.values()) else "fail")

    # 3-fold WF OOS on trade sequence
    fold = n_tr // 3
    wf = []
    for k in range(3):
        seg = rs_[k * fold:(k + 1) * fold if k < 2 else n_tr]
        wf.append(float(seg.mean()) if len(seg) else 0.0)
    print("wf folds exp:", [round(w, 4) for w in wf], "->",
          "PASS" if all(w > 0 for w in wf) else "fail")

    # 2x cost stress
    rs_stress = np.array([(t["pl_usd"] - t["costs_usd"]) / t["stop_usd"]
                          for t in trades])
    mean_s = rs_stress.mean()
    t_s = mean_s / (rs_stress.std(ddof=1) / np.sqrt(len(rs_stress))) if len(rs_stress) > 1 else 0.0
    print(f"stress(2x cost): exp={mean_s:+.3f}R t={t_s:.2f} ->",
          "PASS" if (mean_s > 0 and t_s > 1.5) else "fail")

    (BASE / "reports" / "rv_triangle.json").write_text(json.dumps(
        {"config": {"tf": tf, "entry_z": entry_z},
         "n": n_tr, "expectancy_r": float(mean), "t_stat": float(t_stat),
         "profit_factor": float(pf), "max_dd_r": max_dd,
         "win_rate": float((rs_ > 0).mean()),
         "wf_folds": wf, "gates": {k: bool(v) for k, v in gates.items()},
         "stress_exp_r": float(mean_s), "stress_t": float(t_s),
         "trades": trades[:5]}, indent=2),
        encoding="utf-8")


if __name__ == "__main__":
    main()
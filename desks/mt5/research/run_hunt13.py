"""hunt13: TREND_DAY decomposition - which components carry the effect?

For AUDCAD / AUDJPY / XAUUSD asia-window TREND_DAY cells, decompose the binary
prior-NY state into measurable components and test which ones actually move
next-session expectancy (median-split ablation, deflated t with family size =
number of components).

Components (all computed on the PRIOR NY session, 13:00-22:00 UTC):
  ny_ret_atr      net NY displacement / ATR
  eff_ratio       efficiency ratio of NY session
  close_loc       close location within NY range [0,1]
  vol_pct         NY range vs trailing 90d median
  range_ratio     NY range vs trailing 20d median (TREND_DAY core)
  persist         consecutive same-direction days
  wick_frac       NY wick fraction (lower = cleaner body)
  breakout_count  hours closing beyond prior-day high/low
  close_dist_prior close distance from prior-day extreme / prior range
  gold_usd_z      dollar context (free_states, PIT-safe)
  gold_macro_stress macro-stress context

If a small set of components dominates, they define the generalized state to
test across instruments without the literal label.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mt5desk import families  # noqa: E402
from mt5desk.engine import Costs, run_backtest  # noqa: E402
from research.run_hunt12 import day_states  # noqa: E402

BASE = Path(__file__).resolve().parent.parent
UNI = BASE / "data" / "universe"
N_COMP = 11
E_MAX_11 = 1.56  # E[max of 11 iid standard normals]
WINDOW = dict(range_start=7, wait_bars=12, rr=2.0, ttl_bars=12)
SYMBOLS = ["AUDCAD", "AUDJPY", "XAUUSD"]


def atr_series(h1: pd.DataFrame, n: int = 20) -> pd.Series:
    h, l, c = h1["high"], h1["low"], h1["close"]
    pc = c.shift(1)
    tr = pd.concat([h - l, (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    return tr.rolling(n).mean()


def ny_components(h1: pd.DataFrame, states: dict) -> pd.DataFrame:
    ny = h1.between_time("13:00", "22:00")
    atr = atr_series(h1)
    by = ny.assign(date=ny.index.date)
    grp = by.groupby("date")
    df = grp.agg(o=("open", "first"), c=("close", "last"),
                 hi=("high", "max"), lo=("low", "min"),
                 retsum=("close", lambda x: float((x.pct_change().abs()).sum())))
    df["range"] = df["hi"] - df["lo"]
    df["ny_ret"] = df["c"] - df["o"]
    df["ny_ret_atr"] = df["ny_ret"] / atr.reindex(h1.index).groupby(
        h1.assign(date=h1.index.date)["date"]).last().reindex(df.index)
    df["eff_ratio"] = df["ny_ret"].abs() / df["retsum"].replace(0, np.nan)
    df["close_loc"] = (df["c"] - df["lo"]) / df["range"].replace(0, np.nan)
    med90 = df["range"].rolling(90, min_periods=40).median()
    med20 = df["range"].rolling(20, min_periods=10).median()
    df["vol_pct"] = df["range"] / med90
    df["range_ratio"] = df["range"] / med20
    day = h1.assign(date=h1.index.date).groupby("date").agg(
        dhi=("high", "max"), dlo=("low", "min"), o=("open", "first"), c=("close", "last"))
    day["ret"] = day["c"] - day["o"]
    sign = np.sign(day["ret"]).replace(0, 1)
    persist = []
    last = 0
    streak = 0
    for s in sign:
        if s == last:
            streak += 1
        else:
            last, streak = s, 1
        persist.append(streak)
    day["persist"] = persist
    df["persist"] = day["persist"].reindex(df.index)
    df["wick_frac"] = ((df["hi"] - np.maximum(df["o"], df["c"])
                        + np.minimum(df["o"], df["c"]) - df["lo"]) / df["range"].replace(0, np.nan))
    prev = day["dhi"].shift(1).reindex(df.index)
    prevlo = day["dlo"].shift(1).reindex(df.index)
    df["breakout_count"] = ny.assign(date=ny.index.date).groupby("date")["close"].apply(
        lambda s: int(((s > prev.reindex(s.index).ffill()) | (s < prevlo.reindex(s.index).ffill())).sum()))
    df["close_dist_prior"] = ((df["c"] - prev) / (day["dhi"].shift(1).reindex(df.index)
                                                  - day["dlo"].shift(1).reindex(df.index)).replace(0, np.nan))
    df["state"] = [states.get(d, "NONE") for d in df.index]
    return df


def main() -> None:
    st = pd.read_parquet(BASE / "data" / "states" / "free_states.parquet")
    out = {"swept_at": datetime.now(timezone.utc).isoformat(),
           "symbols": SYMBOLS, "window": "asia", "n_components": N_COMP,
           "components": {}}
    print(f"{'sym':>7} {'comp':<18} {'nHi':>5} {'expHi':>7} {'expLo':>7} "
          f"{'spread':>7} {'deflT':>6} {'carry?':>6}")
    for sym in SYMBOLS:
        h1 = families._h1(pd.read_parquet(UNI / f"{sym}_H1.parquet"))
        states = day_states(h1)
        comp = ny_components(h1, states)
        if sym != "XAUUSD":
            gs = st.reindex(h1.index)
            comp["gold_usd_z"] = gs["gold_usd_z"].groupby(
                h1.assign(date=h1.index.date)["date"]).last().reindex(comp.index)
            comp["gold_macro_stress"] = gs["gold_macro_stress"].groupby(
                h1.assign(date=h1.index.date)["date"]).last().reindex(comp.index)
        meta = json.loads((UNI / "universe.json").read_text(encoding="utf-8"))[sym]
        costs = Costs(spread_per_lot=0.48 if sym == "XAUUSD" else max(
            meta["median_spread_pts"] * meta["tick_size"] * meta["contract_size"], 0.05),
            commission_per_lot=3.50, contract_oz=meta["contract_size"])
        sigs = families.family_session_range_breakout(h1, **WINDOW)
        sdays = [pd.Timestamp(s.time).date() for s in sigs]
        tday = [s for s, d in zip(sigs, sdays) if states.get(d) == "TREND_DAY"]
        base = run_backtest(h1, tday, costs).stats()
        print(f"\n{sym} TREND_DAY asia base: n={base['n']} exp={base['expectancy_r']:+.3f}")
        rows = []
        for col in ["ny_ret_atr", "eff_ratio", "close_loc", "vol_pct", "range_ratio",
                    "persist", "wick_frac", "breakout_count", "close_dist_prior",
                    "gold_usd_z", "gold_macro_stress"]:
            if col not in comp:
                continue
            c = comp[col]
            med = c.median()
            hi_days = set(c[c > med].index)
            lo_days = set(c[c <= med].index)
            hi_sig = [s for s, d in zip(sigs, sdays) if states.get(d) == "TREND_DAY"
                      and d in hi_days]
            lo_sig = [s for s, d in zip(sigs, sdays) if states.get(d) == "TREND_DAY"
                      and d in lo_days]
            if len(hi_sig) < 40 or len(lo_sig) < 40:
                continue
            rhi = run_backtest(h1, hi_sig, costs).stats()
            rlo = run_backtest(h1, lo_sig, costs).stats()
            ehi, elo = rhi["expectancy_r"], rlo["expectancy_r"]
            spread = ehi - elo
            se_hi = rhi["expectancy_r"] / rhi["t_stat"] * np.sqrt(rhi["n"]) if rhi["t_stat"] > 0 else 0.0
            se_lo = rlo["expectancy_r"] / rlo["t_stat"] * np.sqrt(rlo["n"]) if rlo["t_stat"] > 0 else 0.0
            se = np.sqrt(se_hi ** 2 + se_lo ** 2)
            t = spread / se if se > 0 else 0.0
            defl = t - E_MAX_11
            carry = "YES" if (ehi > 0.2 and elo < 0.1 and defl > 0) else ""
            print(f"{sym:>7} {col:<18} {len(hi_sig):5d} {ehi:+7.3f} {elo:+7.3f} "
                  f"{spread:+7.3f} {defl:6.2f} {carry:>6}")
            rows.append(dict(comp=col, n_hi=len(hi_sig), n_lo=len(lo_sig),
                             exp_hi=ehi, exp_lo=elo, spread=spread, t=t, defl=defl))
        out["components"][sym] = rows
    (BASE / "reports" / "hunt13.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print("\n-> reports/hunt13.json")


if __name__ == "__main__":
    main()
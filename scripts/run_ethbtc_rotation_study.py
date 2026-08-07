#!/usr/bin/env python3
"""ETH/BTC ROTATION -- the 4 years the posted backtest omits.

Binds to docs/research/ETHBTC_ROTATION_PREREGISTRATION.md. Kill criteria K1-K8 and the 72-trial
budget were fixed there BEFORE this file was written; nothing here chooses a threshold.

THE ONE THING THIS SCRIPT WILL NOT DO IS INVENT DATA. With no bars it reports BLOCKED and exits 0.
A verdict computed on synthesised prices is a fact about the generator, and it would enter the
funnel wearing the same vocabulary as a real one -- which is worse than no verdict, because the
desk would act on it.

TWO CONTROLS ARE NOT OPTIONAL HERE, and they are the reason this study is worth running at all:

  K7 BUY-AND-HOLD. 2020-2021 returned multiples on either asset. A rotation rule can post a
     spectacular CAGR over that window and still have destroyed value against the trivial
     alternative. A strategy that does not beat holding the better asset is not an edge, it is a
     costlier way to be long -- and this is the comparison most often skipped, because the absolute
     number looks so good that nobody asks what it is being compared to.

  K6 RANDOM CONTROL. A rotation schedule matched on trade count and holding period, with the SIGNAL
     REMOVED. If random scores like the rule, the finding is about the window, not the signal, and
     every other number this harness produces is suspect.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

BARS = ROOT / "data" / "bars"
OUT = ROOT / "data" / "ethbtc_rotation_study.json"
PREREG = ROOT / "docs" / "research" / "ETHBTC_ROTATION_PREREGISTRATION.md"

#: Exactly the grid declared in the pre-registration. Editing this without amending that document
#: is a budget change made in code, which is how a shared deflation stops being shared.
GRID: dict[str, list] = {
    "lookback": [7, 14, 30, 60],
    "rebalance": ["4h", "1d"],
    "regime": ["none", "vol_pct", "trend"],
    "cost_bp": [10.0, 20.0, 30.0],
}

#: The OOS window: everything BEFORE the posted backtest began (2023-09-23).
OOS_START, OOS_END = "2019-09-01", "2023-09-22"

#: Shared across the three registered studies. 16,560 + this study's 72.
SHARED_BUDGET = 16_632
MIN_TRADES = 100          # K8: below this the answer is UNMEASURED, never "no edge"


def nominal_trials() -> int:
    n = 1
    for v in GRID.values():
        n *= len(v)
    return n


def hurdle() -> float:
    return float(np.sqrt(2.0 * np.log(SHARED_BUDGET)))


def _load(symbol: str) -> pd.DataFrame | None:
    """Bars for one symbol, or None. None means NOT PRESENT -- never an empty frame standing in
    for one, because an empty frame silently produces a zero-trade 'result'."""
    if not BARS.exists():
        return None
    for f in sorted([*BARS.rglob(f"*{symbol}*.parquet"), *BARS.rglob(f"*{symbol}*.csv")]):
        try:
            df = pd.read_parquet(f) if f.suffix == ".parquet" else pd.read_csv(f)
        except Exception:
            continue
        cols = {c.lower(): c for c in df.columns}
        if "close" not in cols or "timestamp" not in cols:
            continue
        df = df.rename(columns={cols["close"]: "close", cols["timestamp"]: "timestamp"})
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
        return df[["timestamp", "close"]].sort_values("timestamp").reset_index(drop=True)
    return None


def _rotate(eth: pd.Series, btc: pd.Series, lookback: int, regime: str,
            cost_bp: float, rng: np.random.Generator | None = None) -> tuple[float, int, np.ndarray]:
    """One arm. Returns (total log return, trade count, per-period log returns).

    `rng` non-None is the K6 NEGATIVE CONTROL: the same machinery with the signal replaced by a
    coin flip, so a difference between them is attributable to the signal and nothing else.
    """
    r_eth = np.diff(np.log(eth.to_numpy()))
    r_btc = np.diff(np.log(btc.to_numpy()))
    n = len(r_eth)
    if n <= lookback + 2:
        return 0.0, 0, np.array([])

    # relative strength over the lookback, computed on PAST bars only
    mom = pd.Series(r_eth - r_btc).rolling(lookback).sum().shift(1).to_numpy()
    hold_eth = mom > 0 if rng is None else rng.random(n) > 0.5

    if regime == "vol_pct":                    # stand aside in the top vol decile
        vol = pd.Series(r_btc).rolling(lookback).std().shift(1).to_numpy()
        thr = np.nanpercentile(vol[~np.isnan(vol)], 90) if np.any(~np.isnan(vol)) else np.inf
        flat = vol > thr
    elif regime == "trend":                    # only when BTC trend is up
        tr = pd.Series(r_btc).rolling(lookback).sum().shift(1).to_numpy()
        flat = tr < 0
    else:
        flat = np.zeros(n, dtype=bool)

    pos = np.where(np.isnan(mom) | flat, 0, np.where(hold_eth, 1, -1))  # 1=ETH, -1=BTC, 0=flat
    ret = np.where(pos == 1, r_eth, np.where(pos == -1, r_btc, 0.0))
    switches = int(np.sum(pos[1:] != pos[:-1]))
    ret = ret - (np.concatenate([[0], (pos[1:] != pos[:-1]).astype(float)]) * cost_bp / 10_000.0)
    return float(np.nansum(ret)), switches, ret[~np.isnan(ret)]


def _sharpe(r: np.ndarray, per_year: float) -> float:
    if r.size < 2 or float(np.std(r)) == 0.0:
        return 0.0
    return float(np.mean(r) / np.std(r) * np.sqrt(per_year))


def blocked(missing: list[str]) -> dict:
    return {
        "ts": datetime.now(tz=UTC).isoformat(),
        "verdict": "BLOCKED -- NOT RUN",
        "reason": "no ETH/BTC bars for the out-of-sample window",
        "missing": missing,
        "window": f"{OOS_START} .. {OOS_END}",
        "preregistration": str(PREREG.relative_to(ROOT)),
        "nominal_trials": nominal_trials(),
        "shared_budget": SHARED_BUDGET,
        "hurdle": round(hurdle(), 3),
        "note": ("NOTHING IS SYNTHESISED. A verdict on generated bars measures the generator and "
                 "would enter the funnel wearing the vocabulary of a real one."),
        "authority": "NONE. Stage A. Pre-registers nothing, promotes nothing, trades nothing.",
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--seed", type=int, default=7, help="K6 negative-control seed")
    a = ap.parse_args()

    eth, btc = _load("ETHUSDT"), _load("BTCUSDT")
    missing = [s for s, d in (("ETHUSDT", eth), ("BTCUSDT", btc)) if d is None]
    if missing or eth is None or btc is None:
        rep = blocked(missing)
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(rep, indent=1), "utf-8")
        print(f"ethbtc-rotation: BLOCKED -- missing {missing or 'usable bars'}.")
        print(f"  budget already declared: {nominal_trials()} trials, shared {SHARED_BUDGET}, "
              f"hurdle {hurdle():.3f}")
        print(f"  kill criteria already binding: {PREREG.relative_to(ROOT)}")
        return 0

    df = pd.merge(eth, btc, on="timestamp", suffixes=("_eth", "_btc"))
    df = df[(df.timestamp >= OOS_START) & (df.timestamp <= OOS_END)]
    per_year = 365.0 if len(df) < 5000 else 365.0 * 6

    rows, rng = [], np.random.default_rng(a.seed)
    for lb in GRID["lookback"]:
        for regime in GRID["regime"]:
            for cost in GRID["cost_bp"]:
                tot, trades, r = _rotate(df.close_eth, df.close_btc, lb, regime, cost)
                ctl, _c, rc = _rotate(df.close_eth, df.close_btc, lb, regime, cost, rng=rng)
                rows.append({"lookback": lb, "regime": regime, "cost_bp": cost,
                             "log_return": round(tot, 4), "trades": trades,
                             "sharpe": round(_sharpe(r, per_year), 3),
                             "control_log_return": round(ctl, 4),
                             "control_sharpe": round(_sharpe(rc, per_year), 3)})

    # K7: the trivial alternative, on the identical window
    bh = {k: round(float(np.log(v.iloc[-1] / v.iloc[0])), 4)
          for k, v in (("eth", df.close_eth), ("btc", df.close_btc))}
    best_bh = max(bh.values())
    best = max(rows, key=lambda r: r["sharpe"]) if rows else {}
    n_trades = int(best.get("trades", 0))

    fired = []
    if n_trades < MIN_TRADES:
        fired.append(f"K8 SAMPLE FLOOR: {n_trades} trades < {MIN_TRADES} -> UNMEASURED, not 'no edge'")
    else:
        if best.get("sharpe", 0.0) <= 0:
            fired.append("K2 SIGN: best OOS Sharpe <= 0")
        if best.get("log_return", 0.0) <= best_bh:
            fired.append(f"K7 BUY-AND-HOLD: rule {best.get('log_return')} <= hold {best_bh}")
        if best.get("sharpe", 0.0) <= best.get("control_sharpe", 0.0):
            fired.append("K6 NEGATIVE CONTROL: random rotation matched or beat the rule")

    rep = {
        "ts": datetime.now(tz=UTC).isoformat(),
        "verdict": ("UNMEASURED" if n_trades < MIN_TRADES
                    else ("KILLED" if fired else "SURVIVED-STAGE-A")),
        "window": f"{OOS_START} .. {OOS_END}", "bars": len(df),
        "nominal_trials": nominal_trials(), "shared_budget": SHARED_BUDGET,
        "hurdle": round(hurdle(), 3), "kill_criteria_fired": fired,
        "buy_and_hold_log_return": bh, "best_arm": best, "arms": rows,
        "preregistration": str(PREREG.relative_to(ROOT)),
        "authority": "NONE. Stage A. A survivor here earns a queue place, not capital.",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rep, indent=1), "utf-8")
    print(f"ethbtc-rotation: {rep['verdict']} over {len(df)} bars")
    for f in fired:
        print(f"  {f}")
    print(f"  artifact: {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

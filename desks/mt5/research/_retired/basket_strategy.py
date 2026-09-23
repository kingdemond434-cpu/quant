"""The reconstructed directional-basket strategy, built and tested.

This implements the hypothesis inferred from the mirrored Profit Engine Pro
fills, and then tries to break it. The reconstruction, in the operator's own
words:

    short-term directional bias -> structural/liquidity entry zone -> one
    equal-sized ticket -> additional equal-sized tickets at subsequent valid
    levels -> weighted basket state -> close together at a common target ->
    abort the whole basket when the higher-level thesis invalidates

The measurements on his fills support the shape: escalation 1.00x (equal lots,
not martingale), add spacing cv 1.50 with a 183x spread (structure-driven, not a
ladder), and three size regimes that overlap in time (confidence tiers, not
equity scaling).

WHAT THIS TEST CAN AND CANNOT SETTLE

It runs on H1, and he almost certainly trades M5/M15. So this tests the
MECHANISM — does a directional basket with equal-lot adds at structure levels
and a common exit carry an edge on gold — and not his implementation. A null
here does not clear him; it says the mechanism as stated does not survive at
this resolution, which is a weaker claim and the honest one.

THE ABLATION IS THE POINT, AGAIN

A basket strategy's headline P&L is not evidence about its entries. The adds
happen at better prices by construction, so any basket that ever recovers looks
like it had good entries. `ablate()` strips one layer at a time — first entry
only, no adds, depth-capped, no common exit — and the arm that matters is FIRST
ENTRY ONLY at fixed size. If that is negative while the basket is positive, the
return is the recovery layer and there is no entry edge to rebuild.
"""
from __future__ import annotations

import math
import sys
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))
sys.path.insert(0, str(BASE / "research"))

from mt5desk import families  # noqa: E402

STRATEGY_VERSION = "basket-2026-08-18-a"

#: Maximum tickets in one basket. His deepest observed was 4.
MAX_DEPTH = 4

#: Basket target and stop, in ATR of the entry bar, measured from the
#: LOT-WEIGHTED average entry — which is how he exits, per the common-exit
#: signature in his fills.
TARGET_ATR = 1.0
STOP_ATR = 3.0

#: Bars a basket may stay open before it is abandoned at market. Without this a
#: losing basket is held forever and the backtest reports a win it only got by
#: waiting past any horizon a real account would tolerate.
MAX_BARS = 48


@dataclass
class BasketTrade:
    open_i: int
    close_i: int
    direction: int                     # +1 long, -1 short
    entries: list = field(default_factory=list)   # (bar_index, price)
    exit_price: float = 0.0
    risk_per_unit: float = 1.0
    reason: str = ""

    @property
    def depth(self) -> int:
        return len(self.entries)

    @property
    def weighted_entry(self) -> float:
        return sum(p for _, p in self.entries) / len(self.entries)

    def r_basket(self) -> float:
        """Basket R at EQUAL lots: weighted-average entry against the exit."""
        return ((self.exit_price - self.weighted_entry) * self.direction
                / self.risk_per_unit)

    def r_first_only(self) -> float:
        """THE DECISIVE ARM. What the first entry alone paid, same exit."""
        return ((self.exit_price - self.entries[0][1]) * self.direction
                / self.risk_per_unit)

    def r_at_depth(self, d: int) -> float:
        """Basket R capped at the first `d` tickets."""
        e = self.entries[:max(1, d)]
        w = sum(p for _, p in e) / len(e)
        return (self.exit_price - w) * self.direction / self.risk_per_unit


def _atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    tr = pd.concat([df["high"] - df["low"],
                    (df["high"] - df["close"].shift(1)).abs(),
                    (df["low"] - df["close"].shift(1)).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, min_periods=n).mean()


def _swept(df: pd.DataFrame, i: int, look: int = 20) -> int:
    """Direction implied by a liquidity sweep on the previous bar, else 0.

    Took out a recent extreme and closed back inside — the signature his own
    baskets are built around, and the one the entry classifier scores.
    """
    if i < look + 2:
        return 0
    w = df.iloc[i - look - 1:i - 1]
    prev = df.iloc[i - 1]
    hi, lo = w["high"].max(), w["low"].min()
    if prev["high"] > hi and prev["close"] < hi:
        return -1                       # swept highs, reversed down
    if prev["low"] < lo and prev["close"] > lo:
        return +1
    return 0


def _displaced(df: pd.DataFrame, i: int, atr: pd.Series) -> int:
    """Direction implied by a displacement bar: range > 1.5x ATR, closed strong."""
    if i < 2 or not np.isfinite(atr.iloc[i - 1]) or atr.iloc[i - 1] <= 0:
        return 0
    b = df.iloc[i - 1]
    if (b["high"] - b["low"]) <= 1.5 * atr.iloc[i - 1]:
        return 0
    body = b["close"] - b["open"]
    rng = b["high"] - b["low"]
    if rng <= 0:
        return 0
    if body / rng > 0.5:
        return +1
    if body / rng < -0.5:
        return -1
    return 0


def simulate(df: pd.DataFrame, max_depth: int = MAX_DEPTH,
             target_atr: float = TARGET_ATR, stop_atr: float = STOP_ATR,
             max_bars: int = MAX_BARS, add_on_structure: bool = True) -> list:
    """Run the reconstructed strategy. Returns closed BasketTrades.

    ONE BASKET AT A TIME, and no new basket while one is open — he manages a
    thesis, not a portfolio of overlapping ones, and allowing concurrency would
    inflate the trade count with correlated copies of the same idea.
    """
    atr = _atr(df)
    out: list = []
    i, n = 30, len(df)
    while i < n - 1:
        a = atr.iloc[i]
        if not np.isfinite(a) or a <= 0:
            i += 1
            continue
        d = _swept(df, i) or _displaced(df, i, atr)
        if d == 0:
            i += 1
            continue

        entry = float(df.iloc[i]["open"])
        bt = BasketTrade(open_i=i, close_i=i, direction=d,
                         entries=[(i, entry)], risk_per_unit=float(a))
        target_from = entry
        j = i + 1
        while j < n and (j - i) <= max_bars:
            bar = df.iloc[j]
            wavg = bt.weighted_entry
            tgt = wavg + d * target_atr * a
            stp = wavg - d * stop_atr * a

            # STOP CHECKED BEFORE TARGET on the same bar. Without an intrabar
            # series the order is unknowable, and assuming the favourable one is
            # how a backtest manufactures its edge.
            if (d > 0 and bar["low"] <= stp) or (d < 0 and bar["high"] >= stp):
                bt.exit_price, bt.close_i, bt.reason = stp, j, "basket_stop"
                break
            if (d > 0 and bar["high"] >= tgt) or (d < 0 and bar["low"] <= tgt):
                bt.exit_price, bt.close_i, bt.reason = tgt, j, "basket_target"
                break
            # ADD at a subsequent valid level, in either direction from entry —
            # he pyramids AND averages, which is why the add rule is structural
            # rather than "every X against me".
            if add_on_structure and bt.depth < max_depth:
                if (_swept(df, j) == d) or (_displaced(df, j, atr) == d):
                    bt.entries.append((j, float(bar["open"])))
            j += 1
        else:
            j = min(j, n - 1)
        if not bt.reason:
            bt.exit_price = float(df.iloc[min(j, n - 1)]["close"])
            bt.close_i, bt.reason = min(j, n - 1), "timeout"
        out.append(bt)
        i = bt.close_i + 1
    return out


def ablate(trades: list, max_depth: int = MAX_DEPTH) -> dict:
    """Strip one layer at a time. The first-entry arm is the one that decides."""
    if not trades:
        return {"arms": {}, "verdict": "no trades"}
    arms = {
        "basket (as reconstructed)": [t.r_basket() for t in trades],
        "FIRST ENTRY ONLY": [t.r_first_only() for t in trades],
        "single-entry baskets only": [t.r_basket() for t in trades if t.depth == 1],
        "deep baskets (3+) only": [t.r_basket() for t in trades if t.depth >= 3],
    }
    for d in range(2, max_depth + 1):
        arms[f"capped at depth {d}"] = [t.r_at_depth(d) for t in trades]
    out = {}
    for k, v in arms.items():
        if not v:
            out[k] = {"n": 0}
            continue
        a = np.asarray(v, dtype=float)
        out[k] = {"n": len(a), "exp": float(a.mean()),
                  "t": float(a.mean() / (a.std(ddof=1) / math.sqrt(len(a))))
                  if len(a) > 1 and a.std(ddof=1) > 0 else 0.0,
                  "win": float((a > 0).mean()),
                  "worst": float(a.min())}
    basket = out["basket (as reconstructed)"]
    first = out["FIRST ENTRY ONLY"]
    if first["n"] and basket["n"]:
        if first["exp"] <= 0 < basket["exp"]:
            verdict = ("THE RETURN IS THE ADD LAYER. First entries alone lose; the "
                       "basket is positive only because it adds at better prices "
                       "and waits. There is no entry edge here to rebuild.")
        elif first["exp"] > 0:
            verdict = (f"THERE IS AN ENTRY EDGE: first entries alone average "
                       f"{first['exp']:+.4f}R over {first['n']} baskets. That is "
                       f"the part worth rebuilding, at bounded risk, without the "
                       f"add layer.")
        else:
            verdict = ("neither the basket nor its first entries is positive; "
                       "there is nothing here to reverse-engineer.")
    else:
        verdict = "insufficient trades"
    return {"arms": out, "verdict": verdict}


def main() -> int:
    print(f"RECONSTRUCTED BASKET STRATEGY  ({STRATEGY_VERSION})")
    print("H1 gold. He almost certainly trades M5/M15, so this tests the "
          "MECHANISM,\nnot his implementation. A null here does not clear him.\n")
    h1 = families._h1(pd.read_parquet(BASE / "data" / "universe" / "XAUUSD_H1.parquet"))
    trades = simulate(h1)
    print(f"{len(trades)} baskets over {h1.index.min().date()} -> "
          f"{h1.index.max().date()}")
    depths = {}
    for t in trades:
        depths[t.depth] = depths.get(t.depth, 0) + 1
    print(f"depth distribution: {dict(sorted(depths.items()))}")
    reasons = {}
    for t in trades:
        reasons[t.reason] = reasons.get(t.reason, 0) + 1
    print(f"exits: {reasons}\n")

    res = ablate(trades)
    print(f"{'arm':<28}{'n':>6}{'exp_R':>9}{'t':>8}{'win':>7}{'worst':>9}")
    print("-" * 68)
    for k, v in res["arms"].items():
        if not v.get("n"):
            print(f"{k:<28}{0:>6}   (none)")
            continue
        print(f"{k:<28}{v['n']:>6}{v['exp']:>+9.4f}{v['t']:>8.2f}"
              f"{v['win']:>7.0%}{v['worst']:>9.2f}")
    print()
    print(f"  {res['verdict']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Raise CAGR at a FIXED 35% drawdown. Four levers, none of which is new signal.

The book compounds at 63.2% on a 35% budget. Getting to 100% on the same budget
means raising IR, because at a fixed drawdown the size is whatever the budget
allows and CAGR follows IR. Three of the four things below add no forecasting
skill whatsoever -- they are portfolio construction, and they are the cheapest
IR available anywhere.

  EQUAL WEIGHT IS A CHOICE, AND A BAD ONE. Summing daily R across sleeves
  weights them by whatever variance each happens to have. A sleeve that trades
  bigger swings dominates the portfolio's drawdown without having earned the
  right to. Inverse-vol and risk-parity fix that for free.

  CONSTANT SIZE MEANS THE WORST VOL REGIME SETS THE BUDGET. Drawdown is spent
  almost entirely in high-volatility stretches; a constant q is therefore sized
  for the worst month and under-sized for the other eleven. Scaling inversely
  with TRAILING realised vol flattens the curve, and a flatter curve permits a
  larger average bet at the same maximum drawdown. This is the one lever that
  genuinely does both halves of "more return AND less drawdown".

  BREADTH IS THE ONLY ONE THAT NEEDS NEW SLEEVES, and it is the largest. Five
  sleeves on four symbols against 5.64 measured independent axes.

EVERY LEVER IS CAUSAL. Trailing windows only, shifted by one day so that a day's
size never knows that day's outcome. That shift is not pedantry: vol targeting
computed on the same day it sizes is a lookahead that produces a beautiful
equity curve and no money, and it is the single most common way this particular
trick is got wrong.

Trials are counted and printed. Four arms is four chances to find a lucky one.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mt5desk import families                                    # noqa: E402
from mt5desk.engine import Costs, run_backtest                  # noqa: E402
from mt5desk.sizing import q_for_drawdown                       # noqa: E402
from run_hunt11 import WINDOWS                                  # noqa: E402

UNI = _DESK / "data" / "universe"
OUT = _DESK / "reports" / "push_ceiling.json"
META = json.loads((UNI / "universe.json").read_text("utf-8"))
SPREAD_MULT, DD = 2.0, 0.35

CORE = [("XAUUSD", "asia"), ("USDJPY", "asia"), ("CADJPY", "asia"),
        ("EURJPY", "asia"), ("XAUUSD", "london_am")]
EXIT = dict(bank_frac=0.0, runner_trail_k=4.0, trail_tighten_k=1.0,
            trail_stall_bars=3)

_h1: dict = {}


def h1(sym):
    if sym not in _h1:
        _h1[sym] = families._h1(pd.read_parquet(UNI / f"{sym}_H1.parquet"))
    return _h1[sym]


def daily(trades):
    if not trades:
        return pd.Series(dtype=float)
    return pd.Series([t.r_multiple for t in trades],
                     index=pd.Index([t.entry_time.date() for t in trades])
                     ).groupby(level=0).sum()


def sleeve(sym, win, use_exit=True):
    df, costs = h1(sym), Costs.from_symbol(META[sym], SPREAD_MULT)
    base = list(families.family_session_range_breakout(df, **WINDOWS[win]))
    if use_exit:
        out = []
        for s in base:
            s2 = type(s)(**{**s.__dict__})
            for k, v in EXIT.items():
                setattr(s2, k, v)
            out.append(s2)
        base = out
    return daily(run_backtest(df, base, costs).trades)


def cagr(series, target=DD):
    """Half-edge CAGR at the drawdown budget, plus the size it needed."""
    r = series.dropna()
    if len(r) < 100:
        return float("nan"), 0.0
    x = r.to_numpy(float) - 0.5 * float(r.mean())
    q = q_for_drawdown(x, target)
    yrs = max((max(r.index) - min(r.index)).days / 365.25, 0.5)
    eq = float(np.prod(1.0 + q * x))
    return ((eq ** (1 / yrs) - 1.0) if eq > 0 else -1.0), q


def combine(sleeves: dict[str, pd.Series], weights=None) -> pd.Series:
    frame = pd.DataFrame(sleeves).fillna(0.0).sort_index()
    if weights is None:
        w = pd.Series(1.0, index=frame.columns)
    else:
        w = weights.reindex(frame.columns).fillna(0.0)
    return (frame * w).sum(axis=1)


def inverse_vol_weights(sleeves, lookback=250):
    """One weight per sleeve, from its FULL-SAMPLE vol.

    Full-sample is a deliberate simplification and it is declared: these are
    static allocation weights, not a timing signal, and re-deriving them daily
    would be a different (and more optimistic) experiment. It does mean the
    weights peek, so the honest reading is that this arm is an UPPER BOUND on
    what inverse-vol weighting is worth, not an estimate of it.
    """
    sd = {k: float(v.std(ddof=1)) for k, v in sleeves.items()}
    w = pd.Series({k: (1.0 / s if s > 0 else 0.0) for k, s in sd.items()})
    return w / w.sum() * len(w)


def vol_target(series, lookback=60, cap=3.0):
    """Scale each day by target/trailing-vol, SHIFTED so today cannot see itself."""
    r = series.sort_index()
    vol = r.rolling(lookback, min_periods=20).std(ddof=1).shift(1)
    target = float(r.std(ddof=1))
    mult = (target / vol).clip(upper=cap).fillna(1.0)
    return r * mult


def main() -> int:
    print(f"PUSH THE CEILING — fixed {100 * DD:.0f}% drawdown, half-edge, "
          f"{SPREAD_MULT:.0f}x spread\n")
    core = {f"{s}.{w}": sleeve(s, w) for s, w in CORE}

    rows = []
    g0, q0 = cagr(combine(core))
    rows.append(("1. core 5, equal weight (today)", g0, q0, len(core)))

    ivw = inverse_vol_weights(core)
    g1, q1 = cagr(combine(core, ivw))
    rows.append(("2. core 5, inverse-vol weight", g1, q1, len(core)))

    g2, q2 = cagr(vol_target(combine(core)))
    rows.append(("3. core 5, equal weight + vol target", g2, q2, len(core)))

    g3, q3 = cagr(vol_target(combine(core, ivw)))
    rows.append(("4. core 5, inverse-vol + vol target", g3, q3, len(core)))

    # --- breadth ----------------------------------------------------------
    syms = sorted(p.stem.replace("_H1", "") for p in UNI.glob("*_H1.parquet"))
    wide: dict[str, pd.Series] = {}
    for sym in syms:
        if sym not in META:
            continue
        for win in ("asia", "london_am"):
            try:
                s = sleeve(sym, win)
            except Exception:
                continue
            if len(s) >= 200:
                wide[f"{sym}.{win}"] = s
    if wide:
        g4, q4 = cagr(combine(wide))
        rows.append((f"5. all {len(wide)} sleeves, equal weight", g4, q4, len(wide)))
        wv = inverse_vol_weights(wide)
        g5, q5 = cagr(vol_target(combine(wide, wv)))
        rows.append((f"6. all {len(wide)} sleeves, inverse-vol + vol target",
                     g5, q5, len(wide)))

        # --- selective breadth ------------------------------------------
        # Trading ALL 44 fails because 39 of them lost their own selection
        # test; breadth multiplies IC, it does not manufacture it. The honest
        # question is whether a CAUSAL choice of which sleeves to run each
        # month recovers the breadth without the passengers. Ranked on trailing
        # Sharpe only, re-chosen monthly, with the ranking window ending the
        # day BEFORE the month it governs.
        frame = pd.DataFrame(wide).fillna(0.0).sort_index()
        for topn in (5, 10, 15):
            picks = pd.DataFrame(0.0, index=frame.index, columns=frame.columns)
            months = pd.Series(frame.index).map(lambda d: (d.year, d.month))
            for key in sorted(set(months)):
                mask = (months == key).to_numpy()
                first = int(np.argmax(mask))
                hist = frame.iloc[max(0, first - 250):first]
                if len(hist) < 120:
                    continue
                sd = hist.std(ddof=1).replace(0.0, np.nan)
                sharpe = (hist.mean() / sd).fillna(-9.9)
                for c in sharpe.sort_values(ascending=False).index[:topn]:
                    picks.loc[mask, c] = 1.0
            sel = (frame * picks).sum(axis=1)
            g, q = cagr(sel)
            rows.append((f"7. walk-forward top-{topn} of {len(wide)}, monthly",
                         g, q, topn))

    print(f"{'arm':<46}{'CAGR@35%':>11}{'q':>10}{'sleeves':>9}")
    for name, g, q, n in rows:
        print(f"{name:<46}{100 * g:>10.1f}%{q:>10.4f}{n:>9}")

    print(f"\n{len(rows)} arms tried. Arms 5 and 6 add sleeves that never "
          f"passed\nindividual selection: they are included because portfolio "
          f"value depends on\ncovariance rather than on each sleeve's own "
          f"t-stat, but that is an argument,\nnot evidence, and it is the one "
          f"result here most likely to be selection.")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(
        {"dd": DD, "arms": [{"name": n, "cagr": round(g, 5),
                             "q": round(q, 5), "sleeves": k}
                            for n, g, q, k in rows]}, indent=1), "utf-8")
    print(f"written: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

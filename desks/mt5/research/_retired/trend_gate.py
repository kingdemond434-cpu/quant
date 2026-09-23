"""Does the trend detector predict anything, and does gating an exit on it pay?

A detector can be scale-free, symmetric, causal and completely useless. Those
are hygiene properties; they say the number is well-formed, not that it carries
information. So this asks three separate questions and reports whichever answers
come back, including the unwelcome ones.

  1. DOES STRENGTH PREDICT?  Bin every bar by the detector's reading and measure
     what happens NEXT, in ATRs so the bins are comparable. If the top decile
     does not continue further than the bottom, nothing downstream can help.

  2. DOES GATING THE EXIT PAY?  The stall-tightening trail was measured over all
     pullback entries. Restricting it to bars the detector calls trending is a
     different policy and has to be measured as one, paired on identical events.

  3. IS `dying` WORTH ANYTHING BEYOND THE STALL?  Banking on the detector's
     death call is a THIRD policy, and the honest comparison is against the
     stall-tighten that already works -- not against doing nothing, which is a
     strawman that would flatter it.

ACROSS 22 INSTRUMENTS, NOT ONE. A result on XAUUSD alone is one draw. The
detector claims to be scale-free and symmetric, which is a claim that it should
work on EURUSD and BTCUSD too, and that claim is cheap to test and expensive to
skip. Per-symbol t-stats are printed so the reader can see whether an aggregate
is broad or is one instrument carrying twenty-one.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

_DESK = Path(__file__).resolve().parents[1]
if str(_DESK) not in sys.path:
    sys.path.insert(0, str(_DESK))

from mt5desk.trendday import atr, read                              # noqa: E402

UNI = _DESK / "data" / "universe"
HZ = 24          # bars of forward horizon
COST_ATR = 0.03  # round-trip cost as a fraction of ATR — small but not zero


def load(sym):
    df = pd.read_parquet(UNI / f"{sym}_H1.parquet")
    df.index = pd.DatetimeIndex(pd.to_datetime(df.index))
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")
    return df


def q1_prediction(syms):
    """Bin by strength; measure forward directional move in ATRs."""
    print("1. DOES STRENGTH PREDICT?  forward 24-bar move in the detected "
          "direction, in ATRs\n")
    print(f"{'strength bin':<16}" + "".join(f"{s:>9}" for s in
                                            ("n", "mean", "median", "t")))
    pools = {k: [] for k in ("0.0-0.3", "0.3-0.5", "0.5-0.7", "0.7-1.0")}
    for sym in syms:
        df = load(sym)
        c = df["close"].to_numpy(float)
        a = atr(df["high"].to_numpy(float), df["low"].to_numpy(float), c)
        r = read(df)
        n = len(c)
        i = np.arange(n - HZ)
        ok = (np.isfinite(a[i]) & (a[i] > 0) & (r.direction[i] != 0)
              & np.isfinite(r.strength[i]))
        fwd = np.where(ok, r.direction[i] * (c[i + HZ] - c[i]) / np.where(a[i] > 0, a[i], 1), np.nan)
        s = r.strength[i]
        for lo, hi, key in ((0.0, .3, "0.0-0.3"), (.3, .5, "0.3-0.5"),
                            (.5, .7, "0.5-0.7"), (.7, 1.01, "0.7-1.0")):
            m = ok & (s >= lo) & (s < hi)
            if m.sum():
                pools[key].append(fwd[m])
    for k, v in pools.items():
        if not v:
            continue
        x = np.concatenate(v)
        x = x[np.isfinite(x)]
        t = x.mean() / (x.std(ddof=1) / np.sqrt(len(x)))
        print(f"{k:<16}{len(x):>9}{x.mean():>9.3f}{np.median(x):>9.3f}{t:>9.2f}")


def trail(h, l, c, start, entry, a, side, k_wide, k_tight, stall_j,
          dying=None):
    """One trade under one exit policy. Stop checked before the trail updates."""
    stop = entry - side * k_wide * a
    ext, stall = entry, 0
    for j in range(start, min(start + HZ, len(c))):
        if side > 0 and l[j] <= stop:
            return (stop - entry) / a - COST_ATR
        if side < 0 and h[j] >= stop:
            return (entry - stop) / a - COST_ATR
        if dying is not None and dying[j]:
            return side * (c[j] - entry) / a - COST_ATR
        if side > 0:
            if h[j] > ext:
                ext, stall = h[j], 0
            else:
                stall += 1
        else:
            if l[j] < ext or ext == entry:
                ext, stall = l[j], 0
            else:
                stall += 1
        k = k_tight if (k_tight > 0 and stall >= stall_j) else k_wide
        stop = (max(stop, ext - k * a) if side > 0 else min(stop, ext + k * a))
    j = min(start + HZ, len(c)) - 1
    return side * (c[j] - entry) / a - COST_ATR


def events(sym):
    """Pullback entries in the detected direction, long AND short."""
    df = load(sym)
    h = df["high"].to_numpy(float); l = df["low"].to_numpy(float)
    c = df["close"].to_numpy(float)
    a = atr(h, l, c)
    r = read(df)
    out = []
    for i in range(300, len(c) - HZ - 6):
        d = r.direction[i]
        if d == 0 or not np.isfinite(a[i]) or a[i] <= 0 or r.dying[i]:
            continue
        # a 0.5-ATR retracement against the trend, good for 4 bars
        limit = c[i] - d * 0.5 * a[i]
        for j in range(i + 1, i + 5):
            if (d > 0 and l[j] <= limit) or (d < 0 and h[j] >= limit):
                out.append((i, j, limit, int(d), float(a[i]),
                            float(r.strength[i])))
                break
    return df, h, l, c, r, out


STATIC = [(k, 0.0, 10**9) for k in (1, 2, 3, 4, 6)]
ADAPT = [(4, 1.5, 2), (4, 1.5, 3), (4, 1, 3), (6, 2, 3), (3, 1, 2), (6, 1.5, 2)]


def paired(h, l, c, evs, fam_a, fam_b, dying_a=None, dying_b=None):
    d = []
    for (i, j, px, side, a, _s) in evs:
        x = np.mean([trail(h, l, c, j + 1, px, a, side, *p, dying=dying_a)
                     for p in fam_a])
        y = np.mean([trail(h, l, c, j + 1, px, a, side, *p, dying=dying_b)
                     for p in fam_b])
        d.append(x - y)
    d = np.array(d)
    if len(d) < 20:
        return None
    return d.mean(), 100 * float((d > 0).mean()), \
        d.mean() / (d.std(ddof=1) / np.sqrt(len(d))), len(d)


def main() -> int:
    syms = sorted(p.stem.replace("_H1", "") for p in UNI.glob("*_H1.parquet"))
    print(f"TREND GATE — {len(syms)} instruments, H1, {HZ}-bar horizon, "
          f"cost {COST_ATR} ATR round trip\n")
    q1_prediction(syms)

    print("\n2. ADAPTIVE vs STATIC TRAIL, on detector-selected entries "
          "(both sides)")
    print("   and 3. DYING-AS-FULL-EXIT vs the adaptive trail alone\n")
    print(f"{'symbol':<10}{'n':>6}{'adapt-static':>14}{'win%':>7}{'t':>7}"
          f"{'dying-adapt':>13}{'win%':>7}{'t':>7}")
    agg2, agg3 = [], []
    for sym in syms:
        df, h, l, c, r, evs = events(sym)
        if len(evs) < 50:
            continue
        p2 = paired(h, l, c, evs, ADAPT, STATIC)
        p3 = paired(h, l, c, evs, ADAPT, ADAPT, dying_a=r.dying, dying_b=None)
        if not p2 or not p3:
            continue
        agg2.append(p2[2]); agg3.append(p3[2])
        print(f"{sym:<10}{p2[3]:>6}{p2[0]:>14.4f}{p2[1]:>6.0f}%{p2[2]:>7.2f}"
              f"{p3[0]:>13.4f}{p3[1]:>6.0f}%{p3[2]:>7.2f}")
    for label, agg in (("adaptive beats static", agg2),
                       ("dying-exit beats adaptive alone", agg3)):
        a = np.array(agg)
        print(f"\n{label}: positive on {int((a > 0).sum())}/{len(a)} "
              f"instruments, mean t {a.mean():+.2f}, "
              f"sign test p = {2 * min((a > 0).mean(), (a < 0).mean()):.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

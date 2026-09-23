"""Score a ranker. Against the free one, on identical dates, net of what it cost.

THE ONLY QUESTION WORTH ASKING IS COMPARATIVE

"The model's picks made money" is not a result. Trend strength alone predicts
forward move across 22 instruments, so a ranker that reads the same state and
produces a similar ordering will also make money, and it will cost a hundred
times more to run. The number that decides anything is the model's edge OVER
BaselineRanker on the SAME dates, which is why both are run over one list of
briefs and never over whatever dates each happened to get.

TWO METRICS, BECAUSE THEY FAIL DIFFERENTLY

  IC     Spearman rank correlation between signed conviction and forward move,
         computed per date and then averaged. This is the quantity the
         fundamental law multiplies by sqrt(breadth), so it is the one that
         says whether the thing is worth scaling.

  W.R    the actual return of the unit-gross weight vector, in ATRs. A ranker
         can have a fine IC and lose money by putting its conviction in the
         wrong places, and this is the metric that notices.

WHAT THIS CANNOT SETTLE IN ONE SITTING

A model read takes ~78 seconds. Twenty dates is twenty-six minutes and an error
bar wide enough to drive through: at n=20 the standard error on a per-date IC of
0.05 is around 0.05, so a null and a real edge are indistinguishable. The
harness is therefore built to be run LARGE and unattended -- --dates 500 on the
VPS is the job that answers the question. Anything it prints at n=20 is a smoke
test proving the loop works, and it says so rather than being quoted as a
finding.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

_DESK = Path(__file__).resolve().parents[1]
if str(_DESK) not in sys.path:
    sys.path.insert(0, str(_DESK))

from mt5desk.analyst_rank import (BaselineRanker, ClaudeCodeRanker,   # noqa: E402
                                  RankError, build_brief)
from mt5desk.trendday import atr                                      # noqa: E402

UNI = _DESK / "data" / "universe"
HZ = 24


def load_universe(limit=None):
    frames = {}
    for p in sorted(UNI.glob("*_H1.parquet")):
        sym = p.stem.replace("_H1", "")
        df = pd.read_parquet(p)
        df.index = pd.DatetimeIndex(pd.to_datetime(df.index))
        if df.index.tz is None:
            df.index = df.index.tz_localize("UTC")
        frames[sym] = df
        if limit and len(frames) >= limit:
            break
    # Align on the common index. Doing this HERE and loudly, because a ranker
    # comparing instruments observed at different instants is comparing states
    # that never coexisted.
    idx = None
    for df in frames.values():
        idx = df.index if idx is None else idx.intersection(df.index)
    return {s: df.reindex(idx).ffill().dropna() for s, df in frames.items()}, idx


def forward(frames, syms, i):
    """Forward HZ-bar move per symbol, in ATRs at the decision bar."""
    out = np.full(len(syms), np.nan)
    for k, s in enumerate(syms):
        df = frames[s]
        if i + HZ >= len(df):
            continue
        c = df["close"].to_numpy(float)
        a = atr(df["high"].to_numpy(float)[:i + 1],
                df["low"].to_numpy(float)[:i + 1], c[:i + 1])[-1]
        if np.isfinite(a) and a > 0:
            out[k] = (c[i + HZ] - c[i]) / a
    return out


def spearman(a, b):
    ok = np.isfinite(a) & np.isfinite(b)
    if ok.sum() < 4 or len(set(a[ok])) < 2 or len(set(b[ok])) < 2:
        return np.nan
    ra = pd.Series(a[ok]).rank().to_numpy()
    rb = pd.Series(b[ok]).rank().to_numpy()
    return float(np.corrcoef(ra, rb)[0, 1])


def score(name, ics, wrs, elapsed, usage):
    ics = np.array([x for x in ics if np.isfinite(x)])
    wrs = np.array([x for x in wrs if np.isfinite(x)])
    if len(ics) < 2:
        print(f"{name:<12} too few usable dates ({len(ics)})")
        return None
    t_ic = ics.mean() / (ics.std(ddof=1) / np.sqrt(len(ics)))
    t_wr = wrs.mean() / (wrs.std(ddof=1) / np.sqrt(len(wrs)))
    print(f"{name:<12}{len(ics):>6}{ics.mean():>9.4f}{t_ic:>8.2f}"
          f"{wrs.mean():>10.4f}{t_wr:>8.2f}{elapsed / max(len(ics), 1):>9.1f}s"
          f"{usage:>12}")
    return {"n": len(ics), "ic": float(ics.mean()), "t_ic": float(t_ic),
            "wr": float(wrs.mean()), "t_wr": float(t_wr)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dates", type=int, default=20)
    ap.add_argument("--model-dates", type=int, default=0,
                    help="how many of those to also run the MODEL on (slow)")
    ap.add_argument("--model", default="claude-opus-5")
    ap.add_argument("--step", type=int, default=97,
                    help="bars between sampled dates; prime, to avoid "
                         "landing on the same hour of the day every time")
    ap.add_argument("--out", default=str(_DESK / "reports" / "rank_ic.json"))
    a = ap.parse_args()

    frames, idx = load_universe()
    syms = sorted(frames)
    n = min(len(frames[s]) for s in syms)
    print(f"{len(syms)} instruments, {n} aligned H1 bars, "
          f"{idx[0].date()} -> {idx[-1].date()}, horizon {HZ} bars\n")

    starts = list(range(300, n - HZ - 1, a.step))
    rng = np.random.default_rng(0)
    rng.shuffle(starts)
    picked = sorted(starts[:a.dates])

    print(f"{'ranker':<12}{'dates':>6}{'IC':>9}{'t':>8}{'W.R':>10}{'t':>8}"
          f"{'per date':>10}{'tokens':>12}")

    b_ic, b_wr, t0 = [], [], time.monotonic()
    briefs = {}
    for i in picked:
        try:
            br = build_brief(frames, i)
        except RankError:
            continue
        briefs[i] = br
        fwd = forward(frames, syms, i)
        w = BaselineRanker().rank(br).as_weights(syms)
        b_ic.append(spearman(w, fwd))
        b_wr.append(float(np.nansum(w * np.nan_to_num(fwd))))
    base = score("baseline", b_ic, b_wr, time.monotonic() - t0, "0")

    model = None
    if a.model_dates:
        ranker = ClaudeCodeRanker(model=a.model, billed=False)
        m_ic, m_wr, tok, t0 = [], [], 0, time.monotonic()
        paired_b_ic, paired_b_wr = [], []
        for i in sorted(briefs)[:a.model_dates]:
            try:
                rd = ranker.rank(briefs[i])
            except RankError as e:
                print(f"  {briefs[i].as_of}: {e}")
                continue
            tok += int(rd.usage.get("in", 0)) + int(rd.usage.get("out", 0))
            fwd = forward(frames, syms, i)
            w = rd.as_weights(syms)
            m_ic.append(spearman(w, fwd))
            m_wr.append(float(np.nansum(w * np.nan_to_num(fwd))))
            wb = BaselineRanker().rank(briefs[i]).as_weights(syms)
            paired_b_ic.append(spearman(wb, fwd))
            paired_b_wr.append(float(np.nansum(wb * np.nan_to_num(fwd))))
        model = score(f"{a.model[:11]}", m_ic, m_wr, time.monotonic() - t0,
                      f"{tok:,}")
        if model and len(m_wr) > 2:
            d = np.array(m_wr) - np.array(paired_b_wr)
            t = d.mean() / (d.std(ddof=1) / np.sqrt(len(d)))
            print(f"\nPAIRED, same dates: model - baseline = {d.mean():+.4f} "
                  f"ATR/date, t = {t:.2f}, n = {len(d)}")
            if len(d) < 100:
                print(f"  n = {len(d)} IS A SMOKE TEST, NOT A FINDING. The "
                      f"standard error here is {d.std(ddof=1)/np.sqrt(len(d)):.4f} "
                      f"ATR; run --dates 500 --model-dates 500 unattended "
                      f"before believing any sign.")

    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(
        {"horizon": HZ, "n_instruments": len(syms), "baseline": base,
         "model": model, "model_name": a.model if a.model_dates else None},
        indent=1), "utf-8")
    print(f"\nwritten: {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

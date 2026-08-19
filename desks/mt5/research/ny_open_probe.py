"""Is the New York cash open a special hour for XAUUSD, or just a busy one?

The one structural finding that survived every enlargement of the Profit Engine
sample is an entry window at 16:30-16:37 server time, p = 3.0e-10 across 26
timestamps, two instruments and three days. At the UTC+3 server default that is
13:30-13:37 UTC -- the first seven minutes of the New York cash session.

This asks whether that hour carries anything our own eight years of gold bars
can see, because if it does not, there is nothing to copy no matter how real his
window is.

WHAT H1 CAN AND CANNOT ANSWER, SAID FIRST

It cannot test his trade. He holds 13-20 minutes and targets about a tenth of a
percent; at H1 that entire trade lives inside one bar. So this does NOT measure
his edge and a null here does not refute him.

What it CAN measure is whether the hour is exploitable AT ALL:

  REACHABILITY  does the bar range even clear his target often enough to trade?
                a target you cannot reach is not a strategy.
  DIRECTION     is there a mean return in that hour, and does it beat the
                dispersion? this is the piece a sleeve would be built on.
  PERSISTENCE   does the hour's move continue into the next hour or reverse?
                fade and follow are opposite trades and the sign decides which.

Every hour is measured the same way so the open is judged against the rest of
the day rather than against zero. The DST boundary is handled explicitly: the
cash open is 13:30 UTC from March to November and 14:30 UTC otherwise, so
tagging one fixed UTC hour year-round would smear the two together and blunt
exactly the effect being looked for.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

_DESK = Path(__file__).resolve().parents[1]
if str(_DESK) not in sys.path:
    sys.path.insert(0, str(_DESK))

UNI = _DESK / "data" / "universe"
OUT = _DESK / "reports" / "ny_open_probe.json"
TARGET_PCT = 0.11 / 100.0     # his basket target, the reachability yardstick


def us_dst(ts: pd.Timestamp) -> bool:
    """US DST: second Sunday in March to first Sunday in November."""
    y = ts.year
    mar = pd.Timestamp(year=y, month=3, day=1)
    start = mar + pd.Timedelta(days=(6 - mar.dayofweek) % 7 + 7)
    nov = pd.Timestamp(year=y, month=11, day=1)
    end = nov + pd.Timedelta(days=(6 - nov.dayofweek) % 7)
    return start <= ts.tz_localize(None) < end


def main() -> int:
    sym = sys.argv[1] if len(sys.argv) > 1 else "XAUUSD"
    df = pd.read_parquet(UNI / f"{sym}_H1.parquet")
    df.index = pd.DatetimeIndex(pd.to_datetime(df.index))
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")
    df = df[df.index.dayofweek < 5]

    o = df["open"].to_numpy(float)
    h = df["high"].to_numpy(float)
    lo = df["low"].to_numpy(float)
    c = df["close"].to_numpy(float)
    ret = (c - o) / o
    rng = (h - lo) / o
    nxt = np.full(len(c), np.nan)
    nxt[:-1] = ret[1:]

    hours = df.index.hour.to_numpy()
    # the bar that CONTAINS the cash open, DST-aware
    dst = np.array([us_dst(t) for t in df.index])
    is_open_bar = np.where(dst, hours == 13, hours == 14)

    print(f"{sym}: {len(df)} weekday H1 bars, "
          f"{df.index.min().date()} -> {df.index.max().date()}")
    print(f"target yardstick = {100 * TARGET_PCT:.2f}% of price "
          f"(his lot-weighted basket target)\n")
    print(f"{'hour UTC':>9}{'n':>7}{'reach%':>9}{'mean bp':>9}{'t':>7}"
          f"{'next-h corr':>13}")
    rows = []
    for hr in range(24):
        m = hours == hr
        if m.sum() < 200:
            continue
        r, rr, nx = ret[m], rng[m], nxt[m]
        ok = np.isfinite(nx)
        reach = float((rr >= TARGET_PCT).mean())
        t = float(r.mean() / (r.std(ddof=1) / np.sqrt(len(r)))) if r.std(ddof=1) else 0.0
        corr = float(np.corrcoef(r[ok], nx[ok])[0, 1]) if ok.sum() > 50 else float("nan")
        rows.append({"hour_utc": hr, "n": int(m.sum()),
                     "reach_frac": round(reach, 4),
                     "mean_bp": round(1e4 * float(r.mean()), 3),
                     "t": round(t, 2), "next_hour_corr": round(corr, 4)})
        print(f"{hr:>9}{m.sum():>7}{100 * reach:>8.1f}%{1e4 * r.mean():>9.2f}"
              f"{t:>7.2f}{corr:>13.4f}")

    m = is_open_bar
    r, rr, nx = ret[m], rng[m], nxt[m]
    ok = np.isfinite(nx)
    reach = float((rr >= TARGET_PCT).mean())
    t = float(r.mean() / (r.std(ddof=1) / np.sqrt(len(r))))
    corr = float(np.corrcoef(r[ok], nx[ok])[0, 1])
    allreach = float((rng >= TARGET_PCT).mean())
    print(f"\n{'NY OPEN':>9}{m.sum():>7}{100 * reach:>8.1f}%"
          f"{1e4 * r.mean():>9.2f}{t:>7.2f}{corr:>13.4f}   <- DST-aware")
    print(f"{'all hours':>9}{len(rng):>7}{100 * allreach:>8.1f}%"
          f"{1e4 * ret.mean():>9.2f}")

    print("\nREADING IT")
    best = max(rows, key=lambda x: x["reach_frac"])
    print(f"  most reachable hour: {best['hour_utc']:02d} UTC at "
          f"{100 * best['reach_frac']:.1f}%; the NY open bar is "
          f"{100 * reach:.1f}%.")
    print(f"  the open's mean return is {1e4 * r.mean():+.2f} bp at t = {t:.2f}.")
    sig = [x for x in rows if abs(x["t"]) > 2.0]
    print(f"  {len(sig)} of {len(rows)} hours have |t| > 2 on the mean return "
          f"(chance alone gives ~{len(rows) * 0.05:.1f}).")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(
        {"symbol": sym, "target_pct": TARGET_PCT, "hours": rows,
         "ny_open": {"n": int(m.sum()), "reach_frac": round(reach, 4),
                     "mean_bp": round(1e4 * float(r.mean()), 3),
                     "t": round(t, 2), "next_hour_corr": round(corr, 4)}},
        indent=1), "utf-8")
    print(f"\nwritten: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

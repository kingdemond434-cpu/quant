#!/usr/bin/env python3
"""KIMCHI DEEP BACKFILL: 143 aligned days -> ~2,600, so the screen can actually resolve.

WHY. The 2026-07-29 alignment "fix" retracted the celebrated IC +0.2249 as ~73% timestamp overlap,
on the premise that Upbit's candle_date_time_utc is a KST-day OPEN labelling closes ~15h early.
THAT PREMISE WAS REFUTED on 2026-07-30 from Upbit's own hourly candles (R0067): Upbit dailies are
UTC-midnight-boundary, so the original keying was same-instant and the +1d "fix" was the error.
The retraction itself STANDS on other evidence -- kimchi showed no edge at full 8.2y depth
(IC +0.0012, n=2987) and the original screen ran on a thin 200d window.
The honest re-screen returned forward IC +0.0604 with residual IC +0.1274 -- and verdict
SCREEN-UNDERPOWERED, because at n_eff~121 the detection floor is 1.96/sqrt(121) = 0.178. The
signal was not refuted; it was UNRESOLVABLE. That is a sample-size problem, and the sample size
was an accident: every consumer called Upbit with count=200 and nobody paginated.

WHAT CHANGES. Upbit's `to=` parameter walks back indefinitely (verified: 3 pages reached
2024-12-10); Yahoo serves 2,611 days of USDKRW; Binance klines paginate on startTime. The binding
constraint is the FX leg at ~2016-07. At n~2,600 the floor falls to 1.96/sqrt(2600) = 0.038, so a
residual IC of 0.1274 would sit 3.4x ABOVE it rather than below.

WHY THE RESIDUAL IS THE NUMBER TO WATCH. premium = upbit_usd/binance_usd - 1 puts the Binance
price in the DENOMINATOR, so the premium is mechanically negatively correlated with same-day BTC
return (measured same-period corr -0.692). That contamination is construction, not information --
which is exactly what the harness's de-contamination step removes, and why residual IC (+0.1274)
runs at double the raw IC (+0.0604).

HONESTY, stated up front so the result is not read as a promise: more data buys POWER, never a
verdict. The IC may shrink toward zero on a longer sample -- that is the test working, and a
powered null on 7 years is worth far more than an unpowered maybe on 143 days, because it is
graveyard-grade knowledge instead of an open question. A 7-year window also spans regimes the
premium behaved very differently in (2017-18 saw >50% premiums under different capital controls),
so the run reports per-era slices rather than one pooled number that averages regimes together.

TRIAL ACCOUNTING (TARGET/HORIZON SWEEP DUTY): every target-horizon cell below is a DSR-counted
trial and all are reported, not just the best -- reporting the winning cell alone is p-hacking.
The archive is written to data/kimchi_premium_history.jsonl (L1.11d historical monopolisation:
own the series locally, immune to API deprecation).
"""
from __future__ import annotations

import datetime as dt
import json
import sys
import time
import urllib.request
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from libs.research.axis_screen import stage_a_screen  # noqa: E402
from libs.research.upbit_data import upbit_daily_history  # noqa: E402

_UA = {"User-Agent": "Mozilla/5.0 (quant-desk kimchi-backfill)"}
_ARCHIVE = ROOT / "data/kimchi_premium_history.jsonl"


def _get(url: str, timeout: int = 30):
    return json.loads(urllib.request.urlopen(urllib.request.Request(url, headers=_UA),
                                             timeout=timeout).read())


def upbit_history(market: str = "KRW-BTC", pages: int = 40) -> dict[str, float]:
    """Deep Upbit history from the ONE keying source (R0068).

    This function used to re-derive the join inline, which is precisely how the 07-29 keying change
    reached the live collector while the HISTORY it gets screened against kept a different one.
    """
    return upbit_daily_history(market, pages=pages)


def binance_history(sym: str = "BTCUSDT", start: str = "2016-01-01") -> dict[str, float]:
    out: dict[str, float] = {}
    cur = int(dt.datetime.fromisoformat(start).replace(tzinfo=dt.UTC).timestamp() * 1000)
    end = int(time.time() * 1000)
    while cur < end:
        rows = _get(f"https://api.binance.com/api/v3/klines?symbol={sym}&interval=1d"
                    f"&startTime={cur}&limit=1000")
        if not rows:
            break
        for r in rows:
            d = dt.datetime.fromtimestamp(int(r[0]) / 1000, tz=dt.UTC).date().isoformat()
            out[d] = float(r[4])
        cur = int(rows[-1][0]) + 86_400_000
        if len(rows) < 1000:
            break
        time.sleep(0.15)
    return out


def usdkrw_history() -> dict[str, float]:
    y = _get("https://query1.finance.yahoo.com/v8/finance/chart/KRW=X?interval=1d&range=10y")
    res = y["chart"]["result"][0]
    ts, cl = res["timestamp"], res["indicators"]["quote"][0]["close"]
    return {dt.datetime.fromtimestamp(int(t), tz=dt.UTC).date().isoformat(): float(c)
            for t, c in zip(ts, cl, strict=False) if c}


def main() -> None:
    print("fetching (Upbit paginated / Binance klines / Yahoo FX 10y)...")
    kb, gb, fx = upbit_history(), binance_history(), usdkrw_history()
    print(f"  upbit {len(kb)} | binance {len(gb)} | usdkrw {len(fx)}")

    dates = sorted(set(kb) & set(gb) & set(fx))
    print(f"  ALIGNED: {len(dates)} days  ({dates[0]} .. {dates[-1]})   [was 143]")
    if len(dates) < 200:
        raise SystemExit("backfill did not increase the sample -- aborting rather than reporting")

    prem = np.array([kb[d] / fx[d] / gb[d] - 1.0 for d in dates])
    btc = np.array([gb[d] for d in dates])

    with _ARCHIVE.open("w", encoding="utf-8") as fh:      # L1.11d: own the series locally
        for d, p, b in zip(dates, prem, btc, strict=False):
            fh.write(json.dumps({"date": d, "premium": round(float(p), 6),
                                 "btc_close": float(b)}) + "\n")
    print(f"  archived -> {_ARCHIVE.name} ({len(dates)} rows)")

    floor = 1.96 / np.sqrt(len(dates))
    print(f"\n  detection floor at this n: {floor:.4f}   (was 0.178 at n_eff 121)")

    print("\n=== ALL CELLS (every one is a DSR-counted trial; none omitted) ===")
    for horizon in (1, 5, 20):
        ret = np.zeros(len(btc))
        ret[horizon:] = btc[horizon:] / btc[:-horizon] - 1.0
        r = stage_a_screen(prem, ret, name=f"kimchi_h{horizon}d", zwin=20, horizon_days=horizon)
        print(f"  h={horizon:>2}d  n={r.get('n'):>5}  IC {r.get('ic'):+.4f}  "
              f"resid {r.get('residual_ic'):+.4f}  same {r.get('same_period_corr'):+.3f}  "
              f"n_eff {r.get('n_eff')}  floor {r.get('min_detectable_ic')}  "
              f"powered {r.get('powered')}  -> {r.get('verdict')}")

    print("\n=== PER-ERA (a pooled 7y number averages regimes that behaved differently) ===")
    for lo, hi in (("2016-01-01", "2019-01-01"), ("2019-01-01", "2022-01-01"),
                   ("2022-01-01", "2024-01-01"), ("2024-01-01", "2027-01-01")):
        idx = [i for i, d in enumerate(dates) if lo <= d < hi]
        if len(idx) < 120:
            print(f"  {lo[:7]}..{hi[:7]}  only {len(idx)} days -- skipped")
            continue
        p2, b2 = prem[idx], btc[idx]
        r2 = np.zeros(len(b2))
        r2[1:] = b2[1:] / b2[:-1] - 1.0
        r = stage_a_screen(p2, r2, name=f"kimchi_{lo[:4]}", zwin=20)
        print(f"  {lo[:7]}..{hi[:7]}  n={r.get('n'):>5}  IC {r.get('ic'):+.4f}  "
              f"resid {r.get('residual_ic'):+.4f}  powered {r.get('powered')}  -> {r.get('verdict')}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""KR PER-ASSET PREMIUM, FULL-DEPTH PANEL -- R0069's named decisive experiment.

THE QUESTION. The recent-era panel (175 assets x ~380d, prospector 2026-07-30) returned a
pre-declared HONEST NULL: median IC +0.0050, share-positive 54%, sign-z 0.98 NS. Three assets with
8.2y history showed h=1 cells of +0.045/+0.053 -- clean but underpowered. Either the effect is real
and lived in an earlier regime (larger KR capital-control frictions), or the 3-asset cells are what
a small subset looks like. Only LENGTH resolves that: the desk's own measured lesson is that
campaign WIDTH buys nothing and sample LENGTH buys everything.

WHAT THE ROW'S SPEC GOT WRONG, MEASURED BEFORE SPENDING THE BUDGET. R0069 specified "Upbit
paginated to 2017-09 per asset, ~30min fetch, n_eff ~50k" over the 175-asset panel. Probing all 277
KRW markets: only 42 have any history before 2019-01-01. Paginating the other 235 to 2017-09 fetches
nothing -- most listed 2021+. The real experiment is 42 deep assets, and it costs ~3 minutes.

PRE-REGISTERED CONSTRUCTION -- reused VERBATIM from the prospector's 2026-07-30 pre-declaration
(docs/research/prospector_coverage.md, declared before any result was seen), so this is a LENGTH
extension of a registered test and NOT a new fork in the garden:
  per-asset signal = prem_i - prem_btc      (BTC-relative tilt; FX and venue-close terms cancel)
  per-asset target = ret_i  - ret_btc       (same Binance legs)
  harness = libs.research.axis_screen.stage_a_screen per asset, h=1, zwin=20, defaults
  aggregation = descriptive only (N, median/mean IC, share positive, verdict counts, de-contam
                pass share, sign test) -- assets are cross-correlated, so the sign test carries the
                declared caveat that the BTC-relative construct only partially removes the common
                alt factor.
  INTERPRETATION RULE, pre-declared: significantly >50% positive -> "consistent-positive, brain
  adjudication warranted"; otherwise HONEST NULL. Zero promotion authority either way (L1.6).

ALIGNMENT. Every leg is the 24:00 UTC print of its date: Upbit dailies are UTC-midnight-boundary
(libs/research/upbit_data.py, proven from Upbit's own hourly candles), Binance klines are UTC days,
and the ECB/Yahoo FX fix is ffilled -- staleness is common-mode and cancels in a BTC-relative
cross-section. This experiment is only meaningful on the corrected keying: run before R0067 it
would have paired Upbit against Binance 24h apart.

Screened per asset rather than stacked because stage_a_screen does np.roll(target,-1), which would
wrap each asset's last observation into the next asset's first.
"""
from __future__ import annotations

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

_UA = {"User-Agent": "Mozilla/5.0 (quant-desk kr-perasset)"}
_OUT = ROOT / "reports/axis_screens/kr_perasset_premium_depth.json"
_MIN_DAYS = 120          # pre-declared minimum aligned days per asset
_DEEP_CUTOFF = "2019-01-01"


def _get(url: str, timeout: int = 20):
    return json.loads(urllib.request.urlopen(
        urllib.request.Request(url, headers=_UA), timeout=timeout).read())


def deep_krw_markets() -> list[str]:
    """KRW markets with any candle before _DEEP_CUTOFF -- the only ones a depth panel can use."""
    out = []
    for m in [x["market"] for x in _get("https://api.upbit.com/v1/market/all")
              if x["market"].startswith("KRW-")]:
        try:
            if _get(f"https://api.upbit.com/v1/candles/days?market={m}"
                    f"&count=1&to={_DEEP_CUTOFF}T00:00:00Z"):
                out.append(m)
        except Exception as e:
            print(f"  depth probe failed for {m} ({e!r}) -- excluded, not assumed shallow")
        time.sleep(0.05)
    return out


def binance_daily(sym: str) -> dict[str, float]:
    """UTC-day closes, paginated. Truncation is the failure mode that never throws."""
    import datetime as dt
    out: dict[str, float] = {}
    cur = int(dt.datetime(2017, 1, 1, tzinfo=dt.UTC).timestamp() * 1000)
    end = int(time.time() * 1000)
    while cur < end:
        try:
            rows = _get(f"https://api.binance.com/api/v3/klines?symbol={sym}"
                        f"&interval=1d&startTime={cur}&limit=1000")
        except Exception:
            return {}
        if not rows:
            break
        for r in rows:
            import datetime as _d
            out[_d.datetime.fromtimestamp(int(r[0]) / 1000, tz=_d.UTC).date().isoformat()] = \
                float(r[4])
        cur = int(rows[-1][0]) + 86_400_000
        if len(rows) < 1000:
            break
        time.sleep(0.08)
    return out


def usdkrw() -> dict[str, float]:
    import datetime as dt
    res = _get("https://query1.finance.yahoo.com/v8/finance/chart/KRW=X"
               "?interval=1d&range=10y")["chart"]["result"][0]
    fx = {dt.datetime.fromtimestamp(int(t), tz=dt.UTC).date().isoformat(): float(c)
          for t, c in zip(res["timestamp"], res["indicators"]["quote"][0]["close"], strict=False)
          if c}
    # ffill across weekends/holidays: staleness is common-mode and cancels BTC-relative
    days = sorted(fx)
    full, last = {}, None
    d0 = dt.date.fromisoformat(days[0])
    for i in range((dt.date.fromisoformat(days[-1]) - d0).days + 1):
        k = (d0 + dt.timedelta(days=i)).isoformat()
        last = fx.get(k, last)
        if last:
            full[k] = last
    return full


def main() -> None:
    print("probing Upbit KRW universe for deep history...")
    deep = deep_krw_markets()
    print(f"  {len(deep)} markets with history before {_DEEP_CUTOFF}")
    if "KRW-BTC" not in deep:
        raise SystemExit("BTC reference missing -- cannot build a BTC-relative construct")

    fx = usdkrw()
    ub = {m: upbit_daily_history(m, pages=20) for m in deep}
    print(f"  upbit fetched; BTC depth {len(ub['KRW-BTC'])} days | fx {len(fx)}")

    gb: dict[str, dict[str, float]] = {}
    for m in deep:
        sym = m.replace("KRW-", "") + "USDT"
        d = binance_daily(sym)
        if len(d) >= _MIN_DAYS:
            gb[m] = d
    print(f"  binance pairs available: {len(gb)} of {len(deep)}")
    if "KRW-BTC" not in gb:
        raise SystemExit("BTCUSDT missing")

    def premium(m: str, d: str) -> float | None:
        if d in ub[m] and d in gb.get(m, {}) and d in fx:
            return ub[m][d] / fx[d] / gb[m][d] - 1.0
        return None

    btc_dates = sorted(set(ub["KRW-BTC"]) & set(gb["KRW-BTC"]) & set(fx))
    results, skipped = [], []
    for m in sorted(gb):
        if m == "KRW-BTC":
            continue
        dates = [d for d in btc_dates if premium(m, d) is not None]
        if len(dates) < _MIN_DAYS + 25:
            skipped.append((m, len(dates)))
            continue
        sig = np.array([premium(m, d) - premium("KRW-BTC", d) for d in dates])
        pi = np.array([gb[m][d] for d in dates])
        pb = np.array([gb["KRW-BTC"][d] for d in dates])
        ri, rb = np.zeros(len(pi)), np.zeros(len(pb))
        ri[1:] = pi[1:] / pi[:-1] - 1.0
        rb[1:] = pb[1:] / pb[:-1] - 1.0
        r = stage_a_screen(sig, ri - rb, name=f"kr_tilt_{m}", zwin=20, horizon_days=1)
        results.append({"market": m, "n": int(r.get("n") or 0), "days": len(dates),
                        "ic": float(r.get("ic") or 0.0),
                        "residual_ic": float(r.get("residual_ic") or 0.0),
                        "same_period_corr": float(r.get("same_period_corr") or 0.0),
                        "powered": bool(r.get("powered")), "verdict": r.get("verdict")})

    if not results:
        raise SystemExit("no asset cleared the minimum-days floor -- reporting nothing")

    ics = np.array([x["ic"] for x in results])
    res_ics = np.array([x["residual_ic"] for x in results])
    pos = int((ics > 0).sum())
    n = len(ics)
    sign_z = (pos - n / 2) / np.sqrt(n / 4)
    verdicts: dict[str, int] = {}
    for x in results:
        verdicts[x["verdict"]] = verdicts.get(x["verdict"], 0) + 1
    total_obs = int(sum(x["n"] for x in results))

    summary = {
        "experiment": "kr_perasset_premium full-depth panel (R0069 decisive experiment)",
        "construction": "pre-registered verbatim from prospector 2026-07-30; LENGTH extension",
        "keying": "same-instant, post-R0067 (Upbit UTC-midnight boundary)",
        "n_assets": n, "total_asset_days": total_obs,
        "median_ic": round(float(np.median(ics)), 4), "mean_ic": round(float(ics.mean()), 4),
        "median_residual_ic": round(float(np.median(res_ics)), 4),
        "share_positive": round(pos / n, 3), "sign_z": round(float(sign_z), 2),
        "verdicts": verdicts,
        "recent_era_comparison": {"n_assets": 175, "median_ic": 0.0050, "share_positive": 0.54,
                                  "sign_z": 0.98},
        "interpretation_rule": "pre-declared: significantly >50% positive -> brain adjudication; "
                               "else HONEST NULL. Zero promotion authority either way.",
        "per_asset": sorted(results, key=lambda x: -x["ic"]),
        "skipped_insufficient_days": skipped,
    }
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(f"\n=== FULL-DEPTH PANEL: {n} assets, {total_obs:,} asset-days ===")
    print(f"  median IC   {summary['median_ic']:+.4f}   (recent-era panel: +0.0050)")
    print(f"  mean IC     {summary['mean_ic']:+.4f}")
    print(f"  median residual IC {summary['median_residual_ic']:+.4f}")
    print(f"  share positive {pos}/{n} ({summary['share_positive']:.0%}), sign-z {sign_z:+.2f}")
    print(f"  verdicts: {verdicts}")
    print(f"  -> {'CONSISTENT-POSITIVE' if abs(sign_z) > 1.96 else 'HONEST NULL'} "
          f"(pre-declared rule)")
    print(f"  written -> {_OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

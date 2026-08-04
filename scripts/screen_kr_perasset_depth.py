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
from libs.research.cohort_independence import (  # noqa: E402
    BENCHMARK_MEAN_CORR,
    BENCHMARK_N,
    effective_bets,
)
from libs.research.upbit_data import upbit_daily_history  # noqa: E402

_UA = {"User-Agent": "Mozilla/5.0 (quant-desk kr-perasset)"}
_OUT = ROOT / "reports/axis_screens/kr_perasset_premium_depth.json"
_CACHE = ROOT / "data/kr_perasset_depth_raw.json"   # raw fetch legs; verdict is never cached
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


def _contribution_series(sig: np.ndarray, tgt: np.ndarray,
                         dates: list[str], zwin: int = 20) -> dict[str, float]:
    """Per-date IC contribution z(sig)[t] * fwd_target[t], keyed by date.

    Reproduces stage_a_screen's own convention EXACTLY -- trailing z over `zwin`, np.roll(target,-1)
    for the forward leg, and the [zwin:-1] valid window -- because the whole point is to measure the
    cross-asset dependence OF THE IC ESTIMATES the harness produced, not of some adjacent quantity.
    """
    s = np.asarray(sig, dtype="float64")
    fwd = np.roll(np.asarray(tgt, dtype="float64"), -1)
    z = np.zeros(len(s))
    for t in range(zwin, len(s)):
        w = s[t - zwin:t]
        sd = w.std()
        z[t] = (s[t] - w.mean()) / sd if sd > 0 else 0.0
    return {dates[t]: float(z[t] * fwd[t]) for t in range(zwin, len(s) - 1)}


def _panel_independence(contrib: dict[str, dict[str, float]]) -> dict:
    """How many INDEPENDENT bets is this 38-asset sign test actually made of?

    THE PRE-DECLARED CAVEAT, FINALLY MEASURED. The prospector's construction declared up front that
    "the BTC-relative construct only partially removes the common alt factor", so the naive sign
    test -- whose variance n/4 assumes n INDEPENDENT assets -- was known from the start to be an
    UPPER BOUND on significance. Computing it closes that gap rather than moving a goalpost: the
    correction can only ever make the verdict HARDER to clear, which is the safe direction, and the
    criterion itself ("significantly >50% positive") is unchanged.
    """
    markets = sorted(contrib)
    if len(markets) < 2:
        return {"status": "UNMEASURABLE: fewer than 2 assets"}

    # PAIRWISE-COMPLETE, because the panel is UNBALANCED and a global intersection is empty. The
    # first version required one common date set across all 38 and got ZERO: Upbit purges candles
    # on delisting, so several assets' windows END years before the survivors', and demanding a
    # global overlap silently reduces to the shortest dead asset. (It reported UNMEASURABLE rather
    # than a number, which is the behaviour that made this fixable -- an estimator that had
    # returned 0.0 for "no overlap" would have printed n_eff = n and read as full independence,
    # the most flattering possible answer.)
    common_min = 60
    corrs: list[float] = []
    pairs_skipped = 0
    for i in range(len(markets)):
        for j in range(i + 1, len(markets)):
            a, b = contrib[markets[i]], contrib[markets[j]]
            shared = sorted(set(a) & set(b))
            if len(shared) < common_min:
                pairs_skipped += 1
                continue
            va = np.array([a[d] for d in shared])
            vb = np.array([b[d] for d in shared])
            if va.std() == 0 or vb.std() == 0:
                pairs_skipped += 1
                continue
            corrs.append(float(np.corrcoef(va, vb)[0, 1]))
    if len(corrs) < 10:
        return {"status": f"UNMEASURABLE: only {len(corrs)} usable pairs "
                          f"({pairs_skipped} skipped for <{common_min} shared dates)"}
    mean_corr = float(np.mean(corrs))
    n_eff = effective_bets(len(markets), mean_corr)
    return {"status": "measured", "n_assets": len(markets),
            "n_pairs_used": len(corrs), "n_pairs_skipped": pairs_skipped,
            "mean_pairwise_corr": round(mean_corr, 4),
            "n_eff": round(float(n_eff), 2),
            "benchmark_101_alphas_n_eff": round(effective_bets(BENCHMARK_N,
                                                               BENCHMARK_MEAN_CORR), 2)}


def main() -> None:
    # CACHE THE FETCH, NOT THE VERDICT. The network leg costs ~25 minutes (277 Upbit depth probes
    # plus paginated Binance history per asset); the analysis costs seconds. Caching the raw legs
    # means an adjudication can be re-derived -- a corrected estimator, a different horizon -- for
    # free, instead of the re-run cost silently discouraging the re-analysis. Delete the file to
    # refetch. The VERDICT is never cached: it is always recomputed from the raw legs.
    if _CACHE.exists():
        print(f"using cached fetch {_CACHE.relative_to(ROOT)} (delete it to refetch)")
        raw = json.loads(_CACHE.read_text("utf-8"))
        fx, ub, gb = raw["fx"], raw["ub"], raw["gb"]
        print(f"  {len(gb)} binance-paired markets | BTC depth {len(ub['KRW-BTC'])} days")
    else:
        print("probing Upbit KRW universe for deep history...")
        deep = deep_krw_markets()
        print(f"  {len(deep)} markets with history before {_DEEP_CUTOFF}")
        if "KRW-BTC" not in deep:
            raise SystemExit("BTC reference missing -- cannot build a BTC-relative construct")

        fx = usdkrw()
        ub = {m: upbit_daily_history(m, pages=20) for m in deep}
        print(f"  upbit fetched; BTC depth {len(ub['KRW-BTC'])} days | fx {len(fx)}")

        gb = {}
        for m in deep:
            sym = m.replace("KRW-", "") + "USDT"
            d = binance_daily(sym)
            if len(d) >= _MIN_DAYS:
                gb[m] = d
        print(f"  binance pairs available: {len(gb)} of {len(deep)}")
        _CACHE.parent.mkdir(parents=True, exist_ok=True)
        _CACHE.write_text(json.dumps({"fx": fx, "ub": ub, "gb": gb}), encoding="utf-8")
        print(f"  raw legs cached -> {_CACHE.relative_to(ROOT)}")
    if "KRW-BTC" not in gb:
        raise SystemExit("BTCUSDT missing")

    def premium(m: str, d: str) -> float | None:
        if d in ub[m] and d in gb.get(m, {}) and d in fx:
            return ub[m][d] / fx[d] / gb[m][d] - 1.0
        return None

    btc_dates = sorted(set(ub["KRW-BTC"]) & set(gb["KRW-BTC"]) & set(fx))
    results, skipped = [], []
    contrib: dict[str, dict[str, float]] = {}
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
        contrib[m] = _contribution_series(sig, ri - rb, dates)

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

    indep = _panel_independence(contrib)
    n_eff = indep.get("n_eff")
    # The sign test's variance is n/4 under INDEPENDENCE. With n_eff independent assets the
    # statistic carries only sqrt(n_eff/n) of the resolution the naive z claims.
    sign_z_eff = (float(sign_z) * np.sqrt(n_eff / n)) if n_eff else None
    decisive_z = sign_z_eff if sign_z_eff is not None else float(sign_z)
    consistent = abs(decisive_z) > 1.96

    summary = {
        "experiment": "kr_perasset_premium full-depth panel (R0069 decisive experiment)",
        "construction": "pre-registered verbatim from prospector 2026-07-30; LENGTH extension",
        "keying": "same-instant, post-R0067 (Upbit UTC-midnight boundary)",
        "n_assets": n, "total_asset_days": total_obs,
        "median_ic": round(float(np.median(ics)), 4), "mean_ic": round(float(ics.mean()), 4),
        "median_residual_ic": round(float(np.median(res_ics)), 4),
        "share_positive": round(pos / n, 3), "sign_z": round(float(sign_z), 2),
        "independence": indep,
        "sign_z_effective": (round(float(sign_z_eff), 2) if sign_z_eff is not None else None),
        "sign_z_note": ("naive sign_z assumes n INDEPENDENT assets; the construction pre-declared "
                        "that BTC-relativisation only partially removes the common alt factor, so "
                        "the naive value is an UPPER BOUND. The effective z is the decisive one."),
        "verdict_overall": ("CONSISTENT-POSITIVE" if consistent else "HONEST NULL"),
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
    print(f"  independence: {indep}")
    if sign_z_eff is not None:
        print(f"  sign-z at n_eff={n_eff}: {sign_z_eff:+.2f}  <- the decisive statistic")
    else:
        print("  n_eff UNMEASURABLE -- falling back to the naive z, which OVERSTATES significance")
    print(f"  verdicts: {verdicts}")
    print(f"  -> {summary['verdict_overall']} (pre-declared rule, on the effective z)")
    print(f"  written -> {_OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

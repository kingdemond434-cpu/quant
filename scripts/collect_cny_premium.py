#!/usr/bin/env python3
"""USDT/CNY P2P premium collector -- the mainland capital-flow proxy (ledger #76, unparked
2026-07-24 with principal approval; the clean free source now exists and is live-verified).

CONSTRUCTION (owned methodology, free-first doctrine):
    p2p   = median of the top-10 OKX P2P merchant SELL-side USDT quotes in CNY (public, keyless,
            190 rows live-verified from this box)
    fx    = official USD/CNY (open.er-api.com, free, daily UTC update; frankfurter 403s here)
    premium = p2p / fx - 1
Mechanism: China's capital controls (total crypto ban + 50k USD/yr FX quota) make P2P USDT the
ONLY retail on-ramp -- the premium prices capital-control pressure, the direct CN analog of
kimchi (KRW). Live at build time: p2p ~6.74 vs fx 6.7815 -> -0.6%, a realistic magnitude.

HONESTY GATES, pre-registered up front:
  * NO Stage-A screen -- P2P quotes have no free history, so there is nothing to screen. This is
    a FORWARD-ONLY clock from day 1; z20 is written null until 20 real observations exist (the
    shadow evaluator skips null-z rows, so the stats never contain manufactured zeros).
  * DIRECTION pre-registered NOW, from mechanism only (peek-safe): +1, mirroring kimchi -- the
    one SURVIVING member of this construct family -- premium z-up = mainland demand surge =
    short-horizon momentum. Chosen before any forward return exists; never re-fit.
  * THE TRY FALSIFIER (graveyard: try_premium_timing KILLED the best previous kimchi-analog --
    "kimchi is RARE, not a generic regional-premium pattern"): if the 30-day premium std lands
    TRY-class (<0.3%) rather than KRW-class (1.4%), the axis is expected to read FAILING and
    will be retired by the Holm bar. Logged here so success cannot be quietly redefined.
  * No candle timestamps exist (live quotes sampled at collection time) -> the bithumb
    timezone-lookahead class is structurally impossible here.

Zero promotion authority: the forward clock under the Holm bar decides. stdlib only.
"""
from __future__ import annotations

import json
import statistics
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

_P2P = ("https://www.okx.com/v3/c2c/tradingOrders/books?t=1&quoteCurrency=CNY"
        "&baseCurrency=USDT&side=sell&paymentMethod=all&userType=all&showTrade=false"
        "&showFollow=false&showAlreadyTraded=false&isAbleFilter=false&pageIndex=1&pageSize=10")
_FX = "https://open.er-api.com/v6/latest/USD"
_SERIES = Path("data/cny_premium.jsonl")


def _get(url: str) -> object:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (quant-cny)"})
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.loads(r.read().decode())


def main() -> None:
    d = _get(_P2P)
    rows = (d.get("data", {}) or {}).get("sell", []) or []
    prices = []
    for r in rows[:10]:
        try:
            prices.append(float(r["price"]))
        except Exception:
            continue
    if len(prices) < 5:
        raise SystemExit(f"P2P fetch thin: {len(prices)} quotes -- not writing a weak point")
    p2p = statistics.median(prices)

    fx_d = _get(_FX)
    fx = float((fx_d.get("rates") or {}).get("CNY", 0.0))
    if fx <= 0:
        raise SystemExit("FX fetch failed -- not writing")

    premium = p2p / fx - 1.0

    # z20 from the accruing series itself; null until 20 real observations exist
    hist = []
    if _SERIES.exists():
        for ln in _SERIES.read_text("utf-8").splitlines():
            try:
                hist.append(json.loads(ln))
            except Exception:
                continue
    prem_hist = [float(h["premium"]) for h in hist if h.get("premium") is not None]
    z20 = None
    if len(prem_hist) >= 20:
        w = prem_hist[-20:]
        sd = statistics.pstdev(w)
        z20 = round((premium - statistics.fmean(w)) / sd, 3) if sd > 0 else 0.0

    today = datetime.now(tz=UTC).date().isoformat()
    if hist and hist[-1].get("date") == today:
        print(f"cny-premium: {today} already recorded")
        return
    rec = {"date": today, "p2p_cny": round(p2p, 4), "fx_cny": round(fx, 4),
           "premium": round(premium, 5), "z20": z20, "n_quotes": len(prices)}
    with _SERIES.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")

    n = len(prem_hist) + 1
    std30 = statistics.pstdev([*prem_hist[-30:], premium]) if n >= 10 else None
    print(f"CNY-PREMIUM  {today}  p2p {p2p:.4f} vs fx {fx:.4f} -> {premium*100:+.2f}%  "
          f"(z20 {z20 if z20 is not None else 'null until n>=20'}; n={n})")
    if std30 is not None:
        verdict = "KRW-class (fat, promising)" if std30 > 0.006 else \
                  "TRY-class WARNING (thin -- expect FAILING per pre-registered falsifier)" \
                  if std30 < 0.003 else "intermediate"
        print(f"  30d premium std {std30*100:.2f}% -> {verdict}")


if __name__ == "__main__":
    main()

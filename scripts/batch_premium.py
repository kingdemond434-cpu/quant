"""Batch regional-venue-premium screen -- test many at once through the axis_screen harness.

Each venue: local BTC price at official FX vs Binance BTCUSDT = the regional premium (kimchi class).
Runs the de-contamination gate on every one; keeps only survivors, persists their forward clocks.
Free public APIs. Run from repo root.
"""
from __future__ import annotations

import json
import time
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from libs.research.axis_screen import stage_a_screen


def _get(url: str, hdr: dict | None = None):
    req = urllib.request.Request(url, headers=hdr or {"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.loads(r.read().decode())


def _binance() -> dict[str, float]:
    rows = _get("https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1d&limit=300")
    return {datetime.fromtimestamp(int(r[0]) / 1000, tz=UTC).date().isoformat(): float(r[4])
            for r in rows}


def _yahoo(sym: str) -> dict[str, float]:
    r = _get(f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?interval=1d&range=300d")
    res = r["chart"]["result"][0]
    return {datetime.fromtimestamp(int(t), tz=UTC).date().isoformat(): float(c)
            for t, c in zip(res["timestamp"], res["indicators"]["quote"][0]["close"]) if c}


# --- per-venue local-price fetchers (return {date: local_currency_price}) -------------------
def bithumb() -> dict[str, float]:  # Korea KRW
    d = _get("https://api.bithumb.com/public/candlestick/BTC_KRW/24h")["data"]
    return {datetime.fromtimestamp(int(r[0]) / 1000, tz=UTC).date().isoformat(): float(r[2])
            for r in d}


def coinone() -> dict[str, float]:  # Korea KRW
    d = _get("https://api.coinone.co.kr/public/v2/chart/KRW/BTC?interval=1d&size=300")
    rows = d.get("chart") or d.get("data") or []
    return {datetime.fromtimestamp(int(r["timestamp"]) / 1000, tz=UTC).date().isoformat():
            float(r["close"]) for r in rows}


def bitbank() -> dict[str, float]:  # Japan JPY
    out: dict[str, float] = {}
    for yr in (datetime.now(UTC).year, datetime.now(UTC).year - 1):
        try:
            d = _get(f"https://public.bitbank.cc/btc_jpy/candlestick/1day/{yr}")
            cs = d["data"]["candlestick"][0]["ohlcv"]
            for r in cs:
                out[datetime.fromtimestamp(int(r[5]) / 1000, tz=UTC).date().isoformat()] = float(r[3])
        except Exception as e:  # noqa: BLE001
            print(f"    bitbank {yr}: {type(e).__name__}")
    return out


def mercado() -> dict[str, float]:  # Brazil BRL
    now = int(time.time()); frm = now - 300 * 86400
    d = _get(f"https://api.mercadobitcoin.net/api/v4/candles?symbol=BTC-BRL&resolution=1d"
             f"&from={frm}&to={now}")
    return {datetime.fromtimestamp(int(t), tz=UTC).date().isoformat(): float(c)
            for t, c in zip(d["t"], d["c"])}


VENUES = [("bithumb_KR", bithumb, "KRW=X"), ("coinone_KR", coinone, "KRW=X"),
          ("bitbank_JP", bitbank, "JPY=X"), ("mercado_BR", mercado, "BRL=X")]


def main() -> None:
    gb = _binance()
    fxc: dict[str, dict[str, float]] = {}
    results = []
    for name, fetch, fxsym in VENUES:
        try:
            local = fetch()
        except Exception as e:  # noqa: BLE001
            print(f"{name:14s} DATA-BLOCKED ({type(e).__name__})")
            continue
        if not local:
            print(f"{name:14s} DATA-BLOCKED (empty)")
            continue
        if fxsym not in fxc:
            fxc[fxsym] = _yahoo(fxsym)
        fx = fxc[fxsym]
        dates = sorted(set(local) & set(gb) & set(fx))
        if len(dates) < 60:
            print(f"{name:14s} thin ({len(dates)}d)")
            continue
        prem = np.array([local[d] / fx[d] / gb[d] - 1.0 for d in dates])
        btc = np.array([gb[d] for d in dates])
        ret = np.zeros(len(btc)); ret[1:] = btc[1:] / btc[:-1] - 1.0
        r = stage_a_screen(prem, ret, name=name)   # pure screen -- no clock (screens don't pre-register)
        r["premium_std_pct"] = round(float(prem.std() * 100), 3)
        results.append(r)
        print(f"{name:14s} {len(dates)}d | std {r['premium_std_pct']}% | IC {r.get('ic')} | "
              f"same {r.get('same_period_corr')} | resid {r.get('residual_ic')} | "
              f"momSh {r.get('sharpe_momentum')} | {r['verdict']}")

    Path("data/batch_premium_screen.json").write_text(
        json.dumps({"updated": datetime.now(tz=UTC).isoformat(), "results": results}, indent=1),
        "utf-8")
    surv = [r["name"] for r in results if r["verdict"] == "SCREEN-INTERESTING"]
    print(f"\nSURVIVORS (passed de-contam): {surv or 'NONE'}")


if __name__ == "__main__":
    main()

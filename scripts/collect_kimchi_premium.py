"""Kimchi-premium collector + Stage-A screen (gap #74). Free no-key Upbit + Binance.

Premium is computed USDT-DENOMINATED to avoid needing an FX feed:
    upbit_btc_usdt = Upbit KRW-BTC / Upbit KRW-USDT      (BTC priced in USDT on the Korean venue)
    kimchi = upbit_btc_usdt / Binance BTCUSDT - 1          (Korean vs global, both in USDT)

Stage-A SCREEN ONLY (two-stage law): computes honest in-sample IC + timing Sharpe for both the
momentum and reversal readings, has ZERO promotion authority, and writes the premium series to
data/kimchi_premium.jsonl so a FORWARD clock accrues from today. Promotion needs the forward
gauntlet like anything else. Pure stdlib + numpy. Run from repo root.
"""
from __future__ import annotations

import json
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

_UPBIT = "https://api.upbit.com/v1/candles/days"
_BINANCE = "https://api.binance.com/api/v3/klines"
_YF = "https://query1.finance.yahoo.com/v8/finance/chart/KRW=X?interval=1d&range=250d"
_SERIES = Path("data/kimchi_premium.jsonl")


def _get(url: str) -> object:
    req = urllib.request.Request(url, headers={"User-Agent": "quant-kimchi"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode())


def _upbit_daily(market: str, n: int = 200) -> dict[str, float]:
    rows = _get(f"{_UPBIT}?market={market}&count={n}")
    if not isinstance(rows, list):
        return {}
    return {str(r["candle_date_time_utc"])[:10]: float(r["trade_price"]) for r in rows}


def _binance_daily(sym: str, n: int = 200) -> dict[str, float]:
    rows = _get(f"{_BINANCE}?symbol={sym}&interval=1d&limit={n}")
    if not isinstance(rows, list):
        return {}
    out = {}
    for r in rows:
        d = datetime.fromtimestamp(int(r[0]) / 1000, tz=UTC).date().isoformat()
        out[d] = float(r[4])
    return out


def _yahoo_usdkrw() -> dict[str, float]:
    import datetime as _dt
    r = _get(_YF)
    res = r["chart"]["result"][0]
    ts, cl = res["timestamp"], res["indicators"]["quote"][0]["close"]
    return {_dt.datetime.fromtimestamp(int(t), tz=UTC).date().isoformat(): float(c)
            for t, c in zip(ts, cl) if c}


def main() -> None:
    kbtc = _upbit_daily("KRW-BTC")
    gbtc = _binance_daily("BTCUSDT")
    fx = _yahoo_usdkrw()                          # official USD/KRW -- carries the real premium
    if not (kbtc and gbtc and fx):
        raise SystemExit(f"fetch failed: upbit={len(kbtc)} binance={len(gbtc)} fx={len(fx)}")
    dates = sorted(set(kbtc) & set(gbtc) & set(fx))
    if len(dates) < 60:
        raise SystemExit(f"only {len(dates)} aligned days")

    prem, btc = [], []
    for d in dates:
        upbit_btc_usd = kbtc[d] / fx[d]           # KRW-BTC at OFFICIAL FX = USD price on Upbit
        prem.append(upbit_btc_usd / gbtc[d] - 1.0)
        btc.append(gbtc[d])
    prem = np.array(prem)
    btc = np.array(btc)
    ret = np.zeros(len(btc))
    ret[1:] = btc[1:] / btc[:-1] - 1.0
    fwd = np.roll(ret, -1)                       # next-day BTC return (no lookahead)

    # signal = 20d z-score of the premium
    z = np.zeros(len(prem))
    for t in range(20, len(prem)):
        w = prem[t - 20:t]
        sd = w.std()
        z[t] = (prem[t] - w.mean()) / sd if sd > 0 else 0.0
    valid = slice(20, len(prem) - 1)             # drop warmup + last (no fwd)
    zv, fv = z[valid], fwd[valid]

    ic = float(np.corrcoef(zv, fv)[0, 1]) if zv.std() and fv.std() else 0.0
    # timing Sharpes: momentum = trade WITH z, reversal = trade AGAINST z
    def _sh(sig: np.ndarray) -> float:
        r = np.sign(sig) * fv
        return round(float(r.mean() / r.std() * np.sqrt(365)), 2) if r.std() else 0.0
    sh_mom, sh_rev = _sh(zv), _sh(-zv)

    # current premium level + persist for the forward clock
    today = datetime.now(tz=UTC).date().isoformat()
    rec = {"date": today, "premium": round(float(prem[-1]), 5),
           "z20": round(float(z[-1]), 3), "n_hist": len(dates)}
    prev = _SERIES.read_text("utf-8").strip().splitlines() if _SERIES.exists() else []
    if not prev or json.loads(prev[-1]).get("date") != today:
        with _SERIES.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec) + "\n")

    print(f"KIMCHI SCREEN | {len(dates)} aligned days")
    print(f"  current premium: {prem[-1] * 100:+.2f}%   z20: {z[-1]:+.2f}")
    print(f"  premium range: {prem.min() * 100:+.2f}% .. {prem.max() * 100:+.2f}%  "
          f"(mean {prem.mean() * 100:+.2f}%, std {prem.std() * 100:.2f}%)")
    print(f"  IC(z20, next-day BTC ret): {ic:+.4f}")
    print(f"  timing Sharpe -- MOMENTUM: {sh_mom}   REVERSAL: {sh_rev}")
    verdict = ("SCREEN-INTERESTING -> pre-register a forward clock"
               if max(abs(sh_mom), abs(sh_rev)) > 0.5 and abs(ic) > 0.03
               else "SCREEN-WEAK -> graveyard the timing form; premium level may still be a "
                    "conditioning feature (log, do not promote)")
    print(f"  VERDICT (Stage-A, zero promotion authority): {verdict}")


if __name__ == "__main__":
    main()

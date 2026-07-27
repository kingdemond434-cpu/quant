"""LIVE-CLOCK RE-VALIDATION against the rails added 2026-07-23..27.

Every currently-tracked axis was screened BEFORE some of these controls existed. A signal that
passed a weaker gate is not validated -- it is unexamined. This re-runs each LIVE axis through:
  1. the hardened harness (de-contamination + SUSPECT-LOOKAHEAD plausibility rail)
  2. the SHIFT-SENSITIVITY test that killed bithumb_KR (timezone/candle-label lookahead): a genuine
     leading signal degrades smoothly under a +/-1 day shift; a lookahead artifact keeps or peaks
     its IC when the signal is shifted FORWARD (i.e. it already contained future price).
KIMCHI IS THE PRIORITY: it uses Upbit daily candles, and bithumb -- another KRW venue -- died of
exactly this (KST day-open timestamps sat ~1.6d ahead of Binance UTC closes).
Read-only diagnostic. Run from repo root."""
from __future__ import annotations

import json
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from libs.research.axis_screen import stage_a_screen


def _get(url, timeout=35):
    req = urllib.request.Request(url, headers={"User-Agent": "quant-reval/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def binance(sym="BTCUSDT", n=900):
    rows = _get(f"https://api.binance.com/api/v3/klines?symbol={sym}&interval=1d&limit={n}")
    return {datetime.fromtimestamp(int(r[0]) / 1000, tz=UTC).date().isoformat(): float(r[4])
            for r in rows}


def yahoo(sym):
    r = _get(f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?interval=1d&range=300d")
    res = r["chart"]["result"][0]
    return {datetime.fromtimestamp(int(t), tz=UTC).date().isoformat(): float(c)
            for t, c in zip(res["timestamp"], res["indicators"]["quote"][0]["close"], strict=False) if c}


def upbit():
    rows = _get("https://api.upbit.com/v1/candles/days?market=KRW-BTC&count=200")
    return {str(r["candle_date_time_utc"])[:10]: float(r["trade_price"]) for r in rows}


def stablesupply():
    d = _get("https://stablecoins.llama.fi/stablecoincharts/all")
    out = {}
    for x in d:
        v = x.get("totalCirculatingUSD") or {}
        p = v.get("peggedUSD") if isinstance(v, dict) else None
        if p is not None:
            out[datetime.fromtimestamp(int(x["date"]), tz=UTC).date().isoformat()] = float(p)
    return out


def shift_ic(signal: dict, gb: dict, shift: int, fx: dict | None = None) -> float:
    """IC of z(signal shifted by `shift` days) vs NEXT-day return."""
    dates = sorted(set(signal) & set(gb) & (set(fx) if fx else set(gb)))
    if len(dates) < 60:
        return float("nan")
    {d: i for i, d in enumerate(dates)}
    btc = np.array([gb[d] for d in dates])
    ret = np.zeros(len(btc)); ret[1:] = btc[1:] / btc[:-1] - 1.0
    fwd = np.roll(ret, -1)
    sig, rr = [], []
    for i, d in enumerate(dates):
        j = i + shift
        if 0 <= j < len(dates):
            dj = dates[j]
            v = signal[dj] / fx[d] / gb[d] - 1.0 if fx else signal[dj]
            sig.append(v); rr.append(fwd[i])
    sig, rr = np.array(sig, float), np.array(rr, float)
    z = np.zeros(len(sig))
    for t in range(20, len(sig)):
        w = sig[t - 20:t]; sd = w.std()
        z[t] = (sig[t] - w.mean()) / sd if sd > 0 else 0.0
    zv, fv = z[20:-1], rr[20:-1]
    return float(np.corrcoef(zv, fv)[0, 1]) if zv.std() and fv.std() else 0.0


def main() -> None:
    gb = binance()
    print("=== LIVE CLOCK RE-VALIDATION (hardened harness + shift test) ===\n")

    # ---- 1. KIMCHI (highest risk: KRW venue, same class as the bithumb lookahead kill) ----
    try:
        kb, fx = upbit(), yahoo("KRW=X")
        dates = sorted(set(kb) & set(gb) & set(fx))
        prem = np.array([kb[d] / fx[d] / gb[d] - 1.0 for d in dates])
        btc = np.array([gb[d] for d in dates])
        ret = np.zeros(len(btc)); ret[1:] = btc[1:] / btc[:-1] - 1.0
        r = stage_a_screen(prem, ret, name="kimchi_premium", zwin=20)
        s = {k: shift_ic(kb, gb, k, fx) for k in (-1, 0, 1)}
        print(f"KIMCHI n={len(dates)} | IC {r.get('ic'):+.4f} same {r.get('same_period_corr'):+.3f} "
              f"resid {r.get('residual_ic'):+.4f} | {r['verdict']}")
        print(f"  SHIFT TEST  -1d {s[-1]:+.3f} | 0d {s[0]:+.3f} | +1d {s[1]:+.3f}")
        fwd_leak = abs(s[1]) > abs(s[0]) * 1.5 and abs(s[1]) > 0.3
        print(f"  -> {'*** FORWARD-SHIFT LEAK SUSPECTED ***' if fwd_leak else 'no lookahead pattern (shift0 not dominated by +1d)'}\n")
    except Exception as e:
        print(f"KIMCHI: ERROR {type(e).__name__}: {e}\n")

    # ---- 2. STABLECOIN SUPPLY ----
    try:
        sup = stablesupply()
        dates = sorted(set(sup) & set(gb))
        sig = np.array([sup[d] for d in dates])
        btc = np.array([gb[d] for d in dates])
        ret = np.zeros(len(btc)); ret[1:] = btc[1:] / btc[:-1] - 1.0
        r = stage_a_screen(sig, ret, name="stablecoin_supply", zwin=20)
        s = {k: shift_ic(sup, gb, k) for k in (-1, 0, 1)}
        print(f"STABLECOIN SUPPLY n={len(dates)} | IC {r.get('ic'):+.4f} "
              f"same {r.get('same_period_corr'):+.3f} resid {r.get('residual_ic'):+.4f} | {r['verdict']}")
        print(f"  SHIFT TEST  -1d {s[-1]:+.3f} | 0d {s[0]:+.3f} | +1d {s[1]:+.3f}")
        print(f"  -> {'*** FORWARD-SHIFT LEAK SUSPECTED ***' if abs(s[1])>abs(s[0])*1.5 and abs(s[1])>0.3 else 'no lookahead pattern'}\n")
    except Exception as e:
        print(f"STABLECOIN: ERROR {type(e).__name__}\n")

    # ---- 3. CNY premium clock health ----
    p = Path("data/cny_premium.jsonl")
    if p.exists():
        rows = [json.loads(x) for x in p.read_text("utf-8").splitlines() if x.strip()]
        nz = [r for r in rows if r.get("z20") is not None]
        print(f"CNY PREMIUM clock: {len(rows)} rows, {len(nz)} with usable z20 "
              f"(needs ~20 for warmup)")
        print(f"  -> {'ACCRUING but z still null -- forward evidence has NOT started' if not nz else 'z live'}\n")

    # ---- 4. clock row counts (is forward evidence actually accruing?) ----
    print("=== FORWARD CLOCK ACCRUAL (are rows landing daily?) ===")
    for f in ("kimchi_premium", "stablecoin_supply", "cny_premium", "onchain_activity"):
        fp = Path(f"data/{f}.jsonl")
        if fp.exists():
            rows = [json.loads(x) for x in fp.read_text("utf-8").splitlines() if x.strip()]
            ds = sorted({r.get("date") for r in rows if r.get("date")})
            print(f"  {f:22s} rows={len(rows):3d} span {ds[0] if ds else '-'} .. {ds[-1] if ds else '-'}")
        else:
            print(f"  {f:22s} MISSING")


if __name__ == "__main__":
    main()

"""LIVE OI / LONG-SHORT COLLECTOR -- the desk's best mechanism has been running on 2023 data.

THE FINDING THAT MOTIVATED THIS. data/oi_ls_history.jsonl ends 2023-12-03. It is a static backfill
written once by dl_metrics_history.py for OOS backtesting -- correct as an archive, useless as a
live feed. Meanwhile M_FORCED_DELEVERAGE is the desk's BEST-supported mechanism (2/10 survival,
highest of nine) and holds its ONLY confirmed edge (funding persistence, IC +0.432, t +29.7).

So the mechanism with the strongest evidence has had no live positioning data at all. Binance
publishes both feeds free, no key: openInterestHist and globalLongShortAccountRatio.

MECHANISM, falsifiable as stated:
    crowded positioning -> one side pays funding -> adverse move squeezes the crowd ->
    forced unwind -> the squeeze that positioning predicted
Forced participant: the leveraged crowd. Constraint: margin, which cannot be negotiated or timed.
Why not arbitraged: the data is public but the CONSTRAINT is real -- knowing a crowd is levered
does not let you avoid being the crowd.

UNIVERSE IS THE VIABLE SET, NOT THE FUNDING-RANKED SET. Only symbols whose MEASURED round-trip
lets a carry clear costs (carry_viability: 16 of 30) are collected. Collecting positioning on
COOKIEUSDT -- 130.47bps round-trip against 6.7bps of funding -- would be gathering evidence about
a trade that can never be profitable. The universe switch already applied this to trading; this
applies it to research.

DEFENCES (identical pattern to collect_defi_lending, deliberately):
  schema contract -> quarantine, sanity bounds per row, coverage floor, separate heartbeat.
"""
from __future__ import annotations

import json
import ssl
import time
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data/oi_ls_live.jsonl"
HB = ROOT / "data/oi_ls_live_heartbeat"
QUAR = ROOT / "data/oi_ls_live_quarantine.json"
COST = ROOT / "data/cost_model.json"
CTX = ssl.create_default_context()
BASE = "https://fapi.binance.com/futures/data"

PERIOD = "1h"
_MIN_SYMBOLS = 8
_MAX_VIABLE_RT_BPS = 8.0        # matches carry_viability: clears at <=3bp funding over a 24h hold
_FALLBACK = ("BTCUSDT", "ETHUSDT", "BNBUSDT", "XRPUSDT", "SOLUSDT", "DOGEUSDT",
             "AVAXUSDT", "LINKUSDT", "LTCUSDT", "TRXUSDT")


def _get(path: str, params: str):
    r = urllib.request.Request(f"{BASE}/{path}?{params}",
                               headers={"User-Agent": "quant-desk/1.0"})
    return json.loads(urllib.request.urlopen(r, timeout=45, context=CTX).read())


def _viable_universe() -> list[str]:
    """Symbols whose MEASURED round-trip can clear ordinary funding. Never the funding ranking."""
    try:
        cm = json.loads(COST.read_text("utf-8"))["symbols"]
    except Exception:  # blind-except intentional (BLE001)
        return list(_FALLBACK)
    out = []
    for sym, d in cm.items():
        try:
            v = d["pair"]["500"].get("pair_roundtrip_bps")
            if v is not None and float(v) <= _MAX_VIABLE_RT_BPS:
                out.append(sym)
        except (KeyError, TypeError, ValueError):
            continue
    return sorted(out) or list(_FALLBACK)


def _quarantine(reason: str, detail: dict) -> None:
    QUAR.write_text(json.dumps({"ts": datetime.now(tz=UTC).isoformat(), "reason": reason,
                                **detail}, indent=1), "utf-8")
    print(f"  QUARANTINED: {reason}")
    print("  Nothing written. Wrong data is trusted downstream and fails silently;")
    print("  a stopped collector at least announces itself.")


def main() -> None:
    ts = datetime.now(tz=UTC)
    print("=== LIVE OI / LONG-SHORT COLLECTOR -- M_FORCED_DELEVERAGE ===")
    print("    data/oi_ls_history.jsonl ends 2023-12-03 (static archive). The desk's")
    print("    best-supported mechanism has had NO live positioning feed.\n")
    universe = _viable_universe()
    print(f"  universe: {len(universe)} symbols with measured round-trip "
          f"<= {_MAX_VIABLE_RT_BPS}bps (viable set, not funding-ranked)")

    rows, failed = [], []
    for sym in universe:
        try:
            oi = _get("openInterestHist", f"symbol={sym}&period={PERIOD}&limit=1")
            ls = _get("globalLongShortAccountRatio", f"symbol={sym}&period={PERIOD}&limit=1")
            tk = _get("takerlongshortRatio", f"symbol={sym}&period={PERIOD}&limit=1")
            if not oi or not ls:
                failed.append(sym)
                continue
            o, lrow = oi[-1], ls[-1]
            t = tk[-1] if tk else {}
            lsr = float(lrow["longShortRatio"])
            la = float(lrow["longAccount"])
            # sanity: ratio and account share must be internally consistent and bounded
            if not (0.01 < lsr < 100.0 and 0.0 < la < 1.0):
                failed.append(sym)
                continue
            rows.append({
                "ts": ts.isoformat(), "symbol": sym, "period": PERIOD,
                "oi_contracts": float(o["sumOpenInterest"]),
                "oi_usd": float(o["sumOpenInterestValue"]),
                "long_short_ratio": lsr, "long_account": la,
                "short_account": float(lrow["shortAccount"]),
                "taker_buy_sell_ratio": float(t.get("buySellRatio", 0)) or None,
                "src_ts": int(o["timestamp"])})
            time.sleep(0.12)                      # courteous to a free public endpoint
        except Exception:  # blind-except intentional (BLE001)
            failed.append(sym)

    if len(rows) < _MIN_SYMBOLS:
        _quarantine("coverage below floor", {"collected": len(rows), "floor": _MIN_SYMBOLS,
                                             "failed": failed})
        raise SystemExit(1)

    with OUT.open("a", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")
    HB.write_text(f"{ts.isoformat()} symbols={len(rows)}", "utf-8")
    if QUAR.exists():
        QUAR.unlink()

    tot_oi = sum(r["oi_usd"] for r in rows)
    crowd = sorted(rows, key=lambda r: -abs(r["long_short_ratio"] - 1.0))[:6]
    print(f"  collected {len(rows)}/{len(universe)}  failed={failed or 'none'}")
    print(f"  aggregate open interest ${tot_oi/1e9:.2f}bn\n")
    print(f"  {'symbol':<12}{'L/S ratio':>11}{'long%':>8}{'OI $m':>10}{'taker b/s':>11}")
    for r in crowd:
        print(f"  {r['symbol']:<12}{r['long_short_ratio']:>11.3f}{r['long_account']*100:>7.1f}%"
              f"{r['oi_usd']/1e6:>10.0f}{(r['taker_buy_sell_ratio'] or 0):>11.3f}")
    print("\n  CROWDING IS THE OBSERVABLE, NOT THE ALPHA. A ratio far from 1.0 marks where one")
    print("  side is levered and therefore squeezable. Whether that predicts anything net of")
    print("  cost is a Stage-A question this only feeds -- and the same construction died as a")
    print("  standalone signal before, so it earns a forward clock only in combination.")
    print(f"\n  -> {OUT}  (heartbeat {HB.name})")


if __name__ == "__main__":
    main()

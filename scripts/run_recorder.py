"""DATA-MOAT RECORDER v1 -- the desk's only permanently unrecoverable asset (gap #18).

Principal EXECUTION LOCKDOWN directive 2026-07-18: priority #1. Records LIVE Binance
USD-M futures microstructure (the venue class the desk trades) for the top-5 liquid
perps: top-20 order book at ~1s cadence + every aggTrade. Purpose: pre-live TCA and
execution research (name-level slippage curves, depth dynamics, cascade context), and a
compounding proprietary research asset -- every hour not recorded is gone forever.

v1 design (deliberately boring): REST polling, stdlib-only, gzip-jsonl hourly partitions
under data/moat/fut/{symbol}/. ~40-70 MB/day compressed for 5 symbols; disk-guarded at 80%.
No trading imports, no keys, no writes outside data/moat/ + its heartbeat -- this process
CANNOT touch the book. Upgrade path (brain, per spec-prebuild): websocket diffs + parquet.

Runs detached (setsid); liveness = data/recorder_heartbeat (alerted >10min stale);
scripts/ensure_recorder.py respawns it from the daily cycle.

    python scripts/run_recorder.py
"""

from __future__ import annotations

import contextlib
import gzip
import json
import shutil
import time
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

_BASE = "https://fapi.binance.com"                 # LIVE public market data (read-only)
_SYMBOLS = ("BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT",
            "DOGEUSDT", "ADAUSDT", "AVAXUSDT", "LINKUSDT", "LTCUSDT",
            "TRXUSDT", "DOTUSDT", "BCHUSDT", "NEARUSDT", "SUIUSDT",
            "UNIUSDT", "APTUSDT", "FILUSDT", "ARBUSDT", "OPUSDT")
# 5 -> 20 (principal max order, 2026-07-21): every unrecorded day is unrecoverable;
# disk math: ~33MB/day at 5 syms -> ~130MB/day at 20 -> ~4GB/mo vs 31GB free. Public
# market data only, no keys; weight fine at 20.
_ROOT = Path("data/moat/fut")
_HB = Path("data/recorder_heartbeat")
_DEPTH_EVERY_S = 1.0
_TRADES_EVERY_S = 5.0
_DISK_MAX_FRAC = 0.80                              # stop writing above this disk usage
_FLUSH_ROWS = 200                                  # buffered rows per symbol before flush


def _get(path: str, params: str) -> object:
    req = urllib.request.Request(f"{_BASE}{path}?{params}",
                                 headers={"User-Agent": "quant-recorder/1.0"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())


def _disk_ok() -> bool:
    u = shutil.disk_usage("/")
    return (u.used / u.total) < _DISK_MAX_FRAC


def _flush(sym: str, rows: list[dict]) -> None:
    if not rows:
        return
    hour = datetime.now(tz=UTC).strftime("%Y%m%d_%H")
    p = _ROOT / sym / f"{hour}.jsonl.gz"
    p.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(p, "at", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, separators=(",", ":")) + "\n")
    rows.clear()


def main() -> None:
    print(f"recorder v1 | {len(_SYMBOLS)} symbols | depth@{_DEPTH_EVERY_S}s "
          f"trades@{_TRADES_EVERY_S}s -> {_ROOT}/")
    buf: dict[str, list[dict]] = {s: [] for s in _SYMBOLS}
    last_trade_id: dict[str, int] = {}
    last_trades_poll = 0.0
    disk_warned = False
    while True:
        t0 = time.time()
        if not _disk_ok():
            if not disk_warned:
                print("recorder: DISK >80% -- writing paused (heartbeat continues)")
                disk_warned = True
            _HB.write_text(datetime.now(tz=UTC).isoformat() + " DISK-PAUSED", "utf-8")
            time.sleep(30)
            continue
        disk_warned = False
        for sym in _SYMBOLS:
            try:
                d = _get("/fapi/v1/depth", f"symbol={sym}&limit=20")
                buf[sym].append({"t": int(time.time() * 1000), "k": "d",
                                 "u": d.get("lastUpdateId"),
                                 "b": d.get("bids"), "a": d.get("asks")})
            except Exception:
                pass                                # transient venue hiccup: skip one tick
        now = time.time()
        if now - last_trades_poll >= _TRADES_EVERY_S:
            last_trades_poll = now
            for sym in _SYMBOLS:
                try:
                    q = f"symbol={sym}&limit=1000"
                    if sym in last_trade_id:
                        q += f"&fromId={last_trade_id[sym] + 1}"
                    trades = _get("/fapi/v1/aggTrades", q)
                    if isinstance(trades, list) and trades:
                        last_trade_id[sym] = int(trades[-1]["a"])
                        for tr in trades:
                            buf[sym].append({"t": int(tr["T"]), "k": "t", "a": int(tr["a"]),
                                             "p": tr["p"], "q": tr["q"],
                                             "m": bool(tr["m"])})
                except Exception:
                    pass
        for sym in _SYMBOLS:
            if len(buf[sym]) >= _FLUSH_ROWS:
                try:
                    _flush(sym, buf[sym])
                except OSError:
                    buf[sym].clear()                # disk trouble: drop rather than die
        with contextlib.suppress(OSError):
            _HB.write_text(datetime.now(tz=UTC).isoformat(), "utf-8")
        time.sleep(max(0.0, _DEPTH_EVERY_S - (time.time() - t0)))


if __name__ == "__main__":
    main()

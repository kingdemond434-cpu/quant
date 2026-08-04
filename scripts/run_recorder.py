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
_CORE = ("BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT",
            "DOGEUSDT", "ADAUSDT", "AVAXUSDT", "LINKUSDT", "LTCUSDT",
            "TRXUSDT", "DOTUSDT", "BCHUSDT", "NEARUSDT", "SUIUSDT",
            "UNIUSDT", "APTUSDT", "FILUSDT", "ARBUSDT", "OPUSDT")
# --- DYNAMIC UNIVERSE (gap #39, 2026-07-22) ------------------------------------------------
# The cost model built from this moat was USELESS for real sizing: the recorder held 20 majors
# while the carry book held high-funding small-caps -- ZERO intersection. You cannot calibrate
# execution cost for a book you do not record. The carry book ROTATES, so the traded names are
# read live rather than hardcoded, with a hard cap so a runaway book can never blow the weight
# budget (2026-07-21: an over-wide universe got this recorder IP-banned).
_MAX_SYMBOLS = 32


def _book_symbols() -> tuple[str, ...]:
    try:
        pos = json.loads(Path("data/cashcarry_positions.json").read_text("utf-8"))["positions"]
        return tuple(sorted(str(s) for s in pos))
    except (OSError, json.JSONDecodeError, KeyError, TypeError):
        return ()


_SYMBOLS = tuple(dict.fromkeys(_CORE + _book_symbols()))[:_MAX_SYMBOLS]
# 5 -> 20 (principal max order, 2026-07-21): every unrecorded day is unrecoverable;
# disk math: ~33MB/day at 5 syms -> ~130MB/day at 20 -> ~4GB/mo vs 31GB free. Public
# market data only, no keys; weight fine at 20.
_ROOT = Path("data/moat/fut")
_HB = Path("data/recorder_heartbeat")
_DEPTH_EVERY_S = 5.0   # 1.0 -> 4.0 when symbols went 5 -> 20 (weight budget)
_TRADES_EVERY_S = 40.0  # 5.0 -> 20.0 for the same reason
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



# --- BINANCE WEIGHT GUARD (added 2026-07-21 after a self-inflicted IP ban) ---
# The USD-M futures budget is 2400 weight/min. depth(limit=20) costs 2; aggTrades(limit=1000)
# costs 20. Expanding _SYMBOLS without widening intervals silently triples the burn and the
# venue cuts the stream hours later with no traceback. Compute it at boot and refuse to start.
_WEIGHT_LIMIT_PER_MIN = 2400
_WEIGHT_TARGET_FRAC = 0.80          # stay well under; other desk processes share the IP


def _weight_per_min() -> float:
    depth = len(_SYMBOLS) * 2 * (60.0 / _DEPTH_EVERY_S)
    trades = len(_SYMBOLS) * 20 * (60.0 / _TRADES_EVERY_S)
    return depth + trades


def _assert_weight_budget() -> None:
    w = _weight_per_min()
    cap = _WEIGHT_LIMIT_PER_MIN * _WEIGHT_TARGET_FRAC
    print(f"recorder weight budget: {w:.0f}/min vs cap {cap:.0f}/min "
          f"({len(_SYMBOLS)} symbols, depth@{_DEPTH_EVERY_S}s, trades@{_TRADES_EVERY_S}s)")
    if w > cap:
        raise SystemExit(
            f"REFUSING TO START: {w:.0f} weight/min exceeds {cap:.0f}/min. Widen "
            f"_DEPTH_EVERY_S/_TRADES_EVERY_S or cut _SYMBOLS. (2026-07-21: 20 symbols at the "
            "old 1s/5s intervals = 7200/min got the recorder IP-banned after 6 hours.)")


def main() -> None:
    _assert_weight_budget()
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
                    # ONE SYMBOL'S FETCH MUST NOT KILL THE LOOP FOR THE OTHER TWENTY-NINE.
                    # Raising here stops recording every symbol over a transient failure on
                    # one, and unrecorded seconds are permanently unbuyable. Nothing is lost
                    # by continuing: `fromId` resumes from the last id actually seen, so the
                    # next tick collects the gap. Deferred, not dropped.
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

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
import signal
import time
import urllib.request
from datetime import UTC, datetime
from pathlib import Path


def _retired_exit(label: str) -> None:
    """Exit immediately when the desk has PERMANENTLY retired this recorder.

    `RECORDERS_OFF` is a PAUSE and deliberately does not exit -- systemd would restart it, so a
    paused recorder idles in memory ready to resume. That trade is correct for a pause and wrong
    for a retirement: under the MT5 universe mandate these crypto-venue recorders will never
    resume, and five of them idling held 313MB on a 4GB box for weeks while doing nothing. The
    cash-carry executor logged "RETIRED: idling permanently" and kept 143MB resident to do it.

    So retirement gets its own switch with the opposite behaviour. The process exits; systemd
    restarts it; it exits again; within seconds the unit's own start-rate limiter trips and
    systemd stops trying. The memory is genuinely returned. This is documented systemd behaviour,
    not a trick, and it is fully reversible by someone with root:

        systemctl reset-failed <unit>     # after removing data/RECORDERS_RETIRED
    """
    import sys as _sys
    from pathlib import Path as _P
    flag = _P(__file__).resolve().parent.parent / "data" / "RECORDERS_RETIRED"
    if flag.exists():
        print(f"{label}: data/RECORDERS_RETIRED present -- this venue is retired under the MT5 "
              f"mandate. Exiting so the memory is returned rather than idled. Remove the flag "
              f"and `systemctl reset-failed` to revive.", flush=True)
        _sys.exit(0)


def _switch_wait(label: str) -> None:
    """Pause while data/RECORDERS_OFF exists. See scripts/recorder_switch.py."""
    _retired_exit(label)
    import time as _t
    from pathlib import Path as _P
    flag = _P(__file__).resolve().parent.parent / "data" / "RECORDERS_OFF"
    if not flag.exists():
        return
    print(f"{label}: data/RECORDERS_OFF present -- recording paused (not exiting;"
          " systemd would restart an exit). Remove the file to resume.", flush=True)
    while flag.exists():
        _t.sleep(30)
    print(f"{label}: RECORDERS_OFF cleared -- resuming", flush=True)


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

# RESIDUAL FOUND 2026-07-29: the 07-22 fix unioned the HELD book at BOOT ONLY. The book is
# deadman-halted and flat, so the union is empty and the moat is once again 20 majors the desk
# does not trade -- gap #39 open in effect while reading as closed. Three changes:
#   (a) TRADED names come from the trade LOG too, not only live positions, so a halted or
#       rotated book still records the universe the cost model must calibrate;
#   (b) PRIORITY: traded names outrank majors when the cap binds -- the old order let 20 majors
#       fill the cap and evict the very symbols the cost model needs (BTC/ETH stay as the liquid
#       benchmark, because a cost model with no benchmark cannot tell "thin" from "normal");
#   (c) the universe is RECOMPUTED IN-FLIGHT (hourly), so a name the executor opens starts being
#       recorded within the hour instead of at the next process restart.
_BENCH = ("BTCUSDT", "ETHUSDT")          # always-on liquid benchmark, never evicted
_TRADED_LOOKBACK_D = 30.0
_UNIVERSE_REFRESH_S = 3600.0


def _book_symbols() -> tuple[str, ...]:
    try:
        pos = json.loads(Path("data/cashcarry_positions.json").read_text("utf-8"))["positions"]
        return tuple(sorted(str(s) for s in pos))
    except (OSError, json.JSONDecodeError, KeyError, TypeError):
        return ()


def _recently_traded() -> tuple[str, ...]:
    """Symbols the desk actually traded in the lookback -- read defensively: the trade log is a
    list of dicts on the VPS, may be absent here, and its schema has changed before."""
    try:
        raw = json.loads(Path("data/cashcarry_trades.json").read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        return ()
    rows = raw if isinstance(raw, list) else raw.get("trades") if isinstance(raw, dict) else None
    if not isinstance(rows, list):
        return ()
    floor_ms = (time.time() - _TRADED_LOOKBACK_D * 86400.0) * 1000.0
    out: list[str] = []
    for r in reversed(rows):                       # newest first
        if not isinstance(r, dict):
            continue
        sym = r.get("symbol") or r.get("sym")
        if not isinstance(sym, str):
            continue
        ts = r.get("closed_ms") or r.get("ts_ms") or r.get("opened_ms")
        if isinstance(ts, (int, float)) and float(ts) < floor_ms:
            continue                               # older than the lookback: stop counting it
        if sym not in out:
            out.append(sym)
        if len(out) >= _MAX_SYMBOLS:
            break
    return tuple(out)


def _universe() -> tuple[str, ...]:
    """Benchmark + traded (held, then recently traded) + majors, deduped, capped.

    Order IS the priority: when the cap binds, MAJORS are dropped and traded names survive.
    Pure function of the files it reads, so the twin in run_recorder_spot.py can be diffed
    against it line by line (the two recorders stay standalone by design)."""
    ordered = [*_BENCH, *_book_symbols(), *_recently_traded(), *_CORE]
    return tuple(dict.fromkeys(ordered))[:_MAX_SYMBOLS]


_SYMBOLS = _universe()
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


def _disk_ok(path: Path = _ROOT) -> bool:
    """True when the filesystem THE RECORDER WRITES TO has headroom.

    Measured on the target path, not "/": data/moat sits on its own volume whenever the box has a
    data disk, and then "/" is simply a different disk. Wrong in both directions and silent in
    both -- it pauses the recorder while the moat volume is empty, or lets writes fill the moat
    volume unchecked. Probe the nearest existing ancestor, since the tree may not exist yet.
    """
    probe = path if path.exists() else next((p for p in path.parents if p.exists()), Path("/"))
    u = shutil.disk_usage(probe)
    return (u.used / u.total) < _DISK_MAX_FRAC


# --- GRACEFUL DRAIN ON SIGNAL (L1.28a: a buffered row is as unbuyable as an unrecorded one) ---
# Rows sit in memory until _FLUSH_ROWS of them accumulate, which at depth@5s is ~16 MINUTES per
# symbol. Every respawn therefore dropped up to that much tape on the floor, silently and
# routinely: the */5 supervisor, the */10 pgrep guard, a deploy, a crash-restart. The
# universe-refresh path above already flushes DEPARTING SYMBOLS "so no buffered rows are lost" --
# the same care simply was never extended to the departing PROCESS.
#
# WHY A FLAG AND NOT A FLUSH INSIDE THE HANDLER. Signals land between bytecodes, so flushing from
# the handler can interrupt a gzip member mid-write and corrupt the very file the drain exists to
# protect. Draining at the top of the loop cannot race the writer and costs at most one iteration
# of latency (PEP 475 resumes the sleep, so <= _DEPTH_EVERY_S plus any in-flight request).
_STOP = False


def _request_stop(_signum: int, _frame: object) -> None:
    global _STOP
    _STOP = True


def _install_drain() -> None:
    for sig in (signal.SIGTERM, signal.SIGINT):
        # A handler is unsettable off the main thread; that is not a reason to refuse to record.
        with contextlib.suppress(OSError, ValueError):
            signal.signal(sig, _request_stop)


def _drain(buf: dict[str, list[dict]]) -> None:
    """Flush every buffered row before exit. Best-effort per symbol: one bad path must not
    strand the other twenty-nine symbols' rows."""
    for sym in list(buf):
        with contextlib.suppress(OSError):
            _flush(sym, buf[sym])


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


def _weight_per_min(symbols: tuple[str, ...] = ()) -> float:
    syms = symbols or _SYMBOLS
    depth = len(syms) * 2 * (60.0 / _DEPTH_EVERY_S)
    trades = len(syms) * 20 * (60.0 / _TRADES_EVERY_S)
    return depth + trades


def _weight_capped(symbols: tuple[str, ...]) -> tuple[str, ...]:
    """Trim from the TAIL (lowest priority = majors) until the weight budget fits.

    The 2026-07-21 IP ban came from an over-wide universe; a mid-flight refresh that could grow
    the set is the same hazard, so growth is bounded by arithmetic rather than by trust."""
    cap = _WEIGHT_LIMIT_PER_MIN * _WEIGHT_TARGET_FRAC
    out = list(symbols)
    while out and _weight_per_min(tuple(out)) > cap:
        out.pop()
    return tuple(out)


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
    _install_drain()
    print(f"recorder v1 | {len(_SYMBOLS)} symbols | depth@{_DEPTH_EVERY_S}s "
          f"trades@{_TRADES_EVERY_S}s -> {_ROOT}/")
    symbols = _weight_capped(_SYMBOLS)
    buf: dict[str, list[dict]] = {s: [] for s in symbols}
    last_trade_id: dict[str, int] = {}
    last_trades_poll = 0.0
    last_universe_poll = time.time()
    disk_warned = False
    while True:
        # NO-ROOT KILL SWITCH. `quant` has no sudo on the VPS, so
        # `systemctl stop` is unavailable to the operator who needs it, and
        # Restart=always makes killing the process pointless. Idles rather than
        # exits, because an exit just moves the disk problem into the journal.
        _switch_wait('recorder-fut')
        t0 = time.time()
        if _STOP:
            _drain(buf)
            print("recorder: drained buffers on signal -- exiting")
            return
        # UNIVERSE REFRESH (gap #39, 2026-07-29): a name the executor opens starts being recorded
        # within the hour rather than at the next restart. Departing symbols flush first so no
        # buffered rows are lost; the weight budget is re-checked against the ACTUAL new count.
        if t0 - last_universe_poll >= _UNIVERSE_REFRESH_S:
            last_universe_poll = t0
            fresh = _weight_capped(_universe())
            if set(fresh) != set(symbols):
                for gone in [x for x in symbols if x not in fresh]:
                    with contextlib.suppress(OSError):
                        _flush(gone, buf.get(gone, []))
                    buf.pop(gone, None)
                added = [x for x in fresh if x not in symbols]
                for new_sym in added:
                    buf[new_sym] = []
                dropped_by_weight = [x for x in _universe() if x not in fresh]
                print(f"recorder universe refresh: +{added} -"
                      f"{[x for x in symbols if x not in fresh]} "
                      f"| now {len(fresh)} syms, {_weight_per_min(fresh):.0f} weight/min"
                      + (f" | WEIGHT-DROPPED {dropped_by_weight}" if dropped_by_weight else ""))
                symbols = fresh
        if not _disk_ok():
            if not disk_warned:
                print("recorder: DISK >80% -- writing paused (heartbeat continues)")
                disk_warned = True
            _HB.write_text(datetime.now(tz=UTC).isoformat() + " DISK-PAUSED", "utf-8")
            time.sleep(30)
            continue
        disk_warned = False
        for sym in symbols:
            try:
                d = _get("/fapi/v1/depth", f"symbol={sym}&limit=20")
                # L1.46: `t` is OUR receipt (taken after _get returned), "E"/"T" are the VENUE's
                # own stamps, and "c" declares which clock `t` came from. Retaining both makes
                # Delta = t - E a measured series instead of an assumption; dropping E was
                # discarding the one number no vendor can sell us and no backfill can recover.
                buf[sym].append({"t": int(time.time() * 1000), "k": "d", "c": "recv",
                                 "E": d.get("E"), "T": d.get("T"),
                                 "u": d.get("lastUpdateId"),
                                 "b": d.get("bids"), "a": d.get("asks")})
            except Exception:
                pass                                # transient venue hiccup: skip one tick
        now = time.time()
        if now - last_trades_poll >= _TRADES_EVERY_S:
            last_trades_poll = now
            for sym in symbols:
                try:
                    q = f"symbol={sym}&limit=1000"
                    if sym in last_trade_id:
                        q += f"&fromId={last_trade_id[sym] + 1}"
                    trades = _get("/fapi/v1/aggTrades", q)
                    if isinstance(trades, list) and trades:
                        last_trade_id[sym] = int(trades[-1]["a"])
                        for tr in trades:
                            # L1.46: `t` here is the VENUE's clock, unlike the depth rows above.
                            # Same field, same file, different clock -- now declared rather than
                            # inferable only by reading this source.
                            buf[sym].append({"t": int(tr["T"]), "k": "t", "c": "venue",
                                             "a": int(tr["a"]),
                                             "p": tr["p"], "q": tr["q"],
                                             "m": bool(tr["m"])})
                except Exception:
                    # ONE SYMBOL'S FETCH MUST NOT KILL THE LOOP FOR THE OTHER TWENTY-NINE.
                    # Raising here stops recording every symbol over a transient failure on
                    # one, and unrecorded seconds are permanently unbuyable. Nothing is lost
                    # by continuing: `fromId` resumes from the last id actually seen, so the
                    # next tick collects the gap. Deferred, not dropped.
                    pass
        for sym in symbols:
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

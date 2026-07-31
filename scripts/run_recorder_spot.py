"""DATA-MOAT RECORDER v1 -- SPOT LEG (gap #35).

Companion to scripts/run_recorder.py (which records USD-M FUTURES microstructure). This
process records LIVE Binance SPOT microstructure for the same liquid symbols: top-20 order
book at ~4s cadence + every aggTrade, gzip-jsonl hourly partitions under data/moat/spot/{sym}/.

Why this exists (gap #35, micro-audit 07-19 + panel 07-20, verified vs code): the desk is
DELTA-NEUTRAL -- every carry trade has an equal-weight SPOT leg. A pre-live TCA / execution-
cost model calibrated on perp-only ticks silently mis-prices half of every trade, and spot
liquidity/slippage on the smaller-cap carry names is plausibly the MORE binding cost. Recording
spot alongside futures also yields a live spot-vs-perp basis/depth panel on identical names.
Every unrecorded hour is permanently unrecoverable (the gap #18 principle), so this starts NOW.

Isolation identical to the futures recorder: no trading imports, no keys, stdlib-only, writes
ONLY under data/moat/spot/ + its own heartbeat -- this process CANNOT touch the book.

Rate limits: Binance SPOT (api.binance.com) uses a SEPARATE per-IP weight bucket from USD-M
futures (fapi.binance.com), so this does NOT consume the futures recorder's 2400/min budget.
Spot request-weight limit is 6000/min; boot-time weight guard refuses to start if over
(same defensive pattern the futures recorder gained after the 2026-07-21 self-inflicted IP ban).

Supervision: liveness = data/recorder_spot_heartbeat (alerted if stale); a 10-minute cron
pgrep-guard respawns it (mirrors run_recorder_bybit.py).

    python scripts/run_recorder_spot.py
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

_BASE = "https://api.binance.com"                  # LIVE public SPOT market data (read-only)
# Mirror the futures recorder's symbol set (liquid majors); the boot filter drops any that are
# not TRADING as a Binance spot pair, so a perp-only listing never wastes weight on 400s.
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

# RESIDUAL CLOSED 2026-07-29 -- TWIN OF scripts/run_recorder.py (same ~40 lines, deliberately
# copied: the two recorders stay standalone processes by design, so this block is diffed against
# its twin rather than shared). The 07-22 union was computed at BOOT only, and with the book
# deadman-halted and flat the union is empty -- so the spot moat was 20 majors while every carry
# has a SPOT leg on a small-cap. Traded names now come from the trade LOG as well as live
# positions, they OUTRANK majors when the cap binds, and the set is recomputed hourly in-flight.
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
    """Symbols traded within the lookback, newest first. Read defensively (schema has changed)."""
    try:
        raw = json.loads(Path("data/cashcarry_trades.json").read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        return ()
    rows = raw if isinstance(raw, list) else raw.get("trades") if isinstance(raw, dict) else None
    if not isinstance(rows, list):
        return ()
    floor_ms = (time.time() - _TRADED_LOOKBACK_D * 86400.0) * 1000.0
    out: list[str] = []
    for r in reversed(rows):
        if not isinstance(r, dict):
            continue
        sym = r.get("symbol") or r.get("sym")
        if not isinstance(sym, str):
            continue
        ts = r.get("closed_ms") or r.get("ts_ms") or r.get("opened_ms")
        if isinstance(ts, (int, float)) and float(ts) < floor_ms:
            continue
        if sym not in out:
            out.append(sym)
        if len(out) >= _MAX_SYMBOLS:
            break
    return tuple(out)


def _universe() -> tuple[str, ...]:
    """Benchmark + traded (held, then recently traded) + majors. Order IS the priority: when the
    cap binds, majors are dropped and traded names survive."""
    ordered = [*_BENCH, *_book_symbols(), *_recently_traded(), *_CORE]
    return tuple(dict.fromkeys(ordered))[:_MAX_SYMBOLS]


_SYMBOLS = _universe()
_ROOT = Path("data/moat/spot")
_HB = Path("data/recorder_spot_heartbeat")
_DEPTH_EVERY_S = 5.0    # matches the futures recorder cadence (weight budget below)
_TRADES_EVERY_S = 40.0
_DISK_MAX_FRAC = 0.80                               # stop writing above this disk usage
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


# --- BINANCE SPOT WEIGHT GUARD (gap #35 build, mirrors the futures guard) ---
# Spot IP request-weight budget is 6000/min. depth(limit<=100) costs 5; aggTrades(limit=1000)
# costs 4. Compute the steady-state burn at boot and refuse to start if over -- the futures
# recorder was IP-banned on 2026-07-21 by expanding symbols without widening intervals.
_WEIGHT_LIMIT_PER_MIN = 6000
_WEIGHT_TARGET_FRAC = 0.80          # stay well under; leave headroom for the boot exchangeInfo
_DEPTH_WEIGHT = 5                   # /api/v3/depth, limit 1-100
_TRADES_WEIGHT = 4                  # /api/v3/aggTrades


def _weight_per_min(n_symbols: int) -> float:
    depth = n_symbols * _DEPTH_WEIGHT * (60.0 / _DEPTH_EVERY_S)
    trades = n_symbols * _TRADES_WEIGHT * (60.0 / _TRADES_EVERY_S)
    return depth + trades


def _assert_weight_budget(symbols: tuple[str, ...]) -> None:
    w = _weight_per_min(len(symbols))
    cap = _WEIGHT_LIMIT_PER_MIN * _WEIGHT_TARGET_FRAC
    print(f"spot recorder weight budget: {w:.0f}/min vs cap {cap:.0f}/min "
          f"({len(symbols)} symbols, depth@{_DEPTH_EVERY_S}s, trades@{_TRADES_EVERY_S}s)")
    if w > cap:
        raise SystemExit(
            f"REFUSING TO START: {w:.0f} weight/min exceeds {cap:.0f}/min. Widen "
            "_DEPTH_EVERY_S/_TRADES_EVERY_S or cut _SYMBOLS.")


def _valid_spot_symbols(wanted: tuple[str, ...]) -> tuple[str, ...]:
    """Keep only symbols that are TRADING spot pairs. Boot hiccup -> use the full list rather
    than block recording (a bad symbol just wastes one poll's weight and is caught by try/except).
    """
    try:
        info = _get("/api/v3/exchangeInfo", "")
        trading = {s["symbol"] for s in info.get("symbols", [])
                   if s.get("status") == "TRADING"}
        keep = tuple(s for s in wanted if s in trading)
        dropped = [s for s in wanted if s not in trading]
        if dropped:
            print(f"spot recorder: dropped non-spot/non-trading symbols: {dropped}")
        return keep or wanted
    except Exception as e:  # boot robustness over strictness: never block recording
        print(f"spot recorder: exchangeInfo unavailable ({e}); using full symbol list")
        return wanted


def _weight_capped(symbols: tuple[str, ...]) -> tuple[str, ...]:
    """Trim from the TAIL (lowest priority = majors) until the weight budget fits. A mid-flight
    refresh that can GROW the set is the same hazard as the 2026-07-21 IP ban, so growth is
    bounded by arithmetic, not by trust."""
    cap = _WEIGHT_LIMIT_PER_MIN * _WEIGHT_TARGET_FRAC
    out = list(symbols)
    while out and _weight_per_min(len(out)) > cap:
        out.pop()
    return tuple(out)


def main() -> None:
    symbols = _weight_capped(_valid_spot_symbols(_SYMBOLS))
    _assert_weight_budget(symbols)
    print(f"spot recorder v1 | {len(symbols)} symbols | depth@{_DEPTH_EVERY_S}s "
          f"trades@{_TRADES_EVERY_S}s -> {_ROOT}/")
    buf: dict[str, list[dict]] = {s: [] for s in symbols}
    last_trade_id: dict[str, int] = {}
    last_trades_poll = 0.0
    last_universe_poll = time.time()
    disk_warned = False
    while True:
        t0 = time.time()
        # UNIVERSE REFRESH (gap #39 residual, 2026-07-29): twin of run_recorder.py. New spot legs
        # start recording within the hour; departing symbols flush first; the weight budget is
        # re-checked against the ACTUAL count, and new names are re-validated as spot pairs.
        if t0 - last_universe_poll >= _UNIVERSE_REFRESH_S:
            last_universe_poll = t0
            fresh = _weight_capped(_valid_spot_symbols(_universe()))
            if set(fresh) != set(symbols):
                for gone in [x for x in symbols if x not in fresh]:
                    with contextlib.suppress(OSError):
                        _flush(gone, buf.get(gone, []))
                    buf.pop(gone, None)
                for new_sym in [x for x in fresh if x not in symbols]:
                    buf[new_sym] = []
                print(f"spot recorder universe refresh: now {len(fresh)} syms, "
                      f"{_weight_per_min(len(fresh)):.0f} weight/min")
                symbols = fresh
        if not _disk_ok():
            if not disk_warned:
                print("spot recorder: DISK >80% -- writing paused (heartbeat continues)")
                disk_warned = True
            _HB.write_text(datetime.now(tz=UTC).isoformat() + " DISK-PAUSED", "utf-8")
            time.sleep(30)
            continue
        disk_warned = False
        for sym in symbols:
            try:
                d = _get("/api/v3/depth", f"symbol={sym}&limit=20")
                buf[sym].append({"t": int(time.time() * 1000), "k": "d",
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
                    trades = _get("/api/v3/aggTrades", q)
                    if isinstance(trades, list) and trades:
                        last_trade_id[sym] = int(trades[-1]["a"])
                        for tr in trades:
                            buf[sym].append({"t": int(tr["T"]), "k": "t", "a": int(tr["a"]),
                                             "p": tr["p"], "q": tr["q"],
                                             "m": bool(tr["m"])})
                except Exception:
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

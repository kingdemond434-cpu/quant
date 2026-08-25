"""MT5 DATA MOAT RECORDER v1 -- the permanent Fusion tape (docs/research/MOAT_NODE_SPEC.md).

Records reality; never decides trades. Release-1 scope: full dynamic symbol universe ticks
(incremental copy_ticks_range with per-symbol cursors -- NOT symbol_info_tick polling), symbol
specification history (daily + on-change), DOM where the broker exposes it, feed/terminal
health, clock-skew audit, disk guard. Bronze is append-only gzip-jsonl outside the git repo.

    py -3 moat_recorder.py            # resident loop (single-instance lock)
    py -3 moat_recorder.py --once     # one full cycle, print summary, exit (smoke test)

Design notes that are load-bearing:
- Cursors checkpoint AFTER a successful append, so a crash re-pulls the last window and the
  reader dedupes on (time_msc, bid, ask) -- losing ticks is worse than re-reading some.
- Every append opens the day file in 'ab': multi-member gzip is valid and stream-readable.
- A paused recorder (disk floor) writes PAUSED health rows every cycle -- the gap is recorded
  as a gap, never as silence (WS-005).
- No symbol hardcodes anywhere: the universe is symbols_get() on every refresh (LAWS S1).
"""
from __future__ import annotations

import gzip
import hashlib
import json
import os
import shutil
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import MetaTrader5 as mt5

BRONZE = Path(os.environ.get("MOAT_BRONZE", r"C:\moat\bronze"))
CHECKPOINTS = Path(os.environ.get("MOAT_CHECKPOINTS", r"C:\moat\checkpoints"))
LOCK = Path(os.environ.get("MOAT_LOCK", r"C:\moat\recorder.lock"))
HEARTBEAT = Path(os.environ.get("MOAT_HEARTBEAT", r"C:\moat\heartbeat.json"))

TICK_INTERVAL_S = int(os.environ.get("MOAT_TICK_INTERVAL_S", "60"))
UNIVERSE_REFRESH_S = int(os.environ.get("MOAT_UNIVERSE_REFRESH_S", "300"))
SPEC_INTERVAL_S = int(os.environ.get("MOAT_SPEC_INTERVAL_S", "3600"))
DOM_INTERVAL_S = float(os.environ.get("MOAT_DOM_INTERVAL_S", "2.0"))
HEALTH_INTERVAL_S = int(os.environ.get("MOAT_HEALTH_INTERVAL_S", "60"))
BACKFILL_H = int(os.environ.get("MOAT_BACKFILL_H", "48"))
DISK_FLOOR_GB = float(os.environ.get("MOAT_DISK_FLOOR_GB", "10"))
PULL_CAP = 500_000            # ticks per copy_ticks_range call; loop drains the rest
OVERLAP_MS = 2_000            # re-pull window overlap; dedupe is the reader's job


def log(msg: str) -> None:
    print(f"{datetime.now(tz=UTC).isoformat(timespec='seconds')} {msg}", flush=True)


def append_gz(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = "".join(json.dumps(r, separators=(",", ":"), default=str) + "\n" for r in rows)
    with gzip.open(path, "ab") as f:
        f.write(payload.encode("utf-8"))


def day_file(root: Path, sym: str, now: datetime) -> Path:
    return root / sym / f"{now:%Y%m%d}.jsonl.gz"


def read_json(path: Path, default: dict) -> dict:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return default


def write_json_atomic(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj, separators=(",", ":"), default=str), "utf-8")
    os.replace(tmp, path)


def single_instance() -> bool:
    """PID lock: a duplicate start (watchdog task) exits instantly instead of double-writing."""
    stale = True
    info = read_json(LOCK, {})
    pid = info.get("pid")
    if isinstance(pid, int):
        try:
            import ctypes
            h = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)  # QUERY_LIMITED
            if h:
                ctypes.windll.kernel32.CloseHandle(h)
                stale = False
        except Exception:
            stale = False       # cannot verify -> assume alive; refuse to double-run
    if pid and not stale:
        return False
    write_json_atomic(LOCK, {"pid": os.getpid(), "started": datetime.now(tz=UTC).isoformat()})
    return True


def disk_free_gb() -> float:
    return shutil.disk_usage(str(BRONZE.anchor or "C:\\")).free / 1e9


class Recorder:
    def __init__(self) -> None:
        self.cursors: dict[str, int] = read_json(CHECKPOINTS / "tick_cursors.json", {})
        self.spec_hashes: dict[str, str] = read_json(CHECKPOINTS / "spec_hashes.json", {})
        self.universe: list[str] = []
        self.dom_ok: set[str] = set()
        self.dom_last_hash: dict[str, str] = {}
        self.counters = {"ticks": 0, "spec_changes": 0, "dom_rows": 0, "gaps": 0, "pulls": 0}
        self.skew_samples: list[int] = []
        self.last = {"universe": 0.0, "ticks": 0.0, "specs": 0.0, "health": 0.0}
        self.paused = False

    # -- universe -------------------------------------------------------------------------
    def refresh_universe(self) -> None:
        syms = mt5.symbols_get()
        if not syms:
            self.health_row(event="universe_empty")
            return
        fresh = [s.name for s in syms]
        gone = set(self.universe) - set(fresh)
        new = set(fresh) - set(self.universe)
        if gone or new:
            self.health_row(event="universe_change", added=sorted(new), removed=sorted(gone))
        self.universe = fresh
        for sym in new:
            if mt5.market_book_add(sym):
                self.dom_ok.add(sym)

    # -- ticks ----------------------------------------------------------------------------
    def pull_ticks(self) -> None:
        now = datetime.now(tz=UTC)
        for sym in list(self.universe):
            cur = self.cursors.get(sym)
            if cur is None:
                cur = int((now - timedelta(hours=BACKFILL_H)).timestamp() * 1000)
            start = datetime.fromtimestamp(max(cur - OVERLAP_MS, 0) / 1000, tz=UTC)
            while True:
                arr = mt5.copy_ticks_range(sym, start, now + timedelta(seconds=1),
                                           mt5.COPY_TICKS_ALL)
                self.counters["pulls"] += 1
                if arr is None:
                    self.counters["gaps"] += 1
                    self.health_row(event="tick_pull_failed", symbol=sym,
                                    err=str(mt5.last_error()))
                    break
                if len(arr) == 0:
                    break
                recv = datetime.now(tz=UTC).isoformat(timespec="milliseconds")
                mono = time.monotonic()
                names = arr.dtype.names
                rows = []
                top = cur
                for t in arr[:PULL_CAP]:
                    d = dict(zip(names, (x.item() if hasattr(x, "item") else x for x in t)))
                    if d.get("time_msc", 0) <= cur:
                        continue                      # overlap dedupe on the hot path
                    d["recv_utc"] = recv
                    d["recv_mono"] = mono
                    rows.append(d)
                    top = max(top, int(d["time_msc"]))
                if rows:
                    append_gz(day_file(BRONZE / "mt5_ticks", sym, now), rows)
                    self.counters["ticks"] += len(rows)
                    self.skew_samples.append(
                        int(datetime.now(tz=UTC).timestamp() * 1000) - top)
                    self.cursors[sym] = top
                    cur = top
                if len(arr) < PULL_CAP:
                    break                             # drained
                start = datetime.fromtimestamp(cur / 1000, tz=UTC)
        write_json_atomic(CHECKPOINTS / "tick_cursors.json", self.cursors)

    # -- specs ----------------------------------------------------------------------------
    def snapshot_specs(self) -> None:
        now = datetime.now(tz=UTC)
        rows = []
        for sym in self.universe:
            info = mt5.symbol_info(sym)
            if info is None:
                continue
            spec = info._asdict()
            digest = hashlib.sha256(
                json.dumps(spec, sort_keys=True, default=str).encode()).hexdigest()
            if self.spec_hashes.get(sym) != digest:
                rows.append({"ts": now.isoformat(), "symbol": sym, "hash": digest,
                             "spec": spec})
                self.spec_hashes[sym] = digest
        if rows:
            append_gz(BRONZE / "symbol_specs" / f"{now:%Y%m%d}.jsonl.gz", rows)
            self.counters["spec_changes"] += len(rows)
            write_json_atomic(CHECKPOINTS / "spec_hashes.json", self.spec_hashes)

    # -- DOM ------------------------------------------------------------------------------
    def poll_dom(self) -> None:
        now = datetime.now(tz=UTC)
        for sym in self.dom_ok:
            book = mt5.market_book_get(sym)
            if not book:
                continue
            levels = [{"type": b.type, "price": b.price, "volume": b.volume,
                       "volume_dbl": getattr(b, "volume_dbl", None)} for b in book]
            digest = hashlib.sha256(
                json.dumps(levels, sort_keys=True).encode()).hexdigest()
            if self.dom_last_hash.get(sym) == digest:
                continue
            self.dom_last_hash[sym] = digest
            append_gz(day_file(BRONZE / "mt5_dom", sym, now),
                      [{"ts": now.isoformat(timespec="milliseconds"),
                        "mono": time.monotonic(), "book": levels}])
            self.counters["dom_rows"] += 1

    # -- health / clock -------------------------------------------------------------------
    def health_row(self, event: str = "tick", **extra: object) -> None:
        now = datetime.now(tz=UTC)
        ti = mt5.terminal_info()
        skews = sorted(self.skew_samples[-1000:])
        row = {
            "ts": now.isoformat(), "event": event, "paused": self.paused,
            "connected": bool(ti.connected) if ti else False,
            "ping_last": getattr(ti, "ping_last", None) if ti else None,
            "retransmission": getattr(ti, "retransmission", None) if ti else None,
            "symbols": len(self.universe), "dom_symbols": len(self.dom_ok),
            "disk_free_gb": round(disk_free_gb(), 2),
            "skew_ms_p50": skews[len(skews) // 2] if skews else None,
            "skew_ms_p95": skews[int(len(skews) * 0.95)] if skews else None,
            **self.counters, **extra,
        }
        append_gz(BRONZE / "terminal_health" / f"{now:%Y%m%d}.jsonl.gz", [row])
        write_json_atomic(HEARTBEAT, row)

    # -- main loop ------------------------------------------------------------------------
    def cycle(self) -> None:
        mono = time.monotonic()
        free = disk_free_gb()
        was_paused = self.paused
        self.paused = free < DISK_FLOOR_GB
        if self.paused:
            if not was_paused:
                self.health_row(event="PAUSED_disk_floor", floor_gb=DISK_FLOOR_GB)
                log(f"PAUSED: disk {free:.1f}GB below floor {DISK_FLOOR_GB}GB")
            if mono - self.last["health"] >= HEALTH_INTERVAL_S:
                self.health_row(event="PAUSED_disk_floor")
                self.last["health"] = mono
            return
        if was_paused:
            self.health_row(event="RESUMED")
        if mono - self.last["universe"] >= UNIVERSE_REFRESH_S or not self.universe:
            self.refresh_universe()
            self.last["universe"] = mono
        if mono - self.last["ticks"] >= TICK_INTERVAL_S:
            self.pull_ticks()
            self.last["ticks"] = mono
        if mono - self.last["specs"] >= SPEC_INTERVAL_S:
            self.snapshot_specs()
            self.last["specs"] = mono
        self.poll_dom()
        if mono - self.last["health"] >= HEALTH_INTERVAL_S:
            self.health_row()
            self.last["health"] = mono


def main() -> int:
    once = "--once" in sys.argv
    if not single_instance():
        log("another recorder instance is alive -- exiting (single-instance lock)")
        return 0
    if not mt5.initialize():
        log(f"mt5.initialize FAILED: {mt5.last_error()}")
        return 1
    rec = Recorder()
    rec.health_row(event="recorder_start", once=once, backfill_h=BACKFILL_H)
    log(f"moat recorder up: bronze={BRONZE} universe pending, backfill={BACKFILL_H}h")
    try:
        if once:
            rec.refresh_universe()
            rec.pull_ticks()
            rec.snapshot_specs()
            rec.poll_dom()
            rec.health_row(event="once_complete")
            log(f"ONCE: {len(rec.universe)} symbols, ticks={rec.counters['ticks']} "
                f"specs={rec.counters['spec_changes']} dom={rec.counters['dom_rows']} "
                f"dom_subscribed={len(rec.dom_ok)}")
            return 0
        while True:
            rec.cycle()
            time.sleep(DOM_INTERVAL_S)
    except KeyboardInterrupt:
        log("shutdown requested")
    finally:
        rec.health_row(event="recorder_stop")
        write_json_atomic(CHECKPOINTS / "tick_cursors.json", rec.cursors)
        mt5.shutdown()
        with __import__("contextlib").suppress(OSError):
            LOCK.unlink()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""RESEARCH UNDER LOAD, AND RESEARCH KEPT APART FROM TRADING: two drills run on the box hourly.

    python desks/mt5/research/load_isolation_drill.py          # hourly leg `load_isolation`
    python desks/mt5/research/load_isolation_drill.py --json

WHY (ARCH-07, principal 2026-10-07: "reliable operations and controlled change: successful load,
outage, rollback and backup-restoration tests; experimental workloads separated from trading").
`recovery_drills` already grades outage (the gateway under a faulty MT5 double), rollback (the
sandbox rollback drill) and backup restoration (the off-site restore drill). Two of the five had
nothing behind them: no load test ever ran (`queue_overload` is a CI test of the control plane,
never the box), and the separation of experimental work from trading was a convention written
into task installers (`-Priority 4` for executors, 7 for research) that nothing measured.

THE LOAD DRILL. A probe made of the gateway's own pure decision code (`decision_core.atr_last`,
`bracket_spec`, `entry_is_legal` on a fixed 300-bar frame -- what one bracket placement computes)
is timed three ways for `ARM_S` seconds each:

    baseline   nothing added
    equal      one busy worker per core at THIS process's own priority
    separated  one busy worker per core one priority class BELOW this process

`equal` is the control: it shows what unseparated research does to the trading path on this
host, so a drill that cannot see starvation says so (`sensitive: false`) instead of passing.
`separated` is the claim: research at a lower class must leave the trading path's p99 within
`P99_RATIO_MAX` of its baseline. Workers end themselves at a deadline even if this process dies,
and the whole drill costs ~3 x ARM_S seconds of the cores' idle priority once an hour.

THE SEPARATION CENSUS. Every process on the host is classified by its command line: the trading
side (the gateway, its resident loop, the E8/FTMO executors, the MT5 terminal) and the research
side (anything under desks/mt5/research, the gauntlets, the miners). PASS needs both sides
present and every research process strictly below the lowest trading process's priority; one
research process at or above it is FAIL with its name. A host with no trading process (the build
box, CI) is UNMEASURED -- never PASS (L1.28a).

Writes desks/mt5/reports/LOAD_ISOLATION.json, graded by recovery_drills rows `load` and
`workload_separation`. It touches no money-path file and no live process: it reads priorities and
times a copy of pure functions.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from collections.abc import Callable, Iterable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
OUT = DESK / "reports" / "LOAD_ISOLATION.json"

#: Seconds per arm. Three arms plus spawn overhead: the leg takes ~8 s.
ARM_S = 2.0
#: The separated arm's p99 may be at most this multiple of the baseline p99. Measured on the 4-core
#: build box 2026-11-10: baseline p99 1.78 ms, equal-priority load 4.96 ms (2.8x), one class lower
#: 1.52 ms (0.9x). Twice the baseline leaves room for frequency scaling under a full-core load and
#: still fails a host where research lands on the trading path's priority.
P99_RATIO_MAX = 2.0
#: Workers per arm: one per core (the probe's own core included), so the equal arm contends.
MAX_WORKERS = 32
PASS, FAIL, UNMEASURED = "PASS", "FAIL", "UNMEASURED"

#: Command-line fragments, lower-cased with forward slashes, that mark a process as TRADING.
TRADING_MARKS: tuple[str, ...] = (
    "mt5desk/gateway.py", "gateway_resident.py", "run_gateway_loop.py",
    "e8_executor.py", "e8_gold.py", "ftmo_executor", "ftmo_follower", "venue_reader",
    "terminal64.exe",
)
#: Fragments that mark a process as RESEARCH / experimental work.
RESEARCH_MARKS: tuple[str, ...] = (
    "desks/mt5/research/", "external_gauntlet.py", "run_sharded_gauntlet.py",
    "hourly_cycle.py", "daily_cycle.py", "miner", "world_crawler", "deep_forest",
)

#: Windows priority classes in ascending order (psutil constants' numeric values), so a class
#: can be ranked and "one below" named without psutil's Windows-only attributes.
WIN_CLASSES: tuple[tuple[str, int], ...] = (
    ("IDLE", 0x40), ("BELOW_NORMAL", 0x4000), ("NORMAL", 0x20),
    ("ABOVE_NORMAL", 0x8000), ("HIGH", 0x80), ("REALTIME", 0x100),
)
WORKER = ("import time\nend = time.monotonic() + {s:.3f}\nx = 0\n"
          "while time.monotonic() < end:\n    x += 1\n")


# ------------------------------------------------------------------------------- priority
def rank(nice: Any) -> int | None:
    """A comparable priority: higher runs first. POSIX nice -20..19 -> 20..-19; Windows class ->
    its position in WIN_CLASSES."""
    if nice is None:
        return None
    try:
        n = int(nice)
    except (TypeError, ValueError):
        return None
    if os.name == "nt":
        for i, (_, v) in enumerate(WIN_CLASSES):
            if v == n:
                return i
        return None
    return -n


def _own_nice() -> Any:
    try:
        import psutil  # type: ignore[import-untyped,unused-ignore]
        return psutil.Process().nice()
    except Exception:  # psutil absent or refused: POSIX still answers
        return os.nice(0) if os.name != "nt" else None


def _lower_spawn_kwargs() -> dict[str, Any] | None:
    """Popen kwargs that start a child one priority class below this process, or None when this
    process already sits at the floor (the separated arm cannot then be run)."""
    if os.name == "nt":
        r = rank(_own_nice())
        if r is None or r == 0:
            return None
        return {"creationflags": WIN_CLASSES[r - 1][1]}
    if os.nice(0) >= 19:
        return None
    return {"preexec_fn": lambda: os.nice(10)}


def _equal_spawn_kwargs() -> dict[str, Any]:
    if os.name == "nt":
        r = rank(_own_nice())
        return {"creationflags": WIN_CLASSES[r][1]} if r is not None else {}
    return {}


# ---------------------------------------------------------------------------------- probe
def _probe() -> Callable[[], None]:
    """The trading path's own pure decision code on a fixed frame (no terminal, no file, no I/O)."""
    if str(DESK) not in sys.path:
        sys.path.insert(0, str(DESK))
    import numpy as np
    import pandas as pd
    from mt5desk import decision_core as dc

    rng = np.random.default_rng(7)
    close = 2000.0 + np.cumsum(rng.normal(0.0, 2.0, 300))
    high, low = close + rng.uniform(0, 3, 300), close - rng.uniform(0, 3, 300)
    frame = pd.DataFrame({"open": close, "high": high, "low": low, "close": close})
    hi, lo = float(high[-1]), float(low[-1])

    def run() -> None:
        a = dc.atr_last(frame)
        spec = dc.bracket_spec(hi, lo, max(a, 5.0), 0.01)
        dc.entry_is_legal(spec["buy_stop"]["price"], "buy", lo, lo + 0.2, 0.01, 20)
        dc.entry_is_legal(spec["sell_stop"]["price"], "sell", hi - 0.2, hi, 0.01, 20)
    return run


def _q(xs: list[float], p: float) -> float:
    s = sorted(xs)
    return s[min(len(s) - 1, int(len(s) * p))]


def _sample(probe: Callable[[], None], seconds: float) -> dict[str, Any]:
    ms: list[float] = []
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        t = time.perf_counter()
        probe()
        ms.append((time.perf_counter() - t) * 1000.0)
    if not ms:
        return {"n": 0}
    return {"n": len(ms), "p50_ms": round(_q(ms, 0.50), 4), "p99_ms": round(_q(ms, 0.99), 4),
            "max_ms": round(max(ms), 4)}


def _arm(probe: Callable[[], None], workers: int, kwargs: dict[str, Any] | None,
         seconds: float) -> dict[str, Any]:
    procs: list[subprocess.Popen[bytes]] = []
    if workers and kwargs is not None:
        code = WORKER.format(s=seconds + 1.0)
        for _ in range(workers):
            procs.append(subprocess.Popen([sys.executable, "-c", code],
                                          stdout=subprocess.DEVNULL,
                                          stderr=subprocess.DEVNULL, **kwargs))
        time.sleep(0.3)               # let the workers reach their busy loop
    try:
        return {**_sample(probe, seconds), "workers": len(procs)}
    finally:
        for p in procs:
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                p.kill()
                p.wait()


def load_drill(probe: Callable[[], None] | None = None, *, seconds: float = ARM_S,
               workers: int | None = None) -> dict[str, Any]:
    """The three-arm drill and its verdict."""
    try:
        probe = probe or _probe()
    except Exception as exc:          # the probe could not be built: nothing was measured
        return {"verdict": UNMEASURED, "why": f"probe unavailable: {type(exc).__name__}: {exc}"}
    for _ in range(50):
        probe()                       # warm caches so the baseline is not the cold start
    k = workers if workers is not None else min(MAX_WORKERS, os.cpu_count() or 1)
    lower = _lower_spawn_kwargs()
    base = _arm(probe, 0, {}, seconds)
    equal = _arm(probe, k, _equal_spawn_kwargs(), seconds)
    sep = _arm(probe, k, lower, seconds) if lower is not None else {"n": 0, "workers": 0}
    out: dict[str, Any] = {"arm_s": seconds, "workers": k, "p99_ratio_max": P99_RATIO_MAX,
                           "probe": "decision_core.atr_last + bracket_spec + entry_is_legal x2",
                           "baseline": base, "equal_priority": equal, "separated": sep,
                           "own_priority": _own_nice()}
    if lower is None:
        return {**out, "verdict": UNMEASURED,
                "why": "this process already runs at the lowest priority class: no lower class "
                       "exists to put the research load in"}
    if not (base.get("n") and equal.get("n") and sep.get("n")):
        return {**out, "verdict": UNMEASURED, "why": "an arm took no samples"}
    r_eq = equal["p99_ms"] / max(base["p99_ms"], 1e-6)
    r_sep = sep["p99_ms"] / max(base["p99_ms"], 1e-6)
    out.update(equal_p99_ratio=round(r_eq, 3), separated_p99_ratio=round(r_sep, 3),
               sensitive=r_eq > r_sep)
    if r_sep > P99_RATIO_MAX:
        return {**out, "verdict": FAIL,
                "why": f"research load one class below the trading path raised its p99 "
                       f"{r_sep:.2f}x (> {P99_RATIO_MAX}x): priority does not protect it here"}
    return {**out, "verdict": PASS,
            "why": f"{k} research workers one class lower: trading-path p99 {r_sep:.2f}x baseline "
                   f"(equal-priority control {r_eq:.2f}x)"}


# ------------------------------------------------------------------------------- census
def classify(cmdline: Iterable[str] | None) -> str | None:
    line = " ".join(cmdline or ()).lower().replace("\\", "/")
    if not line:
        return None
    if any(m in line for m in TRADING_MARKS):
        return "trading"
    if any(m in line for m in RESEARCH_MARKS):
        return "research"
    return None


def separation_census(procs: Iterable[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Every process's side and priority; FAIL names each research process that is not below
    the lowest-priority trading process."""
    if procs is None:
        try:
            import psutil  # type: ignore[import-untyped,unused-ignore]
        except ImportError:
            return {"verdict": UNMEASURED, "why": "psutil absent: process priorities unreadable"}
        procs = []
        for p in psutil.process_iter(["pid", "name", "cmdline", "nice"]):
            info = dict(p.info)
            procs.append(info)
    me = os.getpid()
    trading: list[dict[str, Any]] = []
    research: list[dict[str, Any]] = []
    for p in procs:
        if p.get("pid") == me:
            continue                  # the drill itself is research; it is not a reading
        side = classify(p.get("cmdline") or ([p["name"]] if p.get("name") else None))
        if side is None:
            continue
        row = {"pid": p.get("pid"), "name": p.get("name"), "nice": p.get("nice"),
               "rank": rank(p.get("nice")),
               "cmd": " ".join(p.get("cmdline") or [])[-160:]}
        (trading if side == "trading" else research).append(row)
    out: dict[str, Any] = {"trading": trading, "research_n": len(research),
                           "research_sample": research[:12]}
    ranked_t = [r["rank"] for r in trading if r["rank"] is not None]
    if not ranked_t:
        return {**out, "verdict": UNMEASURED,
                "why": "no trading process with a readable priority on this host (not the "
                       "trading box, or the gateway is down)"}
    if not research:
        return {**out, "verdict": UNMEASURED,
                "why": "no research process running at the instant of the census"}
    floor = min(ranked_t)
    offenders = [r for r in research if r["rank"] is None or r["rank"] >= floor]
    out["trading_floor_rank"] = floor
    if offenders:
        return {**out, "verdict": FAIL, "offenders": offenders[:20],
                "why": f"{len(offenders)} research process(es) at or above the trading side's "
                       f"lowest priority (or unreadable): research can starve trading"}
    return {**out, "verdict": PASS,
            "why": f"{len(research)} research process(es) all below the {len(trading)} trading "
                   "process(es)"}


# ---------------------------------------------------------------------------------- build
def build(now: datetime | None = None, *, seconds: float = ARM_S) -> dict[str, Any]:
    now = now or datetime.now(tz=UTC)
    t0 = time.monotonic()
    census = separation_census()
    load = load_drill(seconds=seconds)
    verdicts = (load["verdict"], census["verdict"])
    verdict = FAIL if FAIL in verdicts else PASS if verdicts == (PASS, PASS) else UNMEASURED
    return {"generated_utc": now.isoformat(timespec="seconds"), "host": os.uname().nodename
            if hasattr(os, "uname") else os.environ.get("COMPUTERNAME"),
            "verdict": verdict, "load": load, "separation": census,
            "wall_s": round(time.monotonic() - t0, 2),
            "rule": "load PASS needs the trading path's p99 within P99_RATIO_MAX of baseline "
                    "while one worker per core runs a class below it; separation PASS needs "
                    "every research process below every trading process; a host without a "
                    "trading process is UNMEASURED",
            "valid_until": (now + timedelta(hours=3)).isoformat(timespec="seconds")}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--arm-s", type=float, default=ARM_S)
    a = ap.parse_args(argv)
    doc = build(seconds=a.arm_s)
    if not a.dry_run:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        tmp = OUT.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
        os.replace(tmp, OUT)
    if a.json:
        print(json.dumps(doc, default=str))
    else:
        print(f"load_isolation: {doc['verdict']} load={doc['load']['verdict']} "
              f"({doc['load'].get('why')}) separation={doc['separation']['verdict']} "
              f"({doc['separation'].get('why')})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

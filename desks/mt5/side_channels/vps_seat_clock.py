"""THE BOX'S OWN CLOCK FOR THE SEATS ONLY THE VPS EVER RAN (2026-10-29).

Thirty-three intelligence seats were written only by VPS systemd timers (`seed_miners.py`,
`run_all_miners.py` and, through seed_miners, `regional_survivor_hunters`) and reached this box
only through the `intel-ship/send` transport, silent since 2026-10-14T01:50Z. This leg runs THE
SAME MINERS here, hourly, bounded -- without touching the VPS and without depending on it.

IDEMPOTENT WITH THE VPS PATH. A unit (one seed source, or one external channel) is DUE only when
none of its seats holds output newer than `seat_clocks.BOX_CADENCE_H` from ANY clock -- the VPS's
shipped files count -- and the box has not itself attempted it inside that window. So when the
VPS runs and ships, this skips; when it does not, this runs; and a unit is never fetched more
often than the VPS timer it stands in for. The census counts two sweeps of one seat in one hour
once (`check_producer_yield._seat_output`), so a late-arriving VPS file is not double-counted.

SOURCE RULES ARE THE MINERS' OWN, PLUS THE BOX'S RAILS. Each unit runs through its runner's
normal code path (`seed_miners.run_and_save(only=...)`, `run_all_miners.run_all_miners(only=...)`):
the SOURCE_WALLS dispositions, request caps, spacing, timeouts and the stub / fetch_error rows all
apply as on the VPS. ON TOP of them every request this leg's children send goes through
`box_rails` (PR #524 audit): an honest User-Agent naming the project's research crawler and its
public repository, robots.txt honoured for `*` AND the agent tokens on EVERY source, and no
contact at all with a host walled on the VPS. Public data only; nothing here adds a login, a key,
a paid API or a retry around a refusal.

THE BOX STANDS DOWN WHEN THE VPS FETCHED. Output the VPS shipped counts whether or not this box
adopted it: the transport ref `refs/remotes/intel-ship/send` (fetched hourly by MT5-IntelShip) is
read for each seat's newest shipped commit, so a VPS that is fetching and shipping is never
doubled by this clock even while adoption is broken. A VPS that fetches and ships NOTHING leaves
no trace this box can read; that case is named in the report (`vps_shipped.basis`), not guessed.

BOUNDED, AND NOTHING STARVES. The seed and external groups run side by side, each one unit at a
time in its own child (killed at the unit's bound). Units go stalest-first; a unit whose bound
does not fit the time left is DEFERRED -- not started, not cut -- and, being stalest, leads the
next hour. Progress is published after every unit.

    python side_channels/vps_seat_clock.py [--budget-s 1800] [--dry-run]
    python side_channels/vps_seat_clock.py --unit seed:darwinex          # child: one unit
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
ROOT = BASE.parent.parent
for _p in (str(HERE), str(BASE), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import box_rails  # noqa: E402
from libs.ops import seat_clocks  # noqa: E402

STATE = BASE / "data" / seat_clocks.BOX_STATE.name
REPORT = BASE / "reports" / "VPS_SEAT_CLOCK.json"

#: The leg's own wall budget per pass. hourly_cycle's LEG_BUDGET_SEC sits above it.
BUDGET_S = 1800.0
#: Child bounds. External channels already kill themselves at run_all_miners.MINER_TIMEOUT_S
#: (180 s); the rest is the interpreter importing 25 miner modules.
EXTERNAL_BOUND_S = 300.0
#: A seed source: request caps and 20 s timeouts bound it; the hunters carry their own budgets
#: (regional_survivor_hunters.RUN_BUDGET_S = 900 s).
SEED_BOUND_S = 600.0
SEED_BOUND_OVERRIDES: dict[str, float] = {"regional_survivors": 1200.0}
JOIN_BOUND_S = 300.0
#: A unit KILLED at its bound records no wall time, so a fixed bound would kill it forever. Each
#: kill raises its next bound by this factor, capped at BOUND_CAP_S (the pass budget: a bound
#: past it could never be started, and the seat would sit DEFERRED rather than RED-and-named).
BOUND_GROWTH = 1.5
BOUND_CAP_S = BUDGET_S
SHIP_REF = "refs/remotes/intel-ship/send"
SHIP_LOG_COMMITS = 400
RESULT_PREFIX = "SEAT_CLOCK_RESULT "


def _read(p: Path) -> dict[str, Any]:
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def _write(p: Path, doc: dict[str, Any]) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + f".{os.getpid()}.tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    os.replace(tmp, p)


def _now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def bound_s(unit: str, st: dict[str, Any] | None = None) -> float:
    """A unit's child bound: its default, or 1.5x its last complete run when that is longer, or
    BOUND_GROWTH x the bound it was last KILLED at (capped at BOUND_CAP_S) -- so a unit that
    needs longer than its default gets longer, rather than being killed at the same bound daily."""
    kind, _, name = unit.partition(":")
    base = EXTERNAL_BOUND_S if kind == "external" else SEED_BOUND_OVERRIDES.get(name, SEED_BOUND_S)
    last_ok = float((st or {}).get("last_ok_wall_s") or 0.0)
    killed = float((st or {}).get("killed_at_bound_s") or 0.0)
    grown = min(BOUND_CAP_S, BOUND_GROWTH * killed) if killed else 0.0
    return max(base, 1.5 * last_ok, grown)


def vps_shipped_ts(root: Path = ROOT, ref: str = SHIP_REF,
                   runner: Callable[..., Any] | None = None) -> tuple[dict[str, float], str]:
    """({seat: newest commit time on the VPS transport ref touching that seat}, basis).

    Read-only `git log` over the ref; never fetches. An unreadable ref is an empty map with its
    reason as the basis -- the plan then falls back to the files on disk, and says so."""
    runner = runner or subprocess.run
    cmd = ["git", "-C", str(root), "log", f"-n{SHIP_LOG_COMMITS}", "--format=@%ct",
           "--name-only", ref, "--", "desks/mt5/data/intelligence", "data/intelligence"]
    try:
        r = runner(cmd, capture_output=True, text=True, timeout=30, check=False)
    except Exception as exc:  # a basis, never a crash
        return {}, f"UNMEASURED: git log {ref}: {type(exc).__name__}: {exc}"[:300]
    if r.returncode != 0:
        return {}, f"UNMEASURED: git log {ref} exit {r.returncode}: {(r.stderr or '')[:200]}"
    out: dict[str, float] = {}
    ts = 0.0
    for line in (r.stdout or "").splitlines():
        line = line.strip()
        if line.startswith("@"):
            try:
                ts = float(line[1:])
            except ValueError:
                ts = 0.0
            continue
        parts = line.split("/")
        if "intelligence" in parts:
            i = parts.index("intelligence")
            if i + 2 < len(parts) and ts and ts > out.get(parts[i + 1], 0.0):
                out[parts[i + 1]] = ts
    return out, f"{ref}: newest shipped commit per seat over the last {SHIP_LOG_COMMITS} commits"


def last_touch(unit: str, state: dict[str, Any], desk: Path = BASE) -> float:
    """The later of the unit's newest output (any clock) and the box's last attempt; 0 = never."""
    out = seat_clocks.unit_last_output_ts(unit, desk) or 0.0
    started = seat_clocks._iso_ts((state.get(unit) or {}).get("last_started_at")) or 0.0
    return max(out, started)


def plan(state: dict[str, Any], now: float | None = None, desk: Path = BASE,
         cadence_h: float = seat_clocks.BOX_CADENCE_H,
         shipped: dict[str, float] | None = None) -> dict[str, list[str]]:
    """{"due": [...stalest first], "fresh": [...], "vps_fetched": [...]} over every unit.

    `vps_fetched` (a subset of `fresh`): units the box stands down from ONLY because the VPS
    transport shows it shipped their seats inside the cadence -- the box would otherwise run."""
    now = time.time() if now is None else now
    shipped = shipped or {}
    window = cadence_h * 3600.0
    order = seat_clocks.units()
    touch = {u: last_touch(u, state, desk) for u in order}
    vps = {u: max((shipped.get(s, 0.0) for s in seat_clocks.unit_seats(u)), default=0.0)
           for u in order}
    due = [u for u in order if now - max(touch[u], vps[u]) >= window]
    due.sort(key=lambda u: (max(touch[u], vps[u]), order.index(u)))
    stood = [u for u in order if u not in due and now - touch[u] >= window]
    return {"due": due, "fresh": [u for u in order if u not in due], "vps_fetched": stood}


# ------------------------------------------------------------------------------- child mode

def run_unit(unit: str) -> dict[str, Any]:
    """One unit, in this process, through its runner's normal path."""
    kind, _, name = unit.partition(":")
    # THE RAILS FIRST, before any miner module is imported: an honest UA, robots.txt for every
    # source, no walled host. The env var carries them into the children run_all_miners spawns.
    os.environ[box_rails.ENV] = "1"
    box_rails.install()
    if kind == "seed":
        import seed_miners
        res = seed_miners.run_and_save(only={name}, tail=False)
        rows = sum(int((v or {}).get("count") or 0) for v in res.values()
                   if isinstance(v, dict))
        return {"status": "OK", "rows": rows}
    if kind == "external":
        import run_all_miners
        res = run_all_miners.run_all_miners(only={name})
        r = res.get(name) or {}
        if r.get("error"):
            return {"status": "FAILED", "rows": 0, "error": str(r["error"])[:300]}
        return {"status": "OK", "rows": int(r.get("count") or 0)}
    if unit == "join:seed":
        import seed_miners
        seed_miners.join_stage()
        return {"status": "OK", "rows": 0}
    raise ValueError(f"unknown unit {unit!r}")


def _child_main(unit: str) -> int:
    t0 = time.monotonic()
    try:
        res = run_unit(unit)
    except Exception as exc:
        res = {"status": "FAILED", "error": f"{type(exc).__name__}: {exc}"[:300]}
    res["rails_refused"] = box_rails.refused()[:20]
    res["wall_s"] = round(time.monotonic() - t0, 1)
    print(RESULT_PREFIX + json.dumps(res, default=str), flush=True)
    return 0 if res.get("status") == "OK" else 1


# ------------------------------------------------------------------------------ parent pass

Runner = Callable[[list[str], float], tuple[int | None, str]]


def _default_runner(cmd: list[str], timeout_s: float) -> tuple[int | None, str]:
    try:
        from libs.ops.proctree import run as _run
    except Exception:
        _run = subprocess.run  # type: ignore[assignment]
    try:
        r = _run(cmd, capture_output=True, text=True, timeout=timeout_s, check=False,
                 cwd=str(BASE))
    except subprocess.TimeoutExpired:
        return None, ""
    return r.returncode, ((r.stdout or "") + (r.stderr or ""))[-4000:]


def _parse(tail: str) -> dict[str, Any]:
    for line in reversed(tail.splitlines()):
        if line.startswith(RESULT_PREFIX):
            try:
                d = json.loads(line[len(RESULT_PREFIX):])
                return d if isinstance(d, dict) else {}
            except ValueError:
                return {}
    return {}


def run_pass(budget_s: float = BUDGET_S, *, runner: Runner | None = None,
             now: float | None = None, write: bool = True) -> dict[str, Any]:
    runner = runner or _default_runner
    state = _read(STATE)
    shipped, ship_basis = vps_shipped_ts()
    p = plan(state, now, shipped=shipped)
    t0 = time.monotonic()
    lock = threading.Lock()
    rows: dict[str, dict[str, Any]] = {
        u: {"status": "VPS_FETCHED" if u in p["vps_fetched"] else "FRESH"} for u in p["fresh"]}

    def publish() -> None:
        if not write:
            return
        _write(STATE, state)
        _write(REPORT, {
            "at": _now_iso(), "budget_s": budget_s,
            "spent_s": round(time.monotonic() - t0, 1),
            "cadence_h": seat_clocks.BOX_CADENCE_H, "units": rows,
            "ran": sorted(u for u, r in rows.items() if r.get("status") in ("OK", "FAILED",
                                                                             "KILLED_AT_BOUND")),
            "deferred": sorted(u for u, r in rows.items() if r.get("status") == "DEFERRED"),
            "fresh": sorted(u for u, r in rows.items() if r.get("status") == "FRESH"),
            "vps_fetched": sorted(u for u, r in rows.items()
                                  if r.get("status") == "VPS_FETCHED"),
            "vps_shipped": {"basis": ship_basis, "seats": len(shipped)},
            "rails": {"user_agent": box_rails.USER_AGENT,
                      "robots_tokens": list(box_rails.ROBOTS_TOKENS)},
            "rule": ("a unit runs only when no clock (VPS or box) has produced its seats inside "
                     "the cadence; stalest first; a unit that does not fit is deferred, not cut"),
        })

    def one(unit: str, bound: float) -> dict[str, Any]:
        cmd = [sys.executable, "-u", str(Path(__file__).resolve()), "--unit", unit]
        s0 = time.monotonic()
        rc, tail = runner(cmd, bound)
        res = _parse(tail)
        if rc is None:
            res = {"status": "KILLED_AT_BOUND", "why": f"ran past its {bound:.0f}s bound"}
        elif not res:
            res = {"status": "OK" if rc == 0 else "FAILED",
                   "error": "" if rc == 0 else f"exit {rc}: {tail[-300:]}"}
        res["wall_s"] = round(time.monotonic() - s0, 1)
        res["bound_s"] = round(bound)
        return res

    def group(units: list[str], after: str | None) -> None:
        ran_ok = False
        for unit in units:
            with lock:
                st = state.setdefault(unit, {})
                bound = bound_s(unit, st)
            left = budget_s - (time.monotonic() - t0)
            if bound > left:
                with lock:
                    rows[unit] = {"status": "DEFERRED", "bound_s": round(bound),
                                  "left_s": round(left)}
                    publish()
                continue
            with lock:
                st["last_started_at"] = _now_iso()
                publish()
            res = one(unit, bound)
            with lock:
                rows[unit] = res
                st.update({"last_status": res["status"], "last_wall_s": res["wall_s"],
                           "last_rows": res.get("rows"), "last_at": _now_iso()})
                if res["status"] == "OK":
                    st["last_ok_at"] = st["last_at"]
                    st["last_ok_wall_s"] = res["wall_s"]
                    st.pop("killed_at_bound_s", None)
                    ran_ok = True
                elif res["status"] == "KILLED_AT_BOUND":
                    st["killed_at_bound_s"] = bound
                publish()
        if after and ran_ok and budget_s - (time.monotonic() - t0) >= JOIN_BOUND_S:
            res = one(after, JOIN_BOUND_S)
            with lock:
                rows[after] = res
                publish()

    seed = [u for u in p["due"] if u.startswith("seed:")]
    ext = [u for u in p["due"] if u.startswith("external:")]
    threads = [threading.Thread(target=group, args=(seed, "join:seed"), daemon=True),
               threading.Thread(target=group, args=(ext, None), daemon=True)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    with lock:
        publish()
    return {"due": p["due"], "units": rows,
            "ok": sum(1 for r in rows.values() if r.get("status") == "OK"),
            "failed": sum(1 for r in rows.values() if r.get("status") == "FAILED"),
            "killed": sum(1 for r in rows.values() if r.get("status") == "KILLED_AT_BOUND"),
            "deferred": sum(1 for r in rows.values() if r.get("status") == "DEFERRED")}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else "")
    ap.add_argument("--budget-s", type=float, default=BUDGET_S)
    ap.add_argument("--unit", default="", help="child mode: run ONE unit in-process")
    ap.add_argument("--dry-run", action="store_true", help="print the plan, run nothing")
    a = ap.parse_args(argv)
    if a.unit:
        return _child_main(a.unit)
    if a.dry_run:
        shipped, basis = vps_shipped_ts()
        p = plan(_read(STATE), shipped=shipped)
        print(f"vps shipped: {basis}")
        for u in p["vps_fetched"]:
            print(f"vps    {u}")
        for u in p["due"]:
            print(f"due    {u}")
        print(f"fresh  {len(p['fresh'])} unit(s)")
        return 0
    rep = run_pass(a.budget_s)
    print(f"VPS SEAT CLOCK  due={len(rep['due'])} ok={rep['ok']} failed={rep['failed']} "
          f"killed={rep['killed']} deferred={rep['deferred']} -> {REPORT}", flush=True)
    # A source that fetched and failed is a FETCH_FAILURE with its own row on disk, not a leg
    # failure; the leg fails only when a unit could not even be run.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

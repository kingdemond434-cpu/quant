#!/usr/bin/env python3
"""ORGAN DEATHS BY OOM ARE THE DESK'S LARGEST UNMEASURED LOSS OF RESEARCH THROUGHPUT.

WHY THIS EXISTS (2026-08-30, weekly gap-fixer). A hand read of the journal found **289 OOM kills
in 48 hours** across the fleet -- `quant-cadence` 46, `quant-auto-push` 19, `quant-external-panel`
16, `quant-coverage-ratchet` 10, `quant-certify-gauntlet` 9, `hourly-controller` 3 (the survivor
acquisition controller, killed in 2 of 4 consecutive hours), and `quant-suite-verdict` once after
burning 17min50s of CPU to produce nothing. Not one of these appears in any artifact, fence,
ratchet or the session-start desk-state block. The desk measured coverage to two decimals and did
not measure that a sixth of its organ runs were being destroyed mid-flight.

Under L1.28a an unmeasured loss COUNTS AS ZERO, and that is exactly how it behaved: every
downstream instrument read the *surviving* runs and called the fleet healthy. `check_unit_health`
restarts failed units and `check_memory_ceilings` audits ceilings, but neither counts kills, so
nothing could answer "how much work is the box destroying per day" -- the number a swap/RAM
decision has to be made on, and the reason that decision was never surfaced to the principal.

THE JUDGMENT THIS FENCE ADDS, which no other instrument on the desk computes -- the split that
decides WHICH repair is the right one:

  * SELF-LIMITED -- the unit died at or near its OWN `MemoryMax`. Its cgroup ceiling bound it;
    the kernel killed only it, nothing else was harmed. The repair is that unit: raise its
    ceiling or fix what it leaks. This is the DESIGNED, contained failure.
  * GLOBAL VICTIM -- the unit died well BELOW its own ceiling (or had none). The machine ran out
    of memory and the kernel chose a victim from the whole box; the dying unit is innocent and
    was merely resident when someone else's allocation tipped the box over. The repair is the
    BOX (swap, RAM, or de-synchronised scheduling), never the victim.

Reading a global victim as a unit defect sends every repair to the wrong place, which is why the
counts alone are not enough and this fence reports the split rather than a total. On the measured
sample the desk's kills are overwhelmingly the second kind: `quant-cadence` has a 1.2G ceiling and
dies at a 197-276M peak, `hourly-controller` has 600M and dies at 197M. The box carries 3814MB
with **zero swap**, so there is no reclaim path between "fits" and "something dies".

SCOPE. `memecoin-*` executes `~/.local/opt/memecoin-shadow`, a separate project on this shared
box; its kills are counted and NAMED as foreign, never demanded and never repaired here -- the
same boundary `check_unit_parity` draws, for the same reason. They are reported because a foreign
project's allocations are a real cause of THIS desk's global victims even though the fix is not
this repo's to make.

    .venv/bin/python scripts/check_oom_pressure.py     -> data/oom_pressure.json

Exit 2 when desk-owned organ runs destroyed in the last 24h exceed OOM_FLOOR_24H (a ratchet floor:
it may only fall). Exit 0 otherwise. Absence of journal access is reported as UNMEASURED and exits
2 -- "we cannot count it" and "it is fine" must never render identically (sealed core).
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "oom_pressure.json"

# Ratchet floor (L1.50): desk-owned organ runs destroyed per 24h. May only be lowered, never
# raised to fit a measurement. Seeded at 0 -- ANY destroyed desk organ run is a finding, because
# the desk has never before had a number here and "some is normal" is exactly the belief that
# kept 289 kills invisible for a fortnight.
OOM_FLOOR_24H = 0

# Foreign units: present on this shared box, not this repo's to schedule or repair. Named, not
# demanded. This is a PREFIX SEED for classification, not a scope limit -- any unit not matching
# is treated as desk-owned, so a new desk organ is covered the day it is installed.
FOREIGN_PREFIXES = ("memecoin-",)

_OOM_RE = re.compile(r"([\w.@\\-]+)\.service: The kernel OOM killer killed some processes")
_PEAK_RE = re.compile(r"([\w.@\\-]+)\.service: Consumed .*?([\d.]+)([KMG]) memory peak")
_SCALE = {"K": 1 / 1024, "M": 1.0, "G": 1024.0}


def _run(cmd: list[str], timeout: int = 120) -> tuple[int, str]:
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except (OSError, subprocess.SubprocessError):
        return 127, ""


def _journal(since: str) -> str:
    """Both scopes. The user manager logs its own units and the system manager logs the rest;
    reading only one hides half the fleet, which is how the first hand-count under-reported."""
    text = ""
    for cmd in (["journalctl", "--user", "--since", since, "--no-pager", "-o", "short-iso"],
                ["journalctl", "--since", since, "--no-pager", "-o", "short-iso"]):
        _rc, out = _run(cmd)
        text += out
    return text


def _mem_total_mb() -> float | None:
    try:
        m = re.search(r"MemTotal:\s+(\d+)", Path("/proc/meminfo").read_text("utf-8"))
        return round(int(m.group(1)) / 1024, 1) if m else None
    except OSError:
        return None


def _swap_total_mb() -> float | None:
    try:
        m = re.search(r"SwapTotal:\s+(\d+)", Path("/proc/meminfo").read_text("utf-8"))
        return round(int(m.group(1)) / 1024, 1) if m else None
    except OSError:
        return None


def _ceiling_mb(unit: str) -> float | None:
    """The unit's own MemoryMax in MB, or None when it is unbounded/unreadable. An unbounded
    unit can never be self-limited, so its kills are global by construction."""
    scope = "--user"  # memecoin-* are user units too; no root-scoped unit is readable here
    _rc, out = _run(["systemctl", scope, "show", f"{unit}.service", "-p", "MemoryMax",
                     "--value"], timeout=30)
    raw = out.strip()
    if not raw or raw == "infinity" or not raw.isdigit():
        return None
    return round(int(raw) / 2**20, 1)


def count_kills(text: str) -> tuple[dict[str, int], dict[str, float]]:
    """-> (kills per unit, max observed memory peak MB per unit).

    Peaks come from the `Consumed ... N memory peak` line systemd emits when the unit stops. It
    is the same cgroup's high-water mark, which is what a ceiling is compared against; pairing it
    with the kill count is what makes the self-limited/global split computable at all."""
    kills: dict[str, int] = defaultdict(int)
    peaks: dict[str, float] = defaultdict(float)
    for line in text.splitlines():
        m = _OOM_RE.search(line)
        if m:
            kills[m.group(1)] += 1
            continue
        p = _PEAK_RE.search(line)
        if p:
            unit, val, suffix = p.group(1), float(p.group(2)), p.group(3)
            mb = val * _SCALE.get(suffix, 1.0)
            if mb > peaks[unit]:
                peaks[unit] = round(mb, 1)
    return dict(kills), dict(peaks)


def classify(unit: str, peak_mb: float, ceiling_mb: float | None) -> str:
    """Self-limited only when the unit's own ceiling plausibly bound it. A unit killed at 16% of
    its ceiling was not bound by that ceiling under any reading, and calling it self-limited
    would send the repair to an innocent unit."""
    if ceiling_mb is None:
        return "global_victim"
    return "self_limited" if peak_mb >= 0.9 * ceiling_mb else "global_victim"


def _write_atomic(path: Path, doc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(doc, fh, indent=1)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def main() -> int:
    now = datetime.now(tz=UTC).isoformat(timespec="seconds")
    text_24h = _journal("24 hours ago")
    text_7d = _journal("7 days ago")

    if not text_24h and not text_7d:
        doc = {
            "checked_at": now, "status": "UNMEASURED",
            "why": "journalctl returned nothing for either scope -- OOM pressure is UNKNOWN, "
                   "which is not the same as zero and must never render as healthy (L1.28a).",
            "measuring_command": "scripts/check_oom_pressure.py",
        }
        _write_atomic(OUT, doc)
        print("oom pressure: UNMEASURED -- journal unreadable; this is not a clean verdict")
        return 2

    kills_24h, _peaks_24h = count_kills(text_24h)
    kills_7d, peaks_7d = count_kills(text_7d)

    rows = []
    desk_24h = foreign_24h = 0
    desk_global = desk_self = 0
    for unit, n in sorted(kills_7d.items(), key=lambda kv: -kv[1]):
        foreign = unit.startswith(FOREIGN_PREFIXES)
        peak = peaks_7d.get(unit, 0.0)
        ceiling = _ceiling_mb(unit)
        kind = classify(unit, peak, ceiling)
        n24 = kills_24h.get(unit, 0)
        if foreign:
            foreign_24h += n24
        else:
            desk_24h += n24
            if kind == "global_victim":
                desk_global += n24
            else:
                desk_self += n24
        rows.append({
            "unit": unit, "kills_24h": n24, "kills_7d": n,
            "peak_mb": peak, "ceiling_mb": ceiling, "kind": kind,
            "scope": "foreign" if foreign else "desk",
        })

    swap = _swap_total_mb()
    breach = desk_24h > OOM_FLOOR_24H
    doc = {
        "checked_at": now,
        "status": "BREACH" if breach else "OK",
        "desk_runs_destroyed_24h": desk_24h,
        "desk_runs_destroyed_7d": sum(r["kills_7d"] for r in rows if r["scope"] == "desk"),
        "desk_global_victims_24h": desk_global,
        "desk_self_limited_24h": desk_self,
        "foreign_kills_24h": foreign_24h,
        "floor_24h": OOM_FLOOR_24H,
        "mem_total_mb": _mem_total_mb(),
        "swap_total_mb": swap,
        "no_swap": swap == 0,
        "units": rows,
        "measuring_command": "scripts/check_oom_pressure.py",
    }
    _write_atomic(OUT, doc)

    print(f"oom pressure: {desk_24h} desk organ run(s) destroyed in 24h "
          f"({desk_global} global victim, {desk_self} self-limited), "
          f"{foreign_24h} foreign; floor {OOM_FLOOR_24H}")
    if swap == 0:
        print("  NO SWAP on this box -- there is no reclaim path between 'fits' and 'a unit "
              "dies'; every overshoot is a kill. Adding swap needs root (principal console).")
    for r in rows[:8]:
        if r["kills_24h"]:
            ceil = f"{r['ceiling_mb']:.0f}M" if r["ceiling_mb"] else "unbounded"
            print(f"  {r['kind'].upper():<14} {r['unit']}: {r['kills_24h']} kill(s)/24h, "
                  f"peak {r['peak_mb']:.0f}M vs ceiling {ceil} [{r['scope']}]")
    if desk_global:
        print(f"  {desk_global} of {desk_24h} desk kill(s) are GLOBAL victims -- the repair is "
              f"the BOX (swap/RAM/de-synchronised timers), not those units")
    return 2 if breach else 0


if __name__ == "__main__":
    sys.exit(main())

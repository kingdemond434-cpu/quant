#!/usr/bin/env python3
"""A LIVE TIMER THAT EXISTS ONLY ON THIS BOX IS ONE REBUILD FROM SILENCE.

WHY THIS EXISTS (2026-08-27). `ops/` carried 141 unit files and the box ran 81, and the two sets
were never compared. Measured: **17 timers were firing from `~/.config/systemd/user/` with no
committed copy anywhere in the repo** -- including `quant-mt5-suite` (the 551-test ratchet that
GAP 143 closed), `quant-universe-registry` (GAP 142's self-healing 20-minute cost repair),
`quant-doc-replay-fence` (GAP 157's rollback fence) and six research seats. The register records
all of them as WIRED. The script half was committed; the schedule half never was, so a fresh clone
or a rebuilt box schedules none of them and nothing would say so -- the same two-halves-by-
different-routes class as R0742, one layer down in the stack.

It also mis-taught the desk's own wiring instrument: `max_audit.check_orphan_scripts` globs
`ops/*` for reachability and cannot see `~/.config/systemd/user`, so five actively-scheduled
scripts (`check_desk_tasks`, `check_prompt_prefix`, `check_quota_resume`, `check_research_queue`,
`repair_universe_registry`) were reported as "referenced by NOTHING". Wiring debt measured through
a blind instrument reads as larger than it is in one place and smaller in another, and the real
orphans hide in the noise.

WHAT IT ASSERTS, in both directions:

  * a unit with a LIVE timer on this box and no committed copy -> UNVERSIONED (the defect above)
  * a committed unit that is INSTALLED but whose on-disk text has drifted from the repo -> DRIFTED
    (the box is running something the repo does not describe)

SCOPE IS THIS DESK'S FLEET. `memecoin-*` units execute `~/.local/opt/memecoin-shadow`, a separate
project that does not live in this repo; they are counted and named as foreign rather than
demanded, because a fence that orders another project's files into this repo would be wrong and
would be disabled within a week. Units present in `ops/` but not installed are NOT a defect --
the repo is the superset a box may draw from.

    .venv/bin/python scripts/check_unit_parity.py     -> data/unit_parity.json
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OPS = ROOT / "ops"
USER_UNITS = Path.home() / ".config" / "systemd" / "user"
OUT = ROOT / "data" / "unit_parity.json"

#: Units belonging to other projects on this box. Named, never silently skipped.
FOREIGN_PREFIXES = ("memecoin-",)


def _write_atomic(path: Path, doc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(doc, fh, indent=1, sort_keys=True)
        os.replace(tmp, path)
    finally:
        Path(tmp).unlink(missing_ok=True)


def live_timers() -> set[str] | None:
    """Timer unit names systemd will actually fire, or None if systemd cannot be asked.

    None is UNKNOWN and never the empty set: a box where `systemctl` does not answer is not a box
    with no timers, and treating it as one would report every committed unit as dead weight.
    """
    try:
        res = subprocess.run(["systemctl", "--user", "list-timers", "--all", "--no-legend"],
                             capture_output=True, text=True, timeout=60, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    if res.returncode != 0:
        return None
    return {tok for line in res.stdout.splitlines() for tok in line.split()
            if tok.endswith(".timer")}


def main() -> int:
    now = datetime.now(tz=UTC).isoformat(timespec="seconds")
    timers = live_timers()
    if timers is None:
        doc = {"checked_at": now, "status": "UNMEASURED",
               "why": "systemctl --user did not answer; unit parity is unknown, not clean"}
        _write_atomic(OUT, doc)
        print("unit parity: UNMEASURED -- systemctl --user did not answer")
        return 2

    committed = {p.name for p in OPS.glob("*.service")} | {p.name for p in OPS.glob("*.timer")}
    unversioned, drifted, foreign = [], [], []
    for timer in sorted(timers):
        service = timer.replace(".timer", ".service")
        if timer.startswith(FOREIGN_PREFIXES):
            foreign.append(timer)
            continue
        for name in (timer, service):
            installed = USER_UNITS / name
            if not installed.is_file():
                continue
            if name not in committed:
                unversioned.append(name)
            elif (OPS / name).read_text("utf-8") != installed.read_text("utf-8"):
                drifted.append(name)

    doc = {
        "checked_at": now,
        "status": "BREACH" if (unversioned or drifted) else "OK",
        "live_timers": len(timers),
        "committed_units": len(committed),
        "unversioned": unversioned,
        "drifted": drifted,
        "foreign_units_not_demanded": foreign,
        "measuring_command": "scripts/check_unit_parity.py",
    }
    _write_atomic(OUT, doc)

    print(f"unit parity: {len(timers)} live timer(s), {len(committed)} committed unit file(s)")
    for name in unversioned:
        print(f"  UNVERSIONED: {name} fires on this box and exists in no commit -- a rebuilt box "
              f"would not schedule it and nothing would say so")
    for name in drifted:
        print(f"  DRIFTED: {name} differs from ops/{name} -- the box is running something the "
              f"repo does not describe")
    if foreign:
        print(f"  foreign (named, not demanded): {', '.join(foreign)} -- these execute another "
              f"project on this box and are not this repo's to carry")
    return 1 if (unversioned or drifted) else 0


if __name__ == "__main__":
    sys.exit(main())

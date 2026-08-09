#!/usr/bin/env python3
"""IS THE DESK ACTUALLY RUNNING? -- production, not process status.

WHY THIS EXISTS, AND IT IS THE SAME LESSON THREE TIMES. `systemctl is-active` proves a process is
alive, never that it PRODUCED. This desk has been burned by that exact gap repeatedly: a panel that
exited clean and appended no verdict, an organ whose timer fired for weeks against a crashed
script, a watchdog that died on 2026-07-11 and left the pager silent and the forward clocks frozen
for ELEVEN AND A HALF DAYS while everything looked scheduled.

The failure is always the same shape -- the launcher is fine and the artifact is stale -- so the
question this asks is never "is it running" but "when did it last WRITE something".

AND THE GAP THAT PROMPTED IT. Auditing the repository's own deploy surface found that the desk's
main loop had no launcher at all: nothing started the cadence engine, the pager, the process
supervisor, or the Tier-3 ruin rail. Recorders and diggers had units; the organs that keep the
desk ALIVE did not. That is invisible to any check that only looks at the units which exist, so
this walks the FLOORS -- the freshness contract run_cadence itself enforces -- and asks of each
one: what writes this, what starts that, and when did it last happen?

THREE VERDICTS, AND THE MIDDLE ONE IS THE POINT:
  RUNNING    the artifact exists and is inside its floor
  STALE      it exists and is past its floor -- scheduled but not producing, the class above
  MISSING    it has never been written, or nothing in the repository starts its producer

Exit code is 1 if anything is MISSING or STALE, so this can gate a deploy rather than decorate it.
Read-only. No keys, no order paths.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

REPORT = ROOT / "data/deployment_verification.json"

#: artifact -> (max age hours, the unit that must produce it, what it means when it is stale).
#: The ages mirror run_cadence's own _FLOORS_S0 where they overlap; the rest are the cadence of
#: the organ that writes them. Nothing here is aspirational -- every entry names a producer that
#: exists in the repository.
FLOORS: dict[str, tuple[float, str, str]] = {
    "data/.last_alerts.json": (
        1.0, "quant-alerts.timer",
        "the pager has not ticked -- the desk cannot tell you anything is wrong"),
    "data/cadence_state.json": (
        2.0, "quant-cadence.timer",
        "the cadence engine has not run: the panel, the moat screen, survivor promotion and the "
        "forward-clock review all hang off this tick, and every one of them is owed"),
    "data/moat_mine.json": (
        6.0, "quant-moat-miner.service",
        "the moat miner is not converting tape into coverage"),
    "data/moat_screen.json": (
        6.0, "quant-moat-screen.service",
        "the survivor hunt is not running -- the archive is being recorded and never asked"),
    "data/max_audit_report.json": (
        30.0, "quant-daily-max.timer",
        "the daily maximisation sweep has not run, so nothing is auditing the desk"),
}

#: Tape roots: absence here is the upstream blocker every other moat defect resolves to.
TAPE = ("data/moat",)

#: Units that must be ENABLED for the above to be possible at all. `quant-deadman.service` is
#: deliberately absent: it moves funds and is Tier-3, so it is reported separately and never
#: required by an automated check.
REQUIRED_UNITS = (
    "quant-recorder-fut.service", "quant-recorder-spot.service", "quant-recorder-bybit.service",
    "quant-moat-miner.service", "quant-moat-screen.service",
    "quant-watchdog.timer", "quant-alerts.timer", "quant-cadence.timer", "quant-daily-max.timer",
)

TIER3 = ("quant-deadman.service",)


def _age_h(p: Path) -> float | None:
    try:
        return (time.time() - p.stat().st_mtime) / 3600.0
    except OSError:
        return None


def _systemctl(*args: str) -> str:
    try:
        r = subprocess.run(["systemctl", *args], capture_output=True, text=True, timeout=20,
                           check=False)
        return (r.stdout or r.stderr or "").strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def check_units() -> list[dict]:
    """Is each unit installed and enabled? Absent systemd (a dev box) reports UNKNOWN, not OK.

    Claiming a clean bill of health on a machine that cannot even answer the question is how a
    verifier becomes decoration.
    """
    have_systemd = bool(_systemctl("--version"))
    out = []
    for unit in REQUIRED_UNITS:
        if not have_systemd:
            out.append({"unit": unit, "state": "UNKNOWN",
                        "why": "no systemd on this host -- run this ON THE VPS"})
            continue
        enabled = _systemctl("is-enabled", unit) or "not-found"
        active = _systemctl("is-active", unit) or "unknown"
        ok = enabled.startswith("enabled")
        out.append({"unit": unit, "enabled": enabled, "active": active,
                    "state": "OK" if ok else "NOT-ENABLED",
                    "why": "" if ok else (
                        f"systemctl reports {enabled!r}. Installed unit files are not running "
                        "units -- `enable --now` is what survives a reboot.")})
    for unit in TIER3:
        p = ROOT / "ops" / unit
        st = _systemctl("is-enabled", unit) if have_systemd else ""
        out.append({"unit": unit, "state": "TIER-3", "enabled": st or "unknown",
                    "why": ("the ruin rail. This check NEVER requires it: it moves funds, so "
                            "arming it is the principal's act, not a script's. "
                            + ("unit file present" if p.exists() else "UNIT FILE MISSING"))})
    return out


def check_production() -> list[dict]:
    """The real question: when did each organ last WRITE something?"""
    out = []
    for rel, (max_h, unit, meaning) in sorted(FLOORS.items()):
        p = ROOT / rel
        age = _age_h(p)
        if age is None:
            out.append({"artifact": rel, "state": "MISSING", "unit": unit, "age_h": None,
                        "floor_h": max_h, "why": f"never written. {meaning}"})
        elif age > max_h:
            out.append({"artifact": rel, "state": "STALE", "unit": unit,
                        "age_h": round(age, 2), "floor_h": max_h,
                        "why": (f"{age:.1f}h old against a {max_h}h floor -- scheduled but not "
                                f"PRODUCING. {meaning}")})
        else:
            out.append({"artifact": rel, "state": "RUNNING", "unit": unit,
                        "age_h": round(age, 2), "floor_h": max_h, "why": ""})
    return out


def check_tape() -> list[dict]:
    """Is the archive GROWING? Every moat organ downstream resolves to this one fact."""
    out = []
    for rel in TAPE:
        root = ROOT / rel
        files = list(root.rglob("*.jsonl.gz")) if root.exists() else []
        total = sum(f.stat().st_size for f in files) if files else 0
        newest = max((f.stat().st_mtime for f in files), default=0.0)
        age = (time.time() - newest) / 3600.0 if newest else None
        if not files:
            out.append({"path": rel, "state": "MISSING", "files": 0,
                        "why": ("no tape at all. The recorders are the ONLY thing that writes "
                                "here, and no mining, screening or promotion action closes it. "
                                "This is the upstream blocker every moat defect resolves to.")})
        elif age is not None and age > 2.0:
            out.append({"path": rel, "state": "STALE", "files": len(files),
                        "bytes": total, "newest_age_h": round(age, 2),
                        "why": (f"{len(files)} files but the newest is {age:.1f}h old -- the "
                                "recorders have stopped. Every second unrecorded is permanently "
                                "unbuyable; this is the only cost on the desk money cannot fix "
                                "afterwards.")})
        else:
            out.append({"path": rel, "state": "RUNNING", "files": len(files), "bytes": total,
                        "newest_age_h": round(age, 2) if age is not None else None, "why": ""})
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true", help="artifact only, no human output")
    a = ap.parse_args()

    units, production, tape = check_units(), check_production(), check_tape()
    bad_units = [u for u in units if u["state"] == "NOT-ENABLED"]
    bad_prod = [p for p in production if p["state"] in ("MISSING", "STALE")]
    bad_tape = [t for t in tape if t["state"] in ("MISSING", "STALE")]
    ok = not (bad_units or bad_prod or bad_tape)

    out = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "verdict": "DEPLOYED" if ok else "INCOMPLETE",
        "units": units, "production": production, "tape": tape,
        "note": ("PRODUCTION, NOT PROCESS STATUS. `systemctl is-active` proves a process is alive "
                 "and never that it produced -- the failure that left this desk with a silent "
                 "pager and frozen forward clocks for 11.5 days while every timer looked healthy. "
                 "Every check here asks when an artifact was last WRITTEN."),
        "authority": "NONE. Reports. Starts nothing, enables nothing, moves no funds.",
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(out, indent=1, default=str), "utf-8")
    if a.json:
        print(json.dumps(out, indent=1, default=str))
        return 0 if ok else 1

    print(f"deployment: {out['verdict']}")
    print("\n  UNITS")
    for u in units:
        mark = {"OK": "ok  ", "NOT-ENABLED": "FAIL",
                "TIER-3": "t3  ", "UNKNOWN": "?   "}[u["state"]]
        print(f"    [{mark}] {u['unit']:<32} {u.get('enabled', '')}")
        if u["why"] and u["state"] != "OK":
            print(f"            {u['why'][:104]}")
    print("\n  PRODUCTION (when did it last WRITE?)")
    for p in production:
        mark = {"RUNNING": "ok  ", "STALE": "FAIL", "MISSING": "FAIL"}[p["state"]]
        age = f"{p['age_h']}h" if p["age_h"] is not None else "never"
        print(f"    [{mark}] {p['artifact']:<32} {age:>9} / {p['floor_h']}h floor")
        if p["why"]:
            print(f"            {p['why'][:104]}")
    print("\n  TAPE")
    for t in tape:
        mark = "ok  " if t["state"] == "RUNNING" else "FAIL"
        print(f"    [{mark}] {t['path']:<32} {t.get('files', 0)} files")
        if t["why"]:
            print(f"            {t['why'][:104]}")
    if ok:
        print("\n  Everything the repository can start is started and PRODUCING.")
    else:
        print(f"\n  {len(bad_units)} unit(s), {len(bad_prod)} artifact(s), {len(bad_tape)} tape "
              "root(s) not right. Fix these before believing any number this desk reports.")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

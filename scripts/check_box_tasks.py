#!/usr/bin/env python3
"""Can this repo still reconstitute the WINDOWS BOX -- the machine that touches money?

`ops/crontab.manifest` and `scripts/check_scheduler_manifest.py` answer that question for the VPS,
and answering it there was worth doing: 119 of 162 scripts had no in-repo scheduler reference and
the live crontab was uncommitted, so a GitHub restore yielded a desk that ran NOTHING. The box had
no equivalent at all.

MEASURED 2026-09-05 across the whole tree. Twenty-five `MT5-*` tasks are named in code.
`stall_watch.ps1` heals eight of them by name every ten minutes -- and FIVE OF THOSE EIGHT have no
installer anywhere in this repo: MT5-Gauntlet, MT5-Shadow, MT5-UniversalGate, MT5-QQuantShadow,
MT5-ResearchSupervisor. They exist only in one machine's task registry.

TWO CONSEQUENCES, both live rather than hypothetical:

  THE CADENCE IS UNVERIFIABLE. The standing requirement is that the gauntlet judges, the clocks
  advance and certificates mint EVERY HOUR. Nothing in this repo can confirm or deny that, because
  nothing declares when those tasks fire. "It runs hourly" has been an assumption for as long as
  the tasks have existed, and an assumption cannot be breached.

  A REBUILD SILENTLY LOSES THE RESEARCH LANE. Restore this repo onto a fresh box and the gateway,
  the deadman, the tape recorders and the dashboard come back -- they have installers. The
  gauntlet, the forward clocks, the universal gate and the supervisor do not come back at all,
  and `stall_watch` would report them missing, which reads identically to merely disabled.

WHAT THIS CHECKS, all repo-only so it runs anywhere:

  (a) every `MT5-*` task named anywhere in the tree has a manifest line -- a task the code heals,
      launches or references but the DR floor does not know about is tomorrow's silent loss;
  (b) every manifested `runs=` script exists in this repo -- a manifest pointing at a deleted
      script is a rebuild that produces a task which fails on its first tick;
  (c) every manifested `installer=` file exists -- same reason, one level up;
  (d) UNDECLARED triggers are COUNTED AND RATCHETED. This is the honest half: the repo does not
      know those cadences and nobody may invent one here, so the check reports how many remain and
      fails only when the number RISES. A new task must arrive with its trigger written down.

Exit: 2 on (a)/(b)/(c) or a ratchet breach; 0 clean. stdlib-only, no network, no box needed.

    python scripts/check_box_tasks.py [--json]
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "desks" / "mt5" / "ops" / "box_tasks.manifest"
REPORT = ROOT / "desks" / "mt5" / "reports" / "BOX_TASKS.json"

_TASK_LINE = re.compile(r'^TASK\s+(.*)$')
_KV = re.compile(r'(\w+)="([^"]*)"')
#: A REAL task name is CamelCase after the dash: `MT5-Gauntlet`, never `MT5-volume`. The loose
#: pattern matched prose and data ("MT5-volume", "MT5-valid") and reported three phantom tasks --
#: a fence whose first run is mostly false positives gets muted, which is the one outcome that
#: makes it worthless. Windows task names on this box are all CamelCase by convention.
_TASK_NAME = re.compile(r"MT5-[A-Z][a-z][A-Za-z0-9]*")

#: Files that MENTION task names without being a declaration -- the manifest itself, and this
#: checker. Everything else naming an `MT5-*` task is a real reference the manifest must cover.
_NOT_A_REFERENCE = {"desks/mt5/ops/box_tasks.manifest", "scripts/check_box_tasks.py"}

#: Extensions worth scanning: things that can REGISTER, LAUNCH or HEAL a task. Data and reports
#: are excluded on purpose -- the desk's crawlers mine text about MetaTrader products, so
#: `data/intelligence/*.json` is full of strings like `MT5-PropFirm`, `MT5-Telegram` and
#: `MT5-SMC` that are forum vocabulary rather than scheduled tasks. Reporting those as missing
#: DR coverage is how a fence earns its first mute.
_SCAN = (".ps1", ".py", ".cmd", ".bat")

#: Directories whose contents are OUTPUT, never a declaration. A task name appearing in something
#: this desk generated is not evidence that the task exists.
_NOT_A_DECLARATION = ("data/", "reports/", "desks/mt5/data/", "desks/mt5/reports/", "docs/",
                      "backups/", "web/")

#: Manifested tasks whose trigger this repo does not know. RATCHET: it may fall, never rise.
#: Fourteen today -- the five `stall_watch` heals with no installer, plus the deadman, the vol
#: archive, the moat trio and several data and ops tasks. Each one is a five-minute job on the box (`Get-ScheduledTask
#: -TaskName <name> | Select -Expand Triggers`) that turns a guess into a fact, and until then this
#: number is the honest measure of how much of the box cannot be rebuilt from here.
MAX_UNDECLARED = 14


def manifest_rows(path: Path | None = None) -> list[dict[str, str]]:
    p = MANIFEST if path is None else path
    rows: list[dict[str, str]] = []
    if not p.exists():
        return rows
    for line in p.read_text("utf-8").splitlines():
        m = _TASK_LINE.match(line.strip())
        if not m:
            continue
        rows.append(dict(_KV.findall(m.group(1))))
    return rows


def referenced_tasks(root: Path | None = None) -> dict[str, list[str]]:
    """Task name -> the repo files that name it. The set the manifest must cover."""
    base = ROOT if root is None else root
    out: dict[str, list[str]] = {}
    for path in base.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in _SCAN:
            continue
        rel = path.relative_to(base).as_posix()
        if rel in _NOT_A_REFERENCE or rel.startswith((".git/", "node_modules/", ".venv/")):
            continue
        if any(seg in rel for seg in _NOT_A_DECLARATION):
            continue
        try:
            text = path.read_text("utf-8", errors="ignore")
        except OSError:
            continue
        for name in set(_TASK_NAME.findall(text)):
            out.setdefault(name, []).append(rel)
    return out


def check(root: Path | None = None) -> dict[str, object]:
    base = ROOT if root is None else root
    rows = manifest_rows()
    named = {r.get("name", "") for r in rows}
    refs = referenced_tasks(base)

    missing = sorted(n for n in refs if n and n not in named)
    bad_runs = sorted(f"{r['name']} -> {r.get('runs')}" for r in rows
                      if r.get("runs") and r["runs"] != "UNKNOWN"
                      and not r["runs"].endswith(".exe")
                      and not (base / r["runs"]).exists())
    bad_installers = sorted(f"{r['name']} -> {r.get('installer')}" for r in rows
                            if r.get("installer") not in ("", "NONE", None)
                            and not (base / str(r["installer"])).exists())
    undeclared = sorted(r["name"] for r in rows if r.get("trigger") == "UNDECLARED")
    no_installer = sorted(r["name"] for r in rows if r.get("installer") == "NONE")
    healed = sorted(n for n in refs
                    if any(f.endswith("stall_watch.ps1") for f in refs[n]))
    healed_uninstallable = sorted(set(healed) & set(no_installer))

    problems: list[str] = []
    for n in missing:
        problems.append(f"MT5 task {n} is referenced in {refs[n][0]} and has no manifest line: "
                        f"the DR floor does not know it exists")
    for r in bad_runs:
        problems.append(f"manifest points at a script that is not in this repo: {r}")
    for r in bad_installers:
        problems.append(f"manifest points at an installer that is not in this repo: {r}")
    if len(undeclared) > MAX_UNDECLARED:
        problems.append(f"{len(undeclared)} tasks carry trigger=UNDECLARED, above the ratchet of "
                        f"{MAX_UNDECLARED}. A new task must arrive with its cadence written down "
                        f"-- never invent one here: {undeclared}")

    return {
        "manifested": len(rows), "referenced": len(refs),
        "missing_from_manifest": missing,
        "runs_not_in_repo": bad_runs, "installers_not_in_repo": bad_installers,
        "undeclared_triggers": undeclared, "undeclared_ratchet": MAX_UNDECLARED,
        "no_installer": no_installer,
        "healed_but_uninstallable": healed_uninstallable,
        "status": "BREACH" if problems else ("RATCHETED" if undeclared else "OK"),
        "problems": problems,
        "note": ("`healed_but_uninstallable` is the sharp end: `stall_watch` restarts these by "
                 "name every ten minutes, and a fresh box would never have them at all."),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    out = check()
    try:
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(json.dumps(out, indent=1), "utf-8")
    except OSError:
        pass
    if args.json:
        print(json.dumps(out, indent=1))
    else:
        print(f"box tasks: {out['manifested']} manifested, {len(out['undeclared_triggers'])} "
              f"UNDECLARED (ratchet {MAX_UNDECLARED}) -- {out['status']}")
        if out["healed_but_uninstallable"]:
            print(f"  healed by stall_watch, absent from a fresh box: "
                  f"{', '.join(out['healed_but_uninstallable'])}")
        for p in out["problems"]:
            print(f"  BREACH {p}")
    return 2 if out["problems"] else 0


if __name__ == "__main__":
    raise SystemExit(main())

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
  (e) every installer trigger the repo can RESOLVE agrees with the task's manifest period. An
      installer registered MT5-QQuantGatesCertify daily at 23:00 against a manifest "every 1 hour"
      (found 2026-10-14): a reinstall would have made the certifier's 180-minute contract red for
      good. Triggers built by `New-ManifestTrigger` read the manifest itself and always agree;
      an installer whose trigger cannot be resolved here is counted, never guessed;
  (d) UNDECLARED triggers are COUNTED AND RATCHETED. This is the honest half: the repo does not
      know those cadences and nobody may invent one here, so the check reports how many remain and
      fails only when the number RISES. A new task must arrive with its trigger written down.

Exit: 2 on (a)/(b)/(c)/(e) or a ratchet breach; 0 clean. stdlib-only, no network, no box needed.

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
#: makes it worthless. Windows task names on this box are all CamelCase by convention -- but an
#: acronym may lead (`MT5-FTMOFollow`) and a digit may sit inside (`MT5-E8WindowGuard`), so the
#: rule is "starts upper-case, carries at least one lower-case letter", never "upper then lower".
_TASK_NAME = re.compile(r"MT5-[A-Z][A-Za-z0-9]*[a-z][A-Za-z0-9]*")
#: Names shaped like a task that are not one: the git-writer MUTEX both box writers hold.
_NOT_A_TASK = frozenset({"MT5-GitWriter"})

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
                      "backups/", "web/", "tests/", "scratch/")

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
            if name in _NOT_A_TASK:
                continue
            out.setdefault(name, []).append(rel)
    return out


#: One continued PowerShell statement: a line plus every line its trailing backtick continues.
_PS_STMT = r"(?:[^\n]*`[ \t]*\r?\n)*[^\n]*"
_REP = re.compile(r"-RepetitionInterval\s*\(?\s*New-TimeSpan\s+-(Hours|Minutes)\s+(\d+)")


def manifest_period_min(trigger: str) -> int | None:
    """A manifest trigger's period in minutes, or None for a shape this check does not compare
    (resident, at startup, windows, UNDECLARED)."""
    t = trigger.strip().lower()
    if re.match(r"daily\b", t):
        return 1440
    if re.match(r"hourly\b", t):
        return 60
    m = re.match(r"every (\d+) (minute|hour)s?\b", t)
    if m:
        return int(m.group(1)) * (60 if m.group(2) == "hour" else 1)
    return None


def _ps_period_min(text: str) -> int | None:
    """The period a PowerShell trigger construction fires at: its repetition when it has one,
    else 1440 for a bare -Daily. None when it is neither (at logon, at startup, unresolved)."""
    m = _REP.search(text)
    if m:
        return int(m.group(2)) * (60 if m.group(1) == "Hours" else 1)
    if re.search(r"-Daily\b", text):
        return 1440
    return None


def _literal_task_name(text: str, var: str) -> str | None:
    """`$var`'s value when every assignment to it in the file is the same string literal (a
    `param()` default or a plain `$TaskName = 'MT5-X'`), else None: a loop variable, or one also
    assigned a computed value, never resolves."""
    rhs = re.findall(r"\$" + re.escape(var) + r"\s*=(?!=)\s*([^\n]*)", text)
    lits = [re.match(r"[\"']([^\"'$]+)[\"']", r) for r in rhs]
    vals = {m.group(1) for m in lits if m}
    return vals.pop() if lits and all(lits) and len(vals) == 1 else None


def installer_scan(root: Path | None = None) -> tuple[dict[str, list[tuple[str, int | None]]],
                                                       list[str]]:
    """(task name -> [(installer, period in minutes, or -1 for "from the manifest")],
    registrations this file could NOT resolve, as "path:line").

    Resolves `Register-ScheduledTask -TaskName "<name>"|$var ... -Trigger $t|(New-...Trigger ...)`
    with `$var` a single string literal in the same file and `$t` built there (plus its
    `.Repetition` override), and task-table entries `Name = "<name>" ... Trigger = { ... }`.
    Everything else (a loop over a table of names, a trigger built elsewhere) is listed as
    unresolved, so the blind spot is a measured, ratcheted number and never a silent one."""
    base = ROOT if root is None else root
    out: dict[str, list[tuple[str, int | None]]] = {}
    unresolved: list[str] = []
    for path in sorted((base / "desks" / "mt5").rglob("*.ps1")):
        rel = path.relative_to(base).as_posix()
        try:
            text = path.read_text("utf-8", errors="ignore")
        except OSError:
            continue
        for reg in re.finditer(r"(?m)^[ \t]*Register-ScheduledTask" + _PS_STMT, text):
            stmt = reg.group(0)
            where = f"{rel}:{text.count(chr(10), 0, reg.start()) + 1}"
            lit = re.search(r"-TaskName\s+[\"']([^\"']+)[\"']", stmt)
            ref = re.search(r"-TaskName\s+\$(\w+)\b(?!\.)", stmt)
            name = lit.group(1) if lit else (_literal_task_name(text, ref.group(1)) if ref else None)
            inline = re.search(r"-Trigger\s+\((New-\w+Trigger[^)]*)\)", stmt)
            var = re.search(r"-Trigger\s+\$(\w+)", stmt)
            if not name or not (inline or var):
                unresolved.append(where)
                continue
            if inline:
                out.setdefault(name, []).append((rel, _ps_period_min(inline.group(1))))
                continue
            assert var is not None
            before = text[:reg.start()]
            builds = list(re.finditer(r"\$" + var.group(1) + r"\s*=\s*(New-\w+Trigger" + _PS_STMT
                                      + ")", before))
            if not builds:
                unresolved.append(where)
                continue
            build = builds[-1]
            if build.group(1).startswith("New-ManifestTrigger"):
                out.setdefault(name, []).append((rel, -1))
                continue
            rep = re.search(r"\$" + var.group(1) + r"\.Repetition\s*=" + _PS_STMT,
                            before[build.end():])
            out.setdefault(name, []).append(
                (rel, _ps_period_min(build.group(1) + (rep.group(0) if rep else ""))))
        for entry in re.finditer(r"Name\s*=\s*[\"'](MT5-[A-Za-z0-9]+)[\"']", text):
            nxt = re.search(r"\bName\s*=", text[entry.end():])
            block = text[entry.end():entry.end() + (nxt.start() if nxt else len(text))]
            trig = re.search(r"Trigger\s*=\s*\{(" + _PS_STMT + ")", block)
            if trig:
                out.setdefault(entry.group(1), []).append((rel, _ps_period_min(trig.group(1))))
    return out, unresolved


def installer_triggers(root: Path | None = None) -> dict[str, list[tuple[str, int | None]]]:
    """Task name -> [(installer, period in minutes, or -1 for "from the manifest")]."""
    return installer_scan(root)[0]


#: Installer/manifest cadence disagreements that were already on the tree when (e) was written
#: (2026-10-14), as task -> the period in minutes the installer registers TODAY. Which side is right
#: is a fact about the box, not something to settle here: the installer's 5-minute MT5-DeskState,
#: for one, is deliberate (reboot_drill fails a desk_state older than 900 s). Manifest periods:
#: AllocatorFast 15, DeskState 15, MoatRecorder 30, ResearchSupervisor 30, Shadow 60.
#: DOWNWARD RATCHET: an entry exempts only that exact installer period, so a second change to a
#: listed task is a breach; an entry that no longer resolves to its recorded drift (fixed, or the
#: registration moved) is a breach until it is deleted; the list never grows past
#: MAX_KNOWN_TRIGGER_DRIFT.
KNOWN_TRIGGER_DRIFT: dict[str, int] = {
    "MT5-AllocatorFast": 5,
    "MT5-DeskState": 5,
    "MT5-MoatRecorder": 10,
    "MT5-ResearchSupervisor": 5,
    "MT5-Shadow": 15,
}
MAX_KNOWN_TRIGGER_DRIFT = 5
#: The fence's measured blind spot (2026-10-14), ratcheted so it can only shrink. UNRESOLVED:
#: registrations whose name or trigger is built in a loop over a table (tape, CRO lanes, E8,
#: register_absent, and Install-QuantWindows' own task-table loop, whose entries ARE compared
#: through their `Name = ... Trigger = {}` blocks). UNCOMPARED: resolved tasks with no manifest
#: period to compare against (resident, at startup, at logon, or no manifest row).
MAX_UNRESOLVED_REGISTRATIONS = 5
MAX_UNCOMPARED_TRIGGERS = 11


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

    drift: list[str] = []
    uncompared: list[str] = []
    still_drifting: set[str] = set()
    triggers, unresolved = installer_scan(base)
    for name, regs in sorted(triggers.items()):
        row = next((r for r in rows if r.get("name") == name), None)
        want = manifest_period_min(str(row.get("trigger", ""))) if row else None
        for rel, got in regs:
            if want is None or got is None:
                uncompared.append(f"{name} ({rel}): installer "
                                  f"{'unresolved' if got is None else f'{got} min'}, manifest "
                                  f"{repr(row.get('trigger')) if row else 'has no row'}")
            elif got != -1 and got != want:
                if KNOWN_TRIGGER_DRIFT.get(name) == got:
                    still_drifting.add(name)
                else:
                    drift.append(f"{name}: {rel} registers every {got} min, the manifest says "
                                 f"every {want} min")
    stale_drift = sorted(set(KNOWN_TRIGGER_DRIFT) - still_drifting)

    problems: list[str] = []
    for d in drift:
        problems.append(f"installer trigger disagrees with the manifest -- {d}")
    for n in stale_drift:
        problems.append(f"KNOWN_TRIGGER_DRIFT[{n!r}] no longer resolves to its recorded "
                        f"{KNOWN_TRIGGER_DRIFT[n]}-min drift: delete the entry")
    if len(KNOWN_TRIGGER_DRIFT) > MAX_KNOWN_TRIGGER_DRIFT:
        problems.append(f"KNOWN_TRIGGER_DRIFT holds {len(KNOWN_TRIGGER_DRIFT)} entries, above "
                        f"its ratchet of {MAX_KNOWN_TRIGGER_DRIFT}: fix the drift, never list it")
    if len(unresolved) > MAX_UNRESOLVED_REGISTRATIONS:
        problems.append(f"{len(unresolved)} Register-ScheduledTask sites the trigger check cannot "
                        f"resolve, above the ratchet of {MAX_UNRESOLVED_REGISTRATIONS}: "
                        f"{unresolved}")
    if len(uncompared) > MAX_UNCOMPARED_TRIGGERS:
        problems.append(f"{len(uncompared)} installer triggers with no manifest period to compare, "
                        f"above the ratchet of {MAX_UNCOMPARED_TRIGGERS}: {uncompared}")
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
        "no_installer": no_installer, "installer_trigger_drift": drift,
        "known_trigger_drift": KNOWN_TRIGGER_DRIFT, "stale_known_trigger_drift": stale_drift,
        "unresolved_registrations": unresolved, "uncompared_triggers": uncompared,
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

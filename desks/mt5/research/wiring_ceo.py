"""THE WIRING CEO -- every build the desk has made must be on a clock and used; this hunts the rest.

THE PRINCIPAL'S ORDER (2026-09-16): "make sure everything built so far is actually wired and
used; anything you find unwired you wire; always hunting; and the CEO must do this too as a
daily task, since our system is growing faster than wiring and using builds is."

WHY THE EXISTING AUDIT WAS NOT ENOUGH. `libs.ops.wiring_audit` finds a libs module nothing
imports, and one whose only importer is a script nothing runs. Measured 2026-09-16 it was blind
to the class that actually accumulated: an ORGAN under desks/mt5 with a `main()` and tests whose
importer exists and is reachable -- and sits on no clock. trajectory.py, lineage_dag.py,
novelty_v2.py, tri_alignment.py, research_os/surrogate.py, regime_discovery.py and
run_research_loop.py were all "wired" by that audit's lights and had never run on the box.
Unwired or idle is a defect (LAWS III.16): a build that runs nowhere has produced nothing.

WHAT THIS DOES, EVERY DAY AND EVERY CORE HOUR.
  1. Enumerates every ORGAN: a .py file with `def main(` under desks/mt5/research,
     desks/mt5/scripts, desks/mt5/frontier_intel, desks/mt5/side_channels, scripts/ and
     libs/research_os.
  2. Enumerates every CLOCK the repo declares: the hourly and daily cycles (their `_producer`
     paths and their imports), desks/mt5/ops/box_tasks.manifest `runs=`, ops/*.timer + .service
     ExecStart, ops/crontab.manifest, and every .cmd/.ps1/.sh under ops/ and desks/mt5/scripts.
  3. An organ is SCHEDULED when a clock names its path, its `-m` module or its bare module name
     (the cycles import desk organs by bare name), or when a scheduled organ imports it.
  4. Everything else is UNWIRED. Each gets a docket task with a suggested clock, and the ones
     that can run standalone (a `main()` that takes `--dry-run`, or no required arguments) go
     on PROBATION: `probation_runner` (heavy plan, hourly) exercises them in rotation with a
     bounded budget so that "built" becomes "runs on a clock and leaves an artifact" the same
     day it lands, without anyone editing the cycle by hand. Promotion from probation to a
     named leg is a docket task with the evidence attached (clean runs, artifact written).
  5. A RATCHET: data/wiring_floor.json records the unwired count; it may fall, never rise. A
     rise is reported as BREACH in the artifact and on the CEO docket -- a new organ must arrive
     with its clock, and the closed-loop attestation reads this flag.

The CEO docket (frontier_ceo) carries the top wiring tasks every hour, so the desk's own
research controller is the one asking "what did we build that nothing runs?" -- daily, by rule.
"""
from __future__ import annotations

import argparse
import ast
import contextlib
import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
OUT = DESK / "reports" / "WIRING_CEO.json"
FLOOR = DESK / "data" / "wiring_floor.json"
PROBATION_QUEUE = DESK / "data" / "probation_queue.json"
PROBATION_STATE = DESK / "data" / "probation_state.json"
AUTO_LEGS = DESK / "data" / "auto_legs.json"
#: An organ is CLOCKED automatically once probation has seen it run clean once; it runs on the
#: core plan when its measured run stays under this, on the heavy plan otherwise.
AUTO_CORE_MAX_S = 60.0
AUTO_CORE_MIN_CLEAN = 3

ORGAN_AREAS: tuple[str, ...] = ("desks/mt5/research", "desks/mt5/scripts",
                                "desks/mt5/frontier_intel", "desks/mt5/side_channels",
                                "scripts", "libs/research_os")
CLOCK_FILES: tuple[str, ...] = ("desks/mt5/research/hourly_cycle.py",
                                "desks/mt5/research/daily_cycle.py",
                                "desks/mt5/ops/box_tasks.manifest", "ops/crontab.manifest")
CLOCK_AREAS: tuple[str, ...] = ("ops", "desks/mt5/scripts", "desks/mt5/recorders", "deploy")
CLOCK_SUFFIXES: tuple[str, ...] = (".timer", ".service", ".cmd", ".ps1", ".sh", ".manifest")
#: Organs that are unscheduled ON PURPOSE, each with the reason (an entry without one is not one).
EXEMPT: dict[str, str] = {
    "scripts/learn.py": "a CLI a person runs to add a lesson",
    "scripts/lessons.py": "a CLI a person runs to search lessons",
    "scripts/vault_search.py": "a CLI a person runs to search the vault",
    "scripts/build_lesson_vault.py": "a derived view a person regenerates",
    "scripts/max_audit.py": "the audit a person runs before a push",
    "desks/mt5/scripts/install_adopt_release_task.ps1": "one-time installer",
}
#: Never put on probation: they move money, seal releases or edit the tree.
NEVER_PROBATION: tuple[str, ...] = ("gateway", "e8_", "promoter", "run_gateway", "adopt", "seal",
                                    "release", "deadman", "kill", "close", "order", "executor",
                                    "install", "reboot", "no_log", "reclaim", "delete", "wipe",
                                    "prune", "rotate", "migrate", "sync_", "push", "commit")
PROBATION_BUDGET_S = 120
PROBATION_PER_PASS = 8


def _rel(p: Path) -> str:
    return p.relative_to(ROOT).as_posix()


def organs() -> dict[str, Path]:
    """rel path -> file, for every .py under ORGAN_AREAS that defines main()."""
    out: dict[str, Path] = {}
    for area in ORGAN_AREAS:
        base = ROOT / area
        if not base.is_dir():
            continue
        for p in sorted(base.glob("*.py")):
            if p.name.startswith("_") or "test" in p.name.lower():
                continue
            try:
                text = p.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if re.search(r"^def main\(", text, re.M):
                out[_rel(p)] = p
    return out


def _clock_texts() -> list[tuple[str, str]]:
    """(rel path, text) of every file that can put an organ on a clock."""
    texts: list[tuple[str, str]] = []
    seen: set[Path] = set()
    for rel in CLOCK_FILES:
        p = ROOT / rel
        if p.is_file():
            seen.add(p)
            with contextlib.suppress(OSError):
                texts.append((rel, p.read_text(encoding="utf-8", errors="replace")))
    for area in CLOCK_AREAS:
        base = ROOT / area
        if not base.is_dir():
            continue
        for p in sorted(base.rglob("*")):
            if p in seen or not p.is_file() or p.suffix.lower() not in CLOCK_SUFFIXES:
                continue
            try:
                texts.append((_rel(p), p.read_text(encoding="utf-8", errors="replace")))
            except OSError:
                continue
    return texts


def _local_imports(path: Path) -> set[str]:
    """Bare module names a desk file imports (`import deepening_worker`, `from x import y`)."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, SyntaxError):
        return set()
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            out.add(node.module.split(".")[-1])
            out.add(node.module.split(".")[0])
    return out


def scheduled(orgs: dict[str, Path]) -> tuple[dict[str, list[str]], list[tuple[str, str]]]:
    """rel path -> the clock files that name it (directly, or through a scheduled importer)."""
    texts = _clock_texts()
    named: dict[str, list[str]] = {}
    for rel, p in orgs.items():
        stem = p.stem
        needles = (rel, rel.replace("/", "\\"), p.name,
                   rel.split("/", 2)[-1] if rel.startswith("desks/mt5/") else rel)
        mod_forms = (f"-m {stem}", f"import {stem}", f"from {stem} import",
                     f"research.{stem}", f"frontier_intel.{stem}", f"side_channels.{stem}",
                     f"research_os.{stem}", f"scripts.{stem}")
        hits = [crel for crel, text in texts
                if any(n in text for n in needles) or any(m in text for m in mod_forms)]
        if hits:
            named[rel] = hits
    # transitive: an organ imported (by bare name) by a scheduled organ is scheduled too.
    # Imports are parsed ONCE per organ (the first draft re-parsed every file on every pass and
    # took minutes on 400 organs); the closure then runs on stems alone.
    imports = {rel: _local_imports(p) for rel, p in orgs.items()}
    by_stem: dict[str, list[str]] = {}
    for rel, p in orgs.items():
        by_stem.setdefault(p.stem, []).append(rel)
    frontier = list(named)
    while frontier:
        rel = frontier.pop()
        for imp in imports.get(rel, ()):
            for other in by_stem.get(imp, ()):
                if other not in named:
                    named[other] = [f"imported by {rel}"]
                    frontier.append(other)
    return named, texts


def _tested(orgs: dict[str, Path]) -> set[str]:
    """Organs some test names (by module stem). Each test file is tokenised once."""
    stems: dict[str, list[str]] = {}
    for rel, p in orgs.items():
        stems.setdefault(p.stem, []).append(rel)
    out: set[str] = set()
    word = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
    for base in (ROOT / "tests", ROOT / "desks" / "mt5" / "tests"):
        if not base.is_dir():
            continue
        for t in base.rglob("test_*.py"):
            try:
                tokens = set(word.findall(t.read_text(encoding="utf-8", errors="replace")))
            except OSError:
                continue
            for stem in tokens & stems.keys():
                out.update(stems[stem])
    return out


def _probation_ok(rel: str, p: Path) -> tuple[bool, str]:
    low = rel.lower()
    if any(tok in low for tok in NEVER_PROBATION):
        return False, "touches money, releases or the tree: never exercised blind"
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False, "unreadable"
    if "--dry-run" in text:
        return True, "main() takes --dry-run"
    if "add_argument(" in text and "required=True" in text:
        return False, "main() requires arguments this hunter cannot invent"
    return True, "main() runs standalone"


def _suggest_clock(rel: str, lines: int) -> str:
    if rel.startswith("scripts/check_") or rel.startswith("desks/mt5/scripts/check_"):
        return "hourly_cycle:core (a checker is cheap and belongs on the core plan)"
    if lines > 900:
        return "hourly_cycle:heavy (large organ; budget it with research_budget)"
    return "hourly_cycle:core if it finishes under 90 s, else heavy"


def auto_legs(probation: list[dict[str, Any]], state: dict[str, Any] | None = None,
              ) -> list[dict[str, Any]]:
    """THE WIRER (principal 2026-09-16: "an hourly organ wirer ... which always spots and does
    exactly these things"). Every probation-eligible organ that probation has run clean at
    least once becomes a real hourly leg: `argv` (its own `--dry-run` when it takes one), a
    budget, and a PLAN -- core when its measured runs stay under AUTO_CORE_MAX_S for
    AUTO_CORE_MIN_CLEAN clean runs, heavy otherwise. hourly_cycle.run_auto_legs executes them
    as costed legs, so they get the ledger row, the provenance envelope and the artifact check
    every named leg gets. Nothing here edits the cycle's code; the clock is data."""
    st = state if state is not None else _read(PROBATION_STATE)
    hist = st.get("history") if isinstance(st.get("history"), dict) else {}
    out: list[dict[str, Any]] = []
    for row in probation:
        organ = str(row.get("organ") or "")
        h = hist.get(organ) if isinstance(hist.get(organ), dict) else None
        if not h or int(h.get("clean", 0) or 0) < 1:
            continue
        secs = h.get("seconds") if isinstance(h.get("seconds"), (int, float)) else None
        core = (int(h.get("clean", 0) or 0) >= AUTO_CORE_MIN_CLEAN and secs is not None
                and float(secs) <= AUTO_CORE_MAX_S)
        out.append({"organ": organ, "leg": "auto_" + Path(organ).stem,
                    "argv": ["--dry-run"] if row.get("dry_run") else [],
                    "budget_s": int(row.get("budget_s") or PROBATION_BUDGET_S),
                    "plan": "core" if core else "heavy",
                    "clean_runs": int(h.get("clean", 0) or 0), "seconds": secs})
    return out


def _read(p: Path) -> dict[str, Any]:
    try:
        d = json.loads(p.read_text(encoding="utf-8-sig"))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def build(apply: bool = False) -> dict[str, Any]:
    orgs = organs()
    named, _texts = scheduled(orgs)
    tested = _tested(orgs)
    unwired: list[dict[str, Any]] = []
    probation: list[dict[str, Any]] = []
    for rel, p in sorted(orgs.items()):
        if rel in named or rel in EXEMPT:
            continue
        try:
            lines = len(p.read_text(encoding="utf-8", errors="replace").splitlines())
        except OSError:
            lines = 0
        ok, why = _probation_ok(rel, p)
        row = {"organ": rel, "lines": lines, "has_tests": rel in tested,
               "suggested_clock": _suggest_clock(rel, lines),
               "probation": ok, "probation_why": why,
               "task": (f"wire {rel}: register it as a leg or task (suggested "
                        f"{_suggest_clock(rel, lines).split(' ')[0]}) and give it an artifact")}
        unwired.append(row)
        if ok:
            probation.append({"organ": rel, "dry_run": "--dry-run" in why,
                              "budget_s": PROBATION_BUDGET_S})
    unwired.sort(key=lambda r: (not r["has_tests"], -r["lines"]))
    # the ratchet
    prev = None
    try:
        prev = json.loads(FLOOR.read_text(encoding="utf-8-sig")).get("unwired")
    except (OSError, ValueError, AttributeError):
        prev = None
    n = len(unwired)
    breach = isinstance(prev, int) and n > prev
    legs = auto_legs(probation)
    doc = {
        "at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "n_organs": len(orgs), "n_scheduled": len(named), "n_unwired": n,
        "n_probation": len(probation), "n_exempt": len(EXEMPT),
        "floor": {"previous": prev, "now": n, "status": "BREACH" if breach else
                  ("RATCHETED" if isinstance(prev, int) and n < prev else "HELD"),
                  "rule": ("the unwired count may fall, never rise; a new organ arrives with "
                           "its clock")},
        "unwired": unwired[:200],
        "probation": probation[:200],
        "auto_legs": {"n": len(legs), "core": sum(1 for x in legs if x["plan"] == "core"),
                      "heavy": sum(1 for x in legs if x["plan"] == "heavy"),
                      "rule": ("clocked as a real hourly leg after one clean probation run; "
                               f"core when measured under {AUTO_CORE_MAX_S:.0f}s for "
                               f"{AUTO_CORE_MIN_CLEAN} clean runs, heavy otherwise")},
        "exempt": EXEMPT,
        "scheduled_sample": {k: v[:3] for k, v in list(named.items())[:40]},
        "rule": ("an organ is wired only when a clock names it or a scheduled organ imports it; "
                 "the rest are docketed, the safe ones exercised on probation, and the count "
                 "ratchets down"),
    }
    if apply:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        tmp = OUT.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(doc, indent=1), encoding="utf-8")
        os.replace(tmp, OUT)
        PROBATION_QUEUE.parent.mkdir(parents=True, exist_ok=True)
        PROBATION_QUEUE.write_text(json.dumps({"at": doc["at"], "queue": probation}, indent=1),
                                   encoding="utf-8")
        AUTO_LEGS.write_text(json.dumps({"at": doc["at"], "legs": legs}, indent=1),
                             encoding="utf-8")
        FLOOR.write_text(json.dumps({"unwired": min(n, prev) if isinstance(prev, int) else n,
                                     "at": doc["at"], "breach": breach}, indent=1),
                         encoding="utf-8")
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--apply", action="store_true", help="write the artifact, queue and ratchet")
    ap.add_argument("--dry-run", action="store_true", help="print only")
    a = ap.parse_args(argv)
    doc = build(apply=a.apply and not a.dry_run)
    print(f"wiring ceo: {doc['n_organs']} organ(s), {doc['n_scheduled']} on a clock, "
          f"{doc['n_unwired']} UNWIRED ({doc['n_probation']} on probation, "
          f"{doc['auto_legs']['n']} auto-clocked: {doc['auto_legs']['core']} core / "
          f"{doc['auto_legs']['heavy']} heavy); floor "
          f"{doc['floor']['status']} (was {doc['floor']['previous']})")
    for r in doc["unwired"][:12]:
        print(f"  {r['organ']:<58} {r['lines']:>5}L tests={'y' if r['has_tests'] else 'n'} "
              f"probation={'y' if r['probation'] else 'n'}")
    if a.apply and not a.dry_run:
        print(f"-> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

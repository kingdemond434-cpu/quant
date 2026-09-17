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

THE 2026-09-17 PASS (principal: "wire everything the wiring hunter discovered, revive and
certify and put clocks on everything"). Four defects the first version shipped with, each
measured, each closed here:

  * THE DRY-RUN TRAP, found by the descendants builder. `_probation_ok` returned "main() takes
    --dry-run" for ANY organ whose source contained that string, `build` then set `dry_run` by
    looking for "dry-run" IN THE REASON, and `auto_legs` clocked the organ with argv
    ["--dry-run"]. So every auto-clocked leg ran the one mode that writes nothing: the organ was
    on a clock, cost a subprocess an hour, and donated NOTHING -- wiring that measured itself as
    done while producing exactly what being unwired produced. Probation still passes --dry-run
    (it is proving the organ STARTS, on a build nobody has ever run); the CLOCKED leg never
    does. Production arguments are the organ's own declaration: a module-level
    `PRODUCTION_ARGS = ["--apply"]` read statically, never imported, never guessed.
  * AUTO-CLOCKED ORGANS COUNTED AS UNWIRED FOREVER. auto_legs.json is a clock -- run_auto_legs
    executes it hourly as a costed leg -- but it was in no CLOCK_FILE, so a clocked organ stayed
    in the unwired census, the ratchet could never fall, and auto_legs was rebuilt each pass
    from the probation list alone (an organ that left probation lost its clock). The auto file
    is now a clock source, its organs are closure roots like any other clocked organ, and the
    legs are rebuilt from the union of what is clocked and what probation has just proven.
  * REVIVE. An organ ON a clock that has produced nothing within two cadences is as unwired as
    one on no clock, and the census could not see it. `revive_queue` reads the scout roster's
    measured broken/idle/UNMEASURED-with-a-clock rows and the auto legs whose last probation run
    failed, and hands them to probation, which re-runs them and reports the traceback tail.
  * NO CLI IS NOT NO REACH. A library module has no `main()`, so it can never be clocked, and
    counting it as an organ would be a lie in the other direction. They are censused separately:
    reached by a clocked organ's import closure (fine), imported but only by unwired organs
    (named), or imported by nothing at all -- the true dead list, which is the simplifier's
    input rather than this hunter's.
  * CERTIFICATES ARE CLOCKS TOO. A ten-gate certificate with no forward clock row, or whose only
    rows are stopped, is the same defect one layer up: evidence built and never run. The count is
    published here and the standing identity healer's own callables are invoked under --apply.
"""
from __future__ import annotations

import argparse
import ast
import contextlib
import io
import json
import os
import re
import sys
import time
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
#: The artifacts this hunter READS (as opposed to the four it writes, which are the constants
#: above). They are resolved at CALL time through `_desk_file`, never frozen at import: a test
#: repoints DESK to build a hermetic tree, and a constant bound at import would send that test
#: reading -- and under --apply, WRITING -- the live desk's registry.
SCOUT_ROSTER = ("reports", "SCOUT_ROSTER.json")
SURVIVORS = ("reports", "UNIVERSAL_SURVIVORS.json")
SHADOW_STATE = ("reports", "shadow", "shadow_state.json")
SLEEVE_REGISTRY = ("data", "sleeve_registry.json")
#: An organ is CLOCKED automatically once probation has seen it run clean once; it runs on the
#: core plan when its measured run stays under this, on the heavy plan otherwise.
AUTO_CORE_MAX_S = 60.0
AUTO_CORE_MIN_CLEAN = 3
#: What `data/auto_legs.json` IS, written into the census as the clock it is. hourly_cycle's
#: `run_auto_legs` runs every row in it as a costed leg with a ledger row and an artifact check,
#: so an organ named there is on a clock in exactly the sense this hunter measures.
AUTO_CLOCK = "data/auto_legs.json (auto-clocked hourly leg)"
#: The module-level name an organ uses to declare how the CLOCK should call it: a list of string
#: literals, read by AST and never by import. `PRODUCTION_ARGS = ["--apply"]` on an organ whose
#: default mode reports without writing is the difference between a clocked leg that donates and
#: one that burns a subprocess an hour to print.
PRODUCTION_ARGS_NAME = "PRODUCTION_ARGS"
#: Forward-clock statuses that are ACCRUING. Anything else is a stopped clock: the certificate
#: exists, the clock row exists, and no forward evidence is being earned against it.
LIVE_CLOCK_STATUS: frozenset[str] = frozenset({"ACTIVE", "PROMOTION CANDIDATE",
                                               "PROMOTION_CANDIDATE"})
#: Stopped statuses the identity healer can actually act on. `REFUSED_BY_UNIVERSE_POLICY` is NOT
#: one of them and never becomes one here: that is a policy verdict about the instrument, not a
#: broken clock, and reviving it would be this hunter overruling the universe mandate.
HEALABLE_CLOCK_STATUS: frozenset[str] = frozenset({"IDENTITY_BROKEN", "VOID",
                                                   "RETIRED_UNRECONSTRUCTIBLE",
                                                   "QUARANTINED_FORWARD_CLOCK_BREACH"})
#: Scout statuses that mean "on a clock and not producing" -- the revive lane. `UNMEASURED` is
#: here ONLY when the scout has a clock: a clocked organ with no observable output has either
#: never run or leaves nothing behind, and both are defects probation can measure.
REVIVE_STATUS: frozenset[str] = frozenset({"broken", "idle", "UNMEASURED"})
#: A revive run is a real run of a real organ (crawlers, miners), not a --dry-run smoke test.
REVIVE_BUDGET_S = 300

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
    try:
        return p.relative_to(ROOT).as_posix()
    except ValueError:
        return p.as_posix()


def _desk_file(parts: tuple[str, ...]) -> Path:
    """A desk artifact, resolved against DESK as it is NOW (see the note on SCOUT_ROSTER)."""
    return DESK.joinpath(*parts)


def _census_files() -> list[tuple[str, Path, str]]:
    """(rel, path, text) for every candidate .py under ORGAN_AREAS, read ONCE.

    Both censuses need the same files: organs (a `main()`) and libraries (no `main()`). Reading
    the areas twice doubled the hunter's I/O for nothing."""
    out: list[tuple[str, Path, str]] = []
    for area in ORGAN_AREAS:
        base = ROOT / area
        if not base.is_dir():
            continue
        for p in sorted(base.glob("*.py")):
            if p.name.startswith("_") or "test" in p.name.lower():
                continue
            try:
                out.append((_rel(p), p, p.read_text(encoding="utf-8", errors="replace")))
            except OSError:
                continue
    return out


def organs(census: list[tuple[str, Path, str]] | None = None) -> dict[str, Path]:
    """rel path -> file, for every .py under ORGAN_AREAS that defines main()."""
    return {rel: p for rel, p, text in (census if census is not None else _census_files())
            if re.search(r"^def main\(", text, re.M)}


def library_modules(census: list[tuple[str, Path, str]] | None = None) -> dict[str, Path]:
    """rel path -> file, for every .py under ORGAN_AREAS with NO `main()`.

    A library cannot be clocked -- there is nothing to invoke -- so counting it as an unwired
    organ would be a lie, and leaving it out of the census entirely is the other lie: a module
    nothing imports is dead weight whether or not it has a CLI. They are counted here and judged
    by REACH (`library_reach`) instead of by clock."""
    return {rel: p for rel, p, text in (census if census is not None else _census_files())
            if not re.search(r"^def main\(", text, re.M)}


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


#: path -> (narrow module names, names bound by `from <pkg> import <name>`), parsed ONCE per pass.
#: `build` clears it, because the tests build several trees in one process and a memo that
#: outlives a tree is a lie about it.
_IMPORTS: dict[str, tuple[set[str], set[str]]] = {}


def _parse_imports(path: Path) -> tuple[set[str], set[str]]:
    """One AST parse per file, both extractions. The first draft parsed twice and cost the hunter
    25 seconds a pass for a set it already had."""
    key = str(path)
    hit = _IMPORTS.get(key)
    if hit is not None:
        return hit
    narrow: set[str] = set()
    bound: set[str] = set()
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, SyntaxError, ValueError):
        _IMPORTS[key] = (narrow, bound)
        return _IMPORTS[key]
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            narrow |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                narrow.add(node.module.split(".")[-1])
                narrow.add(node.module.split(".")[0])
            bound |= {a.name.split(".")[0] for a in node.names}
    _IMPORTS[key] = (narrow, bound)
    return _IMPORTS[key]


def _local_imports(path: Path) -> set[str]:
    """Bare module names a desk file imports (`import deepening_worker`, `from x import y`)."""
    return _parse_imports(path)[0]


def _imported_names(path: Path) -> set[str]:
    """`_local_imports` PLUS the names bound by `from <pkg> import <name>`.

    THE TWO EXTRACTIONS POINT IN OPPOSITE DIRECTIONS AND THAT IS DELIBERATE. Claiming an organ is
    WIRED needs evidence, so the scheduling closure stays narrow: a false import there invents a
    clock that does not exist and the ratchet would fall on a lie. Claiming a module is DEAD needs
    evidence in the other direction, so reach uses the wider form: `from side_channels import
    china_miner` binds a MODULE under the narrow rule's blind spot, and missing it would propose
    deleting a module that something imports."""
    narrow, bound = _parse_imports(path)
    return narrow | bound


def scheduled(orgs: dict[str, Path], extra_roots: dict[str, str] | None = None,
              ) -> tuple[dict[str, list[str]], list[tuple[str, str]]]:
    """rel path -> the clock files that name it (directly, or through a scheduled importer).

    `extra_roots` are organs a clock that is DATA rather than text already carries -- today the
    auto-clocked legs in data/auto_legs.json. They are roots of the import closure like any other
    clocked organ, because the leg that runs them imports whatever they import."""
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
    for rel, label in (extra_roots or {}).items():
        if rel in orgs and rel not in named:
            named[rel] = [label]
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


#: `add_argument("--dry-run")`, in either quote, with whatever spacing. The first version tested
#: `"--dry-run" in text`, which is true of any organ that MENTIONS the flag in a docstring, a
#: comment or a usage line -- and probation then passed a flag argparse rejects, which reads as a
#: broken organ. A flag is declared or it is not.
_DRY_RUN_DECL = re.compile(r"add_argument\(\s*[\"']--dry-run[\"']")


def takes_dry_run(text: str) -> bool:
    """Does this organ DECLARE --dry-run (not merely mention it)?"""
    return bool(_DRY_RUN_DECL.search(text))


def production_argv(text: str) -> tuple[list[str], str]:
    """(argv, basis) for the CLOCKED leg: the organ's own `PRODUCTION_ARGS`, or nothing.

    THE CONTRACT, and why it is a declaration rather than a guess. An auto-clocked leg must run
    the organ the way the desk wants it run in production, and only the organ knows that: some
    write by default, some report unless given `--apply`, some take a budget. This hunter will
    not invent `--apply` for an organ it has never read -- handing an unknown flag to an organ
    that moves state is exactly the kind of blind action NEVER_PROBATION exists to prevent. So
    the organ declares it, at module level, in string literals:

        PRODUCTION_ARGS = ["--apply", "--max-donations", "15"]

    read by AST (the module is never imported: importing 300 organs to read one constant would
    run 300 module bodies). Absent, the leg runs with NO arguments, which is the organ's own
    default mode. What it is never given is `--dry-run`: that is probation's flag, and a clocked
    leg that runs it produces nothing by construction."""
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError):
        return [], "unparseable: no production args"
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(t, ast.Name) and t.id == PRODUCTION_ARGS_NAME for t in node.targets):
            continue
        if not isinstance(node.value, (ast.List, ast.Tuple)):
            return [], f"{PRODUCTION_ARGS_NAME} is not a list of literals; ignored"
        argv = [e.value for e in node.value.elts
                if isinstance(e, ast.Constant) and isinstance(e.value, str)]
        argv = [a for a in argv if a != "--dry-run"]
        return argv, f"declared {PRODUCTION_ARGS_NAME}"
    return [], "no PRODUCTION_ARGS: the leg runs the organ's own default mode"


def _probation_ok(rel: str, p: Path) -> tuple[bool, str]:
    low = rel.lower()
    if any(tok in low for tok in NEVER_PROBATION):
        return False, "touches money, releases or the tree: never exercised blind"
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False, "unreadable"
    if takes_dry_run(text):
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


def _organ_text(organ: str) -> str:
    try:
        return (ROOT / organ).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def directly_clocked(named: dict[str, list[str]]) -> set[str]:
    """Organs a CLOCK FILE names outright -- not reached through an importer, not auto-clocked.

    The difference matters in exactly one place and it is load-bearing: an auto-clocked organ that
    later earns a named leg must LOSE its auto leg, or the desk runs it twice an hour and pays for
    both. Being reached through the import closure is not that: importing a module does not call
    its `main()`, so an auto leg is still the only thing invoking it."""
    return {rel for rel, hits in named.items()
            if any(h != AUTO_CLOCK and not h.startswith("imported by ") for h in hits)}


def auto_legs(probation: list[dict[str, Any]], state: dict[str, Any] | None = None,
              prev: list[dict[str, Any]] | None = None,
              orgs: dict[str, Path] | None = None,
              drop: set[str] | None = None) -> list[dict[str, Any]]:
    """THE WIRER (principal 2026-09-16: "an hourly organ wirer ... which always spots and does
    exactly these things"). Every organ probation has run clean at least once becomes a real
    hourly leg: production `argv`, a budget, and a PLAN -- core when its measured runs stay under
    AUTO_CORE_MAX_S for AUTO_CORE_MIN_CLEAN clean runs, heavy otherwise. hourly_cycle's
    `run_auto_legs` executes them as costed legs, so they get the ledger row, the provenance
    envelope and the artifact check every named leg gets. Nothing here edits the cycle's code;
    the clock is data.

    IT NEVER PASSES --dry-run, and that is the whole 2026-09-17 fix. A clocked leg running an
    organ's dry mode is a subprocess an hour that writes nothing and donates nothing, while every
    counter here reports the organ as wired. Probation uses `--dry-run` to prove the organ starts;
    the clock uses the organ's declared `PRODUCTION_ARGS`, or nothing at all.

    `prev` KEEPS A CLOCKED ORGAN CLOCKED. Once an organ is auto-clocked it stops being unwired,
    so it leaves the probation list -- and the first version rebuilt this file from that list
    alone, silently un-clocking every organ it had just wired. The legs are the union: what is
    already clocked here (still present in `orgs`, still not money-path) plus what probation has
    just proven."""
    st = state if state is not None else _read(PROBATION_STATE)
    hist = _sub(st, "history")
    seen: dict[str, dict[str, Any]] = {}
    for row in list(prev or []) + list(probation):
        organ = str(row.get("organ") or "")
        if not organ or organ in seen:
            continue
        if any(tok in organ.lower() for tok in NEVER_PROBATION):
            continue                      # a money-path name never earns a clock, ever
        if orgs is not None and organ not in orgs:
            continue                      # the organ left the tree
        if drop and organ in drop:
            continue                      # a named leg took it over: never run it twice an hour
        h = _sub(hist, organ)
        if int(h.get("clean", 0) or 0) < 1:
            continue
        secs = h.get("seconds") if isinstance(h.get("seconds"), (int, float)) else None
        core = (int(h.get("clean", 0) or 0) >= AUTO_CORE_MIN_CLEAN and secs is not None
                and float(secs) <= AUTO_CORE_MAX_S)
        argv, basis = production_argv(_organ_text(organ))
        seen[organ] = {"organ": organ, "leg": "auto_" + Path(organ).stem,
                       "argv": argv, "argv_basis": basis,
                       "budget_s": int(row.get("budget_s") or PROBATION_BUDGET_S),
                       "plan": "core" if core else "heavy",
                       "clean_runs": int(h.get("clean", 0) or 0), "seconds": secs,
                       "last_status": h.get("last_status")}
    return list(seen.values())


def _read(p: Path) -> dict[str, Any]:
    try:
        d = json.loads(p.read_text(encoding="utf-8-sig"))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def _sub(doc: dict[str, Any] | None, key: str) -> dict[str, Any]:
    """`doc[key]` when it is a mapping, {} otherwise. Every state file this hunter reads is
    written by another organ and may be half-built, truncated or of an older shape, so a nested
    read is never indexed blind."""
    value = (doc or {}).get(key)
    return value if isinstance(value, dict) else {}


def library_reach(orgs: dict[str, Path], libs: dict[str, Path],
                  named: dict[str, list[str]]) -> tuple[list[dict[str, Any]], list[str]]:
    """(rows, dead) for every library module: who imports it, and whether a CLOCK reaches it.

    A library has no `main()`, so it can never be clocked and it is never "unwired" in the sense
    the ratchet counts. The question that IS answerable about it is REACH: does the import closure
    of some clocked organ arrive here? Three answers, and only one of them is a defect this desk
    can act on.

      * reached      a clocked organ imports it, directly or through another library. It runs
                     every time that organ runs; nothing to do.
      * unreached    something imports it, but nothing on a clock does. Its importers are named,
                     so the fix is visible: clock an importer, or let it go.
      * dead         NOTHING imports it, anywhere in the census. This is the true dead list and
                     it is the SIMPLIFIER's input, not this hunter's: deleting code is a proposal
                     a session decides, and `simplifier.dead` already prices what a deletion
                     would break. Published here so the two organs count the same population.
    """
    by_stem: dict[str, list[str]] = {}
    for rel, p in libs.items():
        by_stem.setdefault(p.stem, []).append(rel)
    importers: dict[str, set[str]] = {rel: set() for rel in libs}
    for rel, p in {**orgs, **libs}.items():
        for stem in _imported_names(p):
            for target in by_stem.get(stem, ()):
                if target != rel:
                    importers[target].add(rel)
    reached: dict[str, str] = {}
    frontier = [rel for rel in named if rel in orgs]
    while frontier:
        rel = frontier.pop()
        src = orgs.get(rel) or libs.get(rel)
        if src is None:
            continue
        for stem in _imported_names(src):
            for target in by_stem.get(stem, ()):
                if target not in reached:
                    reached[target] = rel
                    frontier.append(target)
    rows: list[dict[str, Any]] = []
    dead: list[str] = []
    for rel, p in sorted(libs.items()):
        imps = sorted(importers.get(rel) or ())
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            text = ""
        # A .py with no `main()` is not automatically a library: a hand-run script with top-level
        # code under `if __name__ == "__main__"` is invisible to the ORGAN rule (`def main(`) and
        # is a different remedy -- give it a main() and it becomes clockable. Lumping the two
        # together would hand the simplifier a deletion list full of working scripts.
        kind = "script_no_main" if "__main__" in text else "library"
        row = {"module": rel, "lines": len(text.splitlines()), "kind": kind,
               "importers": len(imps), "importers_sample": imps[:4],
               "reached_by_clock": rel in reached,
               "reached_via": reached.get(rel),
               "why": ("reached by a clocked organ's import closure" if rel in reached else
                       (f"imported by {len(imps)} organ(s), none of them on a clock" if imps else
                        ("a hand-run script with no main(): the organ rule cannot see it; give it "
                         "a main() to make it clockable" if kind == "script_no_main" else
                         "imported by nothing in the census: the true dead list")))}
        rows.append(row)
        if not imps:
            dead.append(rel)
    rows.sort(key=lambda r: (r["reached_by_clock"], r["importers"], -int(r["lines"])))
    return rows, dead


def _clock_signature(key: str) -> tuple[str, str, str] | None:
    """(symbol, family, selector) for a forward-clock key, or None when the shape is unreadable.

    The key shapes are `shadow_forward.sleeve_key`'s own: `SYM.window` for the breakout family
    (never renamed, because running clocks must not be), `SYM.family.window` for every other
    family, `@TF` for a non-H1 chart, `#k=v` for parameters, `.SHORT` for the short twin, and an
    UPPERCASE tail for a conditioner (`.FAILED_BREAK`). Parameters and chart are dropped here on
    purpose: the question is whether the certified CELL has a clock at all, and a certificate
    whose only clock runs different parameters is a different question, asked elsewhere."""
    s = str(key)
    if s.upper().endswith(".SHORT"):
        s = s[:-6]
    s = s.split("#", 1)[0].split("@", 1)[0]
    parts = [x for x in s.split(".") if x]
    if len(parts) < 2:
        return None
    sym, rest = parts[0], parts[1:]
    if len(rest) > 1 and rest[-1].isupper():
        rest = rest[:-1]                            # a conditioner, not a selector
    if len(rest) == 1:
        return sym, "session_range_breakout", rest[0]
    return sym, rest[0], rest[1]


def certificate_clocks() -> dict[str, Any]:
    """CERTIFICATES ARE CLOCKS TOO: how many ten-gate certificates have no clock accruing.

    A certificate is a claim that has passed every gate the desk has. If no forward clock row
    exists for its cell, or every row that does exist is stopped, then the claim is a build that
    runs nowhere -- the same defect as an unwired organ, one layer up, and far more expensive
    because the evidence that would promote it is never earned.

    UNREADABLE IS NOT ZERO (L1.28a). If either artifact is missing or unparseable the count is
    None with the reason named, never 0 -- "no certificate is stranded" and "I could not read the
    certificates" are opposite facts."""
    surv_path, shadow_path = _desk_file(SURVIVORS), _desk_file(SHADOW_STATE)
    surv = _read(surv_path)
    shadow = _read(shadow_path)
    rows = surv.get("survivors") if isinstance(surv.get("survivors"), dict) else None
    if not rows:
        return {"n": None, "why": f"UNMEASURED: no readable survivors at {_rel(surv_path)}"}
    if not shadow:
        return {"n": None, "why": f"UNMEASURED: no readable clock state at {_rel(shadow_path)}"}
    index: dict[tuple[str, str, str], list[str]] = {}
    for key, row in shadow.items():
        sig = _clock_signature(key)
        if sig is None or not isinstance(row, dict):
            continue
        index.setdefault(sig, []).append(str(row.get("status") or "").upper())
    stranded: list[dict[str, Any]] = []
    by_status: dict[str, int] = {}
    clocked = 0
    for cert, row in rows.items():
        spec = row.get("shadow_spec") if isinstance(row, dict) else None
        spec = spec if isinstance(spec, dict) else {}
        sig = (str(spec.get("symbol") or ""), str(spec.get("family") or "session_range_breakout"),
               str(spec.get("selector") or ""))
        states = index.get(sig)
        if states and any(s in LIVE_CLOCK_STATUS for s in states):
            clocked += 1
            continue
        blocking = sorted(set(states or ()))
        for s in blocking or ["NO_CLOCK_ROW"]:
            by_status[s] = by_status.get(s, 0) + 1
        stranded.append({"certificate": cert, "cell": f"{sig[0]} {sig[1]} {sig[2]}".strip(),
                         "clock_rows": len(states or ()), "blocking_status": blocking,
                         "healable": any(s in HEALABLE_CLOCK_STATUS for s in blocking)})
    healable = sum(1 for r in stranded if r["healable"])
    return {"n": len(stranded), "n_certificates": len(rows), "n_clocked": clocked,
            "healable": healable, "by_status": by_status, "stranded": stranded[:40],
            "rule": ("a certificate whose cell has no forward clock row, or whose only rows are "
                     "stopped, is evidence built and never run; REFUSED_BY_UNIVERSE_POLICY is a "
                     "policy verdict and is never counted as healable")}


def heal_clocks(apply: bool = False) -> dict[str, Any]:
    """Call the STANDING identity healer's own callables, and report exactly what they did.

    WHY IT CALLS THE HEALER RATHER THAN REIMPLEMENTING IT. `heal_identity_broken_clocks` already
    owns the two repairs and their preconditions: `backfill_behaviour` immunises an intact clock
    against a prose edit, `freeze_unfrozen` enrols a running clock that never froze an identity.
    A second implementation of either would be a second answer to one question.

    IT NEVER IMPORTS THE PROMOTER. `freeze_unfrozen` resolves modern `#param` keys through
    `promoter.clock_identities()`, which is a heavy import inside what is a CORE hourly leg here,
    so `identities={}` is passed explicitly: legacy keys are enrolled from this pass and the
    modern ones are left to the healer's own MT5-IdentityHealer task (every 30 minutes) and to
    hourly_cycle's `heal_clocks` leg, which are the places that own that work. The gap is named
    in the artifact rather than papered over."""
    out: dict[str, Any] = {"applied": bool(apply),
                           "callables": ["heal_identity_broken_clocks.backfill_behaviour",
                                         "heal_identity_broken_clocks.freeze_unfrozen"],
                           "limitation": ("modern '#param' clock keys need "
                                          "promoter.clock_identities(); they are left to the "
                                          "MT5-IdentityHealer task")}
    reg_path = _desk_file(SLEEVE_REGISTRY)
    if not reg_path.is_file():
        out["gap"] = f"no sleeve registry at {_rel(reg_path)}: nothing to enrol"
        return out
    for extra in (DESK / "scripts", DESK / "research", DESK, ROOT):
        if str(extra) not in sys.path:
            sys.path.insert(0, str(extra))
    t0 = time.monotonic()
    try:
        import heal_identity_broken_clocks as healer
        registry = json.loads(reg_path.read_text(encoding="utf-8-sig"))
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            immunised = healer.backfill_behaviour(reg_path, apply=apply)
            enrolled = healer.freeze_unfrozen(registry, apply=apply, identities={})
        out.update(immunised=int(immunised), enrolled=int(enrolled),
                   seconds=round(time.monotonic() - t0, 1),
                   tail=buf.getvalue().strip().splitlines()[-3:])
    except Exception as exc:        # a healer that cannot load is a GAP, never a raised core leg
        out["gap"] = f"healer unavailable here: {type(exc).__name__}: {exc}"
    return out


def revive_queue(named: dict[str, list[str]], auto: list[dict[str, Any]] | None = None,
                 state: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Organs that ARE on a clock and have produced nothing within two cadences.

    UNWIRED AND IDLE ARE THE SAME DEFECT (LAWS III.16) and only one of them was being counted.
    An organ with a task, a timer and a leg that has not written an artifact in two cadences has
    produced exactly what an unclocked organ produces, and the wiring census scored it as wired
    because a clock file names it. Two measured sources, never a guess:

      * the SCOUT ROSTER's own status, which is derived from the clock the scout actually has
        (output inside one cadence is active, two is idle, beyond that is broken) -- plus the
        UNMEASURED rows that HAVE a clock, which is the worst case of all: clocked, and leaving
        nothing anywhere to observe.
      * the AUTO LEGS whose last probation run did not exit clean. Those are organs this hunter
        itself put on a clock, so it owns their failure.

    The rows go to `probation_runner`, which re-runs each one for real (never --dry-run: the
    point is to make it produce) and reports the traceback tail of whatever stops it."""
    rows: dict[str, dict[str, Any]] = {}
    roster = _read(_desk_file(SCOUT_ROSTER))
    for scout in roster.get("scouts") or []:
        if not isinstance(scout, dict):
            continue
        organ = str(scout.get("organ_file") or "")
        status = str(scout.get("status") or "")
        clock = scout.get("clock")
        if not organ or status not in REVIVE_STATUS or not clock:
            continue
        if any(tok in organ.lower() for tok in NEVER_PROBATION):
            continue
        if not (ROOT / organ).is_file():
            continue
        argv, basis = production_argv(_organ_text(organ))
        rows[organ] = {"organ": organ, "clock": str(clock), "cadence_s": scout.get("cadence_s"),
                       "last_output": scout.get("last_output_at"), "status": status,
                       "source": "scout_roster", "argv": argv, "argv_basis": basis,
                       "budget_s": REVIVE_BUDGET_S}
    hist = _sub(state, "history")
    for leg in auto or []:
        organ = str(leg.get("organ") or "")
        last = str(_sub(hist, organ).get("last_status") or "")
        if not organ or organ in rows or last in ("", "OK"):
            continue
        argv, basis = production_argv(_organ_text(organ))
        rows[organ] = {"organ": organ, "clock": AUTO_CLOCK, "cadence_s": 3600.0,
                       "last_output": None, "status": f"auto leg last exited {last}",
                       "source": "auto_legs", "argv": argv, "argv_basis": basis,
                       "budget_s": int(leg.get("budget_s") or REVIVE_BUDGET_S)}
    # The census's own word on each one, so a reader can see when the two disagree: the roster
    # reads the clock a scout HAS, this hunter reads the clocks the repo DECLARES, and a row where
    # one says clocked and the other does not is itself a finding.
    for organ, row in rows.items():
        clocks = named.get(organ) or []
        row["census_clock"] = clocks[0] if clocks else None
    return list(rows.values())


def build(apply: bool = False) -> dict[str, Any]:
    _IMPORTS.clear()
    census = _census_files()
    orgs = organs(census)
    libs = library_modules(census)
    state = _read(PROBATION_STATE)
    # AUTO_LEGS IS A CLOCK, so its organs are scheduled and are roots of the import closure. It
    # is also the previous pass's decision: an organ this hunter clocked stays clocked until the
    # organ leaves the tree or a named clock takes it over (`auto_legs(prev=...)`).
    prev_auto = [e for e in (_read(AUTO_LEGS).get("legs") or [])
                 if isinstance(e, dict) and e.get("organ")]
    auto_roots = {str(e["organ"]): AUTO_CLOCK for e in prev_auto}
    named, _texts = scheduled(orgs, extra_roots=auto_roots)
    tested = _tested(orgs)
    unwired: list[dict[str, Any]] = []
    probation: list[dict[str, Any]] = []
    needs_production_args: list[str] = []
    for rel, p in sorted(orgs.items()):
        if rel in named or rel in EXEMPT:
            continue
        text = ""
        with contextlib.suppress(OSError):
            text = p.read_text(encoding="utf-8", errors="replace")
        lines = len(text.splitlines())
        ok, why = _probation_ok(rel, p)
        row = {"organ": rel, "lines": lines, "has_tests": rel in tested,
               "suggested_clock": _suggest_clock(rel, lines),
               "probation": ok, "probation_why": why,
               "task": (f"wire {rel}: register it as a leg or task (suggested "
                        f"{_suggest_clock(rel, lines).split(' ')[0]}) and give it an artifact")}
        unwired.append(row)
        if ok:
            argv, basis = production_argv(text)
            # THE DRY-RUN FLAG LIVES ON THE PROBATION ROW AND NOWHERE ELSE. It used to be
            # recovered by looking for the substring "dry-run" in the REASON string, which is how
            # a reason became an instruction and every auto leg inherited the one mode that
            # writes nothing.
            probation.append({"organ": rel, "dry_run": takes_dry_run(text),
                              "budget_s": PROBATION_BUDGET_S,
                              "production_argv": argv, "argv_basis": basis})
            if not argv and "--apply" in text:
                needs_production_args.append(rel)
    unwired.sort(key=lambda r: (not r["has_tests"], -r["lines"]))
    # the ratchet
    prev = None
    try:
        prev = json.loads(FLOOR.read_text(encoding="utf-8-sig")).get("unwired")
    except (OSError, ValueError, AttributeError):
        prev = None
    n = len(unwired)
    breach = isinstance(prev, int) and n > prev
    legs = auto_legs(probation, state, prev=prev_auto, orgs=orgs, drop=directly_clocked(named))
    lib_rows, lib_dead = library_reach(orgs, libs, named)
    revive = revive_queue(named, legs, state)
    certs = certificate_clocks()
    heal = heal_clocks(apply=apply)
    doc = {
        "at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "n_organs": len(orgs), "n_scheduled": len(named), "n_unwired": n,
        "n_probation": len(probation), "n_exempt": len(EXEMPT),
        "n_auto_clocked": len(legs), "n_revive": len(revive),
        "certificates_without_clocks": certs.get("n"),
        "floor": {"previous": prev, "now": n, "status": "BREACH" if breach else
                  ("RATCHETED" if isinstance(prev, int) and n < prev else "HELD"),
                  "rule": ("the unwired count may fall, never rise; a new organ arrives with "
                           "its clock")},
        "unwired": unwired[:200],
        "probation": probation[:200],
        "revive": revive[:80],
        "auto_legs": {"n": len(legs), "core": sum(1 for x in legs if x["plan"] == "core"),
                      "heavy": sum(1 for x in legs if x["plan"] == "heavy"),
                      "with_production_argv": sum(1 for x in legs if x["argv"]),
                      "needs_production_args": needs_production_args[:40],
                      "rule": ("clocked as a real hourly leg after one clean probation run; "
                               f"core when measured under {AUTO_CORE_MAX_S:.0f}s for "
                               f"{AUTO_CORE_MIN_CLEAN} clean runs, heavy otherwise; the leg runs "
                               f"the organ's declared {PRODUCTION_ARGS_NAME} and NEVER "
                               "--dry-run")},
        "library": {"n": len(libs), "reached": sum(1 for r in lib_rows if r["reached_by_clock"]),
                    "unreached": sum(1 for r in lib_rows if not r["reached_by_clock"]),
                    "dead": len(lib_dead),
                    "dead_scripts": sum(1 for r in lib_rows
                                        if not r["importers"] and r["kind"] == "script_no_main"),
                    "rule": ("a module with no main() cannot be clocked; it is judged by reach. "
                             "Imported by nothing is the true dead list and belongs to the "
                             "simplifier, which prices what a deletion would break; a "
                             "script_no_main among them is a hand-run script, and its remedy is a "
                             "main() rather than a deletion")},
        "library_unreached": [r for r in lib_rows if not r["reached_by_clock"]][:120],
        "library_dead": lib_dead[:120],
        "certificates": certs,
        "identity_heal": heal,
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
        PROBATION_QUEUE.write_text(json.dumps({"at": doc["at"], "queue": probation,
                                               "revive": revive}, indent=1), encoding="utf-8")
        AUTO_LEGS.parent.mkdir(parents=True, exist_ok=True)
        AUTO_LEGS.write_text(json.dumps({"at": doc["at"], "legs": legs}, indent=1),
                             encoding="utf-8")
        FLOOR.parent.mkdir(parents=True, exist_ok=True)
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
    lib = doc["library"]
    print(f"  libraries: {lib['n']} with no CLI -- {lib['reached']} reached by a clocked organ, "
          f"{lib['unreached']} unreached, {lib['dead']} imported by nothing (-> simplifier; "
          f"{lib['dead_scripts']} of those are hand-run scripts needing a main())")
    print(f"  revive: {doc['n_revive']} organ(s) on a clock producing nothing within 2 cadences")
    c = doc["certificates"]
    print(f"  certificates without clocks: {c.get('n')} of {c.get('n_certificates')} "
          f"({c.get('healable')} healable); identity heal "
          f"{doc['identity_heal'].get('gap') or doc['identity_heal']}")
    if a.apply and not a.dry_run:
        print(f"-> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

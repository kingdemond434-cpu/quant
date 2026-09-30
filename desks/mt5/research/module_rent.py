"""MODULE RENT -- every organ pays rent in MEASURED downstream research, or it gets named.

    "A module cannot exist forever for free."                        -- the principal, 2026-09-17

WHAT THE DESK ALREADY HAD, AND WHY IT IS NOT THIS. `libs/ops/module_rent.py` prices the RAILS and
the capital components in log-wealth per day: does this veto/cap/allocator-component raise or
lower E[log W]. It answers the money question. It says nothing at all about the 804 organs that
never touch a position -- the miners, compilers, screens, censuses and reports that consume the
hours. Measured on this tree the day this landed: 804 organs with a `main()`, 508 named by some
clock, 294 on no clock at all, and not one of them carrying a line that says what its compute
bought in candidates, admissions or survivors. A module nothing bills is a module nothing can
reduce, merge or retire, which is how a desk grows machinery faster than it grows edge.

ARTIFACT NAMES, AND WHY THESE ONES. `desks/mt5/reports/MODULE_RENT.json` and
`desks/mt5/data/module_rent.jsonl` ALREADY BELONG to `libs/ops/module_rent.py` -- they are
declared as its writes in `libs/ops/capability_graph.py` and read by
`scripts/check_acceptance_properties.py` and `libs/ops/capability_graph.py`. One artifact, one
producer: this organ writes MODULE_RENT_RESEARCH.json and module_rent_research.jsonl beside
them so both ledgers survive, and the names sort next to each other so a person scanning the
reports directory finds the pair rather than wondering which one lied.

WHAT IS MEASURED, per module, over trailing 7 and 30 days -- compute (the ledger's hours for the
leg that runs it), candidates (graph rows whose `source` names it, plus the registry's
generator_yield), novel mechanisms (cells no earlier row had occupied), gauntlet admissions,
survivors, delta n_eff, defects (its name on a FAILED log line or a stall_watch heal),
maintenance (ONE bounded `git log` for the whole census) and complexity (LOC + fan). Every one of
them can come back UNMEASURED rather than zero, and the per-function docstrings say when.

    ROI = (survivors x 10 + admissions x 1 + novel x 3 + candidates x 0.1)
          / (compute hours + maintenance commits + complexity / 1000)

The weights are DECLARED, not fitted: a survivor is worth a hundred candidates because a
candidate is free and a survivor is the only thing that reaches capital; an admission is worth
ten because the gauntlet's trial budget is the scarce thing a candidate spends. Argue with the
constants by editing WEIGHTS, where they are visible.

VERDICTS, BY RULE, IN THIS ORDER (the first rule that fires wins, and the row says which):

    RETIRE_CANDIDATE   zero measured downstream research over 30 days AND on a clock AND not
                       EXEMPT. On a clock matters: an unwired organ costs nothing and is
                       wiring_ceo's problem, not rent's. EXEMPT means an exemption whose
                       falsifier has NOT arrived -- see below; an expired one shields nothing.
    MERGE              paired by > 60% overlapping artifact keys, or by >= 3 shared imports with
                       near-identical outputs. The pair is NAMED.
    REDUCE             ROI below the census median WITH compute above it -- the expensive half of
                       the unproductive half. The row suggests a longer cadence.
    KEEP               ROI at or above the census median.

NOTHING IS DISABLED HERE. Reducing a cadence, merging two organs or retiring one is a later
decision made against the number, and the number is what this file exists to produce.

EVERY EXEMPTION CARRIES ITS OWN FALSIFIER (2026-09-24). The first draft of `EXEMPT_TOKENS` was a
token -> reason map and nothing more, which made it the one structure on this desk that could
never be wrong: a governance/publication/health organ was excused from the cells yardstick
FOREVER, on a sentence, with no condition under which the sentence stops being true. The desk
already knew better -- `docs/research/productivity_blockers.json` says it in its own note, "an
EXEMPTION here is PERMANENT only while it stays true: every row carries `retire_if`, the
condition that deletes it, so a declaration cannot outlive the fact it was declared on" -- and
the rent ledger, whose entire purpose is that no module exists for free, was the place the rule
was missing. So the schema is now `Exemption(why, retire_if, checks, declared_utc)`, the
constructor REFUSES a row without a falsifier, and `checks` names MEASURED predicates
(`RETIRE_CHECKS`) evaluated per covered module on every pass. A fired falsifier stops shielding
in the same pass it fires, and the row says which check fired and on what evidence. UNMEASURED
never deletes anything (L1.28a) and never quietly passes either: a half-measured condition reads
UNMEASURED, the exemption keeps shielding, and the census says so by name.
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import re
import subprocess
import sys
import time
from collections import defaultdict
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

OUT = DESK / "reports" / "MODULE_RENT_RESEARCH.json"
LEDGER = DESK / "data" / "module_rent_research.jsonl"
GRAPH = DESK / "data" / "hypothesis_graph.jsonl"
COMPUTE = DESK / "data" / "compute_ledger.jsonl"
LOGS = DESK / "logs"
STALL = DESK / "data" / "stall_watch.json"
#: `scripts/check_dead_architecture.py`'s census: per organ, the artifacts it writes, who reads
#: them, and a verdict in {LIVE, BURNING, NO_CLOCK, UNREACHED}. BURNING ("on a clock and no
#: reader found") is the falsifier half of every governance/publication/health exemption, and it
#: is READ here, never recomputed -- the census owns the definition.
DEAD = DESK / "reports" / "dead_architecture.json"

#: The census areas, borrowed from wiring_ceo so the two organs count the same population.
ORGAN_AREAS: tuple[str, ...] = ("desks/mt5/research", "desks/mt5/scripts",
                                "desks/mt5/frontier_intel", "desks/mt5/side_channels",
                                "scripts", "libs/research_os")
CLOCK_FILES: tuple[str, ...] = ("desks/mt5/research/hourly_cycle.py",
                                "desks/mt5/research/daily_cycle.py",
                                "desks/mt5/ops/box_tasks.manifest", "ops/crontab.manifest")
CLOCK_AREAS: tuple[str, ...] = ("ops", "desks/mt5/scripts", "desks/mt5/recorders", "deploy")
CLOCK_SUFFIXES: tuple[str, ...] = (".timer", ".service", ".cmd", ".ps1", ".sh", ".manifest")

#: DECLARED weights. Downstream research, in candidate-equivalents.
WEIGHTS: dict[str, float] = {"survivors": 10.0, "admissions": 1.0, "novel_mechanisms": 3.0,
                             "candidates": 0.1}
COMPLEXITY_FAN_WEIGHT = 50.0
MERGE_JACCARD = 0.60
MERGE_SHARED_IMPORTS = 3
#: A Jaccard over two-element sets is noise, not evidence: the first draft paired
#: `factor_residual_engine` with `repair_universe_spreads` because both name `universe.json` and
#: one bars file. A pair must carry weight on BOTH sides before it is named.
MERGE_MIN_KEYS = 3
MERGE_MIN_SHARED = 2
MIN_COST = 1e-3
LOG_TAIL_BYTES = 200_000

#: A module can only read MEASURED ZERO downstream research if the desk keeps a channel that
#: could have credited it. These are the channels: a module whose own source names one is a
#: DECLARED PRODUCER, and its zero is a finding. A module that names none of them (an allocator,
#: a cost model, a recorder) is UNMEASURED on this axis and can never be a RETIRE_CANDIDATE --
#: retiring a module for failing a yardstick it was never on is the denominator trick, inverted.
PRODUCER_MARKS: tuple[str, ...] = (
    "hypothesis_graph", "enqueue_candidate", "record_discovery", "generator_yield",
    "miner_candidates", "research_queue", "discoveries_", "data/intelligence",
    "suggestion_ledger", "donate", "candidate", "hypothes",
)

# ------------------------------------------------------------ exemptions, and their falsifiers
#
# AN EXEMPTION WITHOUT A FALSIFIER IS A PERMANENT EXCUSE. The three predicates below are the only
# conditions an exemption may declare, and each one was chosen because it is MEASURED TODAY on an
# artifact this desk already writes -- not because it sounded like a condition:
#
#   mints_cells            the hypothesis graph / registry generator_yield, through this organ's
#                          own per-module row. It REFUTES the premise: "its product is a verdict,
#                          not a candidate" is false about a module that minted candidates.
#   output_reaches_nobody  desks/mt5/reports/dead_architecture.json, verdict BURNING ("on a clock
#                          and no reader found"). It refutes the OTHER half: an organ excused
#                          because it makes a verdict/page/alarm instead of a cell must actually
#                          be making one that something reads. BURNING means it makes neither.
#   gains_a_clock          this organ's own clock index. It is the falsifier of a "no schedule by
#                          design" claim and of nothing else, so only the inherited wiring_ceo
#                          rows declare it.
#
# A FOURTH CANDIDATE WAS MEASURED AND REFUSED, and the measurement is why. "The organ names no
# artifact of its own" reads well and would have been a platitude: dead_architecture's artifact
# list is non-empty for all 671 organs it judges (its heuristic over-reports on purpose -- it may
# make an organ look more alive, never mark a live one dead), so the predicate could never fire.
# A condition that cannot fire is the permanent excuse wearing a falsifier's clothes.

#: The named, MEASURED predicates an exemption may declare -> what each one reads. A check
#: answers True (the falsifier arrived: this exemption stops shielding this module), False (it
#: holds) or None (UNMEASURED on this host, which never deletes and never passes -- L1.28a).
RETIRE_CHECKS: dict[str, str] = {
    "mints_cells": "this module's own rent row records candidates, admissions or survivors in "
                   "the last 30 days (hypothesis_graph source tokens + registry generator_yield)",
    "output_reaches_nobody": "desks/mt5/reports/dead_architecture.json judges this module "
                             "BURNING -- on a clock with no reader found for anything it writes",
    "gains_a_clock": "this organ's clock index names the module (a clock file references its "
                     "path, or a clocked organ imports it)",
}
#: A falsifier has to be a CONDITION, not a mood. Same bar `check_build_standard` puts on a
#: schedule exemption's reason, for the same reason: a sentence shorter than this cannot say what
#: would have to be observed.
MIN_RETIRE_IF_CHARS = 40
#: 20+ chars, the bar `docs/research/productivity_blockers.json` already sets for a `why`.
MIN_WHY_CHARS = 20


@dataclass(frozen=True)
class Exemption:
    """One declared excuse from RETIRE_CANDIDATE, and the MEASURED condition that deletes it.

    The constructor is the fence: an exemption that cannot say what would prove it wrong cannot
    be constructed, so there is no code path on this desk that writes one. `checks` must name
    predicates in `RETIRE_CHECKS`, which are evaluated per covered module on every pass --
    `retire_if` is the prose a person reads and `checks` is what the machine measures, and the
    two are kept in one object so neither can drift away from the other.
    """

    #: What this organ produces INSTEAD of cells -- the claim being made.
    why: str
    #: The condition under which this row is DELETED, in the vocabulary
    #: `docs/research/productivity_blockers.json` already uses.
    retire_if: str
    #: The `RETIRE_CHECKS` names that measure `retire_if`. ANY of them firing retires the row.
    checks: tuple[str, ...]
    #: When the claim was declared, so a reader can see how long it has stood unfalsified.
    declared_utc: str
    #: Where the declaration lives, for a reader who has to go and delete it.
    source: str = "desks/mt5/research/module_rent.py EXEMPTIONS"
    #: What about this claim CANNOT be measured yet, said out loud rather than given a
    #: fake-green condition. Empty means every part of `retire_if` has a predicate behind it.
    unmeasured: str = ""

    def __post_init__(self) -> None:
        if len(self.why.strip()) < MIN_WHY_CHARS:
            raise ValueError(f"exemption {self.why!r}: a reason under {MIN_WHY_CHARS} chars is "
                             "not a decision")
        if len(self.retire_if.strip()) < MIN_RETIRE_IF_CHARS:
            raise ValueError(
                f"exemption {self.why!r}: retire_if is missing or under {MIN_RETIRE_IF_CHARS} "
                "chars. An exemption with no falsifier is a permanent excuse, which is the one "
                "thing this ledger exists to refuse -- name the condition that DELETES this row")
        if not self.checks:
            raise ValueError(f"exemption {self.why!r}: retire_if names no measured check; prose "
                             "nothing evaluates is not a falsifier (pick from "
                             f"{sorted(RETIRE_CHECKS)})")
        unknown = [c for c in self.checks if c not in RETIRE_CHECKS]
        if unknown:
            raise ValueError(f"exemption {self.why!r}: unknown check(s) {unknown}; a check must "
                             f"be measured by this module ({sorted(RETIRE_CHECKS)})")
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", self.declared_utc.strip()):
            raise ValueError(f"exemption {self.why!r}: declared_utc {self.declared_utc!r} is not "
                             "a YYYY-MM-DD date; an undated claim cannot be aged")


#: The three falsifiers the governance / publication / health classes share, written once so the
#: 21 rows below differ by their CLAIM rather than by an accident of phrasing.
_GOVERNANCE_RETIRE = (
    "the covered organ's name reaches the hypothesis graph or generator_yield as a source of "
    "candidates, admissions or survivors within 30 days -- then it mints cells after all and is "
    "judged on them like every other producer -- OR dead_architecture.json judges it BURNING (on "
    "a clock, no reader found), which means it produces neither a cell nor a verdict anybody "
    "reads and the excuse has nothing left to protect. Either way the row is DELETED, not amended.")
_PUBLICATION_RETIRE = (
    "the covered organ starts minting cells within 30 days (then it is a producer and is judged "
    "as one), OR dead_architecture.json judges it BURNING -- on a clock with no reader for the "
    "page or report it renders. A rendering leg is excused because somebody reads the rendering; "
    "when nobody does, the excuse is gone and this row is DELETED, not amended.")
_HEALTH_RETIRE = (
    "the covered organ starts minting cells within 30 days (then it is a producer and is judged "
    "as one), OR dead_architecture.json judges it BURNING -- on a clock with no reader for the "
    "alarm or census it raises. A health organ is excused because its alarm reaches somebody; an "
    "alarm nobody reads is not a different product, it is no product. DELETED, not amended.")
_GOVERNANCE_CHECKS = ("mints_cells", "output_reaches_nobody")

_DECLARED = "2026-09-24"


def _gov(why: str) -> Exemption:
    return Exemption(why, _GOVERNANCE_RETIRE, _GOVERNANCE_CHECKS, _DECLARED)


def _pub(why: str) -> Exemption:
    return Exemption(why, _PUBLICATION_RETIRE, _GOVERNANCE_CHECKS, _DECLARED)


def _hlth(why: str) -> Exemption:
    return Exemption(why, _HEALTH_RETIRE, _GOVERNANCE_CHECKS, _DECLARED)


#: EXEMPT from RETIRE_CANDIDATE, each with the reason AND the falsifier that deletes it. A
#: governance, publication or health organ produces a verdict, a page or an alarm -- never a
#: candidate -- so judging it by downstream research is judging it by a yardstick it was never
#: built to move. That claim is now falsifiable in both directions (see `_GOVERNANCE_RETIRE`).
#: wiring_ceo.EXEMPT and wiring_ceo.NEVER_PROBATION are folded in at runtime through `INHERITED`.
EXEMPTIONS: dict[str, Exemption] = {
    "check_": _gov("governance: a law gate; its product is a verdict, not a candidate"),
    "attest": _gov("governance: the closed-loop attestation"),
    "audit": _gov("governance: an audit names defects, it does not mint hypotheses"),
    "verify": _gov("governance: a verifier"),
    "guard": _gov("governance: a fence -- it refuses, it does not propose"),
    "fence": _gov("governance: a fence -- it refuses, it does not propose"),
    "law": _gov("governance: the law compendium's own machinery"),
    "constitution": _gov("governance: the sealed core's checker"),
    "publish": _pub("publication: it renders what other organs measured"),
    "dashboard": _pub("publication: the desk's page"),
    "report": _pub("publication: a rendering leg"),
    "render": _pub("publication: a rendering leg"),
    "scorecard": _pub("publication: a rendering leg"),
    "health": _hlth("health: it measures the machine, not the market"),
    "stall": _hlth("health: the stall watch"),
    "smoke": _hlth("health: a release smoke test"),
    "burn_in": _hlth("health: the burn-in exercises a release, it does not mint a hypothesis"),
    "heartbeat": _hlth("health: liveness -- it proves the machine is up, not that price moved"),
    "issue_board": _hlth("health: the defect board"),
    "wiring": _hlth("health: the wiring census is how idleness is found at all"),
    "probation": _hlth("health: probation is how an unwired organ earns a clock"),
}

#: THE TWO BORROWED REGISTRIES, and the falsifier this organ declares for the borrowed USE.
#: `wiring_ceo` keeps both lists for its own question (who owes a cron line, who is never
#: exercised blind); this file is the one that turns them into a shield against a RETIRE verdict,
#: so this file owes the condition under which that shield lapses. Declaring it here rather than
#: editing wiring_ceo keeps one owner per decision: wiring_ceo decides who gets probation, rent
#: decides who gets excused from rent.
INHERITED: dict[str, Exemption] = {
    "wiring_ceo.EXEMPT": Exemption(
        why="unscheduled on purpose (wiring_ceo.EXEMPT)",
        retire_if="a clock names the organ -- a clock file references its path, or a clocked "
                  "organ imports it. The whole claim is 'a person runs this by hand'; the moment "
                  "the machine runs it, the claim is false and the row is DELETED from "
                  "wiring_ceo.EXEMPT. It also lapses if the organ starts minting cells.",
        checks=("gains_a_clock", "mints_cells"),
        declared_utc=_DECLARED,
        source="desks/mt5/research/wiring_ceo.py EXEMPT (falsifier declared in module_rent)"),
    "wiring_ceo.NEVER_PROBATION": Exemption(
        why="never exercised blind (wiring_ceo.NEVER_PROBATION)",
        retire_if="the organ's name reaches the hypothesis graph or generator_yield as a source "
                  "of candidates, admissions or survivors within 30 days -- a money-path organ "
                  "that mints cells is a producer and is judged as one, and this token stops "
                  "excusing it here (the wiring_ceo list itself is untouched: it governs "
                  "probation, not rent).",
        checks=("mints_cells",),
        declared_utc=_DECLARED,
        source="desks/mt5/research/wiring_ceo.py NEVER_PROBATION "
               "(falsifier declared in module_rent)",
        unmeasured="the consumer half cannot be measured for a money path and is NOT declared: "
                   "a gateway's reader is the broker, not a repo artifact, so "
                   "`output_reaches_nobody` would read UNMEASURED forever and declaring it would "
                   "be a fake-green condition. This exemption therefore has ONE live falsifier "
                   "and the desk should know that rather than be told otherwise."),
}

#: Token -> reason, DERIVED so a plain-string exemption cannot be smuggled back in. Kept because
#: it is the shape older readers expect; `EXEMPTIONS` is the source of truth.
EXEMPT_TOKENS: dict[str, str] = {tok: ex.why for tok, ex in EXEMPTIONS.items()}


# --------------------------------------------------------------------------- small readers
def paths_for(rt: Path) -> dict[str, Path]:
    """Every path this organ touches, derived from ONE root. Tests hand it a tmp tree; the box
    hands it nothing and gets the module constants, so a monkeypatched constant still binds."""
    if Path(rt) == ROOT:
        return {"compute": COMPUTE, "graph": GRAPH, "logs": LOGS, "stall": STALL,
                "dead": DEAD, "out": OUT, "ledger": LEDGER}
    d = Path(rt) / "desks" / "mt5"
    return {"compute": d / "data" / "compute_ledger.jsonl",
            "graph": d / "data" / "hypothesis_graph.jsonl",
            "logs": d / "logs", "stall": d / "data" / "stall_watch.json",
            "dead": d / "reports" / "dead_architecture.json",
            "out": d / "reports" / "MODULE_RENT_RESEARCH.json",
            "ledger": d / "data" / "module_rent_research.jsonl"}


def _read_json(p: Path) -> dict[str, Any]:
    try:
        d = json.loads(p.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return {}
    return d if isinstance(d, dict) else {}


def _atomic(p: Path, payload: Any) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=1, default=str), encoding="utf-8")
    os.replace(tmp, p)


def _at(v: Any) -> datetime | None:
    try:
        return datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


_MAIN_RE = re.compile(r"^def main\(", re.M)
_WORD_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_KEY_RE = re.compile(r"""["']([\w.\-]{3,}\.(?:json|jsonl|csv|parquet|npz))["']""")


# --------------------------------------------------------------------------- the census
def organ_files(root: Path) -> dict[str, Path]:
    """rel path -> file for every .py under ORGAN_AREAS that defines main() (wiring_ceo's rule)."""
    out: dict[str, Path] = {}
    for area in ORGAN_AREAS:
        base = root / area
        if not base.is_dir():
            continue
        for p in sorted(base.glob("*.py")):
            if p.name.startswith("_") or "test" in p.name.lower():
                continue
            try:
                text = p.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if _MAIN_RE.search(text):
                out[p.relative_to(root).as_posix()] = p
    return out


_IMPORT_CACHE: dict[str, tuple[set[str], set[str]]] = {}


def _imports(path: Path) -> tuple[set[str], set[str]]:
    """(bare stems, dotted names) this file imports. Parsed ONCE per path: wiring_ceo records
    that re-parsing 400 organs per pass cost minutes, and this census is twice that size."""
    key = str(path)
    hit = _IMPORT_CACHE.get(key)
    if hit is not None:
        return hit
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, SyntaxError, ValueError):
        _IMPORT_CACHE[key] = (set(), set())
        return set(), set()
    bare: set[str] = set()
    dotted: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                dotted.add(a.name)
                bare.add(a.name.split(".")[0])
                bare.add(a.name.split(".")[-1])
        elif isinstance(node, ast.ImportFrom) and node.module:
            dotted.add(node.module)
            bare.add(node.module.split(".")[0])
            bare.add(node.module.split(".")[-1])
            for a in node.names:
                dotted.add(f"{node.module}.{a.name}")
    _IMPORT_CACHE[key] = (bare, dotted)
    return bare, dotted


#: The FORMS that put an organ on a clock, as wiring_ceo defines them: a path ending in its file,
#: `-m <module>`, `import <module>`, `from <module> import`. Anything else is a coincidence.
_PATH_RE = re.compile(r"([A-Za-z0-9_./\\-]+\.py)\b")
_MODULE_RES: tuple[re.Pattern[str], ...] = (
    re.compile(r"-m\s+([A-Za-z_][A-Za-z0-9_.]*)"),
    re.compile(r"(?:^|[;&|(\s])import\s+([A-Za-z_][A-Za-z0-9_.]*)", re.M),
    re.compile(r"from\s+([A-Za-z_][A-Za-z0-9_.]*)\s+import"),
)
#: How many trailing path components a clock's path reference is indexed by.
PATH_SUFFIX_DEPTH = 4


def path_suffixes(rel: str, depth: int = PATH_SUFFIX_DEPTH) -> set[str]:
    """`desks/mt5/research/x.py` -> {research/x.py, mt5/research/x.py, desks/mt5/research/x.py}.

    TWO OR MORE COMPONENTS, NEVER ONE, and that is the whole point: `libs/ops/module_rent.py`
    and `desks/mt5/research/module_rent.py` share a basename and nothing else, so a bare
    `module_rent.py` in a clock file identifies neither."""
    parts = [p for p in rel.replace("\\", "/").lower().split("/") if p not in ("", ".", "..")]
    return {"/".join(parts[-i:]) for i in range(2, min(depth, len(parts)) + 1)}


def clock_index(root: Path) -> tuple[set[str], set[str]]:
    """(module stems, path suffixes) any clock file SCHEDULES, by the four forms above.

    THE FIRST DRAFT TOOK EVERY WORD in every clock file, which is fast and wrong: `daily_cycle`
    carries the tuple `("module_rent", _module_rent)` for the rail-rent leg that runs
    libs/ops/module_rent.py, and that bare word made THIS file read as clocked -- and therefore a
    RETIRE_CANDIDATE -- on the very first pass, an hour after it was written and while nothing
    ran it. A clock names a PATH or a MODULE; a leg's display name is neither, and a basename
    two files share is not a name at all."""
    stems: set[str] = set()
    paths: set[str] = set()
    seen: set[Path] = set()
    files: list[Path] = [root / rel for rel in CLOCK_FILES]
    for area in CLOCK_AREAS:
        base = root / area
        if base.is_dir():
            files += [p for p in sorted(base.rglob("*"))
                      if p.is_file() and p.suffix.lower() in CLOCK_SUFFIXES]
    for p in files:
        if p in seen or not p.is_file():
            continue
        seen.add(p)
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for hit in _PATH_RE.findall(text):
            norm = str(hit).replace("\\", "/").lower()
            stems.add(norm.rsplit("/", 1)[-1][:-3])
            paths |= path_suffixes(norm)
        for rx in _MODULE_RES:
            for hit in rx.findall(text):
                parts = str(hit).split(".")
                stems.add(parts[-1])
                stems.add(parts[0])
    return stems, paths


def _leg_layer() -> dict[str, str]:
    try:
        from libs.research.layers import LEG_LAYER
    except (ImportError, AttributeError):
        return {}
    return dict(LEG_LAYER)


def census(root: Path) -> dict[str, dict[str, Any]]:
    """Every organ, plus every libs module a CLOCKED organ imports. The libs half is the part
    `wiring_ceo` never bills: a leg's hours are really spent inside the libs it calls."""
    organs = organ_files(root)
    stems, paths = clock_index(root)
    legs = _leg_layer()
    # A BASENAME TWO FILES SHARE IS NOT A NAME. Counted over the organs AND every libs module,
    # because that is where the collisions are (module_rent, registry, frontier, rails).
    seen_stems: dict[str, int] = defaultdict(int)
    for p in organs.values():
        seen_stems[p.stem] += 1
    libs_dir = root / "libs"
    if libs_dir.is_dir():
        for p in libs_dir.rglob("*.py"):
            seen_stems[p.stem] += 1
    rows: dict[str, dict[str, Any]] = {}
    for rel, p in organs.items():
        stem = p.stem
        by_path = bool(path_suffixes(rel) & paths)
        by_stem = seen_stems[stem] == 1 and stem in stems
        rows[rel] = {"path": p, "stem": stem, "kind": "organ",
                     "clock": ("hourly_cycle:" + stem) if stem in legs else
                              ("clock names it" if (by_path or by_stem) else "none")}
    # TRANSITIVE, wiring_ceo's rule: an organ that a clocked organ imports by bare name runs on
    # that organ's clock. Without this the census reads 352 unwired where wiring_ceo reads 294,
    # and the 58 difference is organs that DO run -- a RETIRE_CANDIDATE needs "on a clock" to be
    # the same question both organs are asking.
    by_stem: dict[str, list[str]] = defaultdict(list)
    for rel, r in rows.items():
        by_stem[r["stem"]].append(rel)
    frontier = [rel for rel, r in rows.items() if r["clock"] != "none"]
    while frontier:
        src = frontier.pop()
        bare, _ = _imports(rows[src]["path"])
        for imp in bare:
            for other in by_stem.get(imp, ()):
                if rows[other]["clock"] == "none":
                    rows[other]["clock"] = f"imported by {src}"
                    frontier.append(other)

    libs_seen: dict[str, Path] = {}
    for row in rows.values():
        if row["clock"] == "none":
            continue
        _, dotted = _imports(row["path"])
        for mod in dotted:
            if not mod.startswith("libs."):
                continue
            f = root.joinpath(*mod.split(".")).with_suffix(".py")
            if f.is_file():
                libs_seen[f.relative_to(root).as_posix()] = f
    for rel, f in libs_seen.items():
        rows.setdefault(rel, {"path": f, "stem": f.stem, "kind": "lib",
                              "clock": "imported by a clocked organ"})
    return rows


# --------------------------------------------------------------------------- the measurements
def compute_hours(rows: list[dict[str, Any]], since: datetime) -> dict[str, float]:
    """leg name -> wall hours since `since`, from the compute ledger."""
    out: dict[str, float] = defaultdict(float)
    for r in rows:
        t = _at(r.get("at"))
        if t is None or t < since:
            continue
        try:
            out[str(r.get("run") or "")] += float(r.get("wall_s") or 0.0) / 3600.0
        except (TypeError, ValueError):
            continue
    return dict(out)


def _jsonl(p: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    try:
        with p.open("r", encoding="utf-8", errors="replace") as fh:
            for ln in fh:
                ln = ln.strip()
                if not ln:
                    continue
                try:
                    r = json.loads(ln)
                except ValueError:
                    continue
                if isinstance(r, dict):
                    out.append(r)
    except OSError:
        return out
    return out


def source_tokens(source: str) -> set[str]:
    """`miner:ff_calendar_vintage` -> {miner, ff_calendar_vintage, ff, calendar, vintage}: the
    graph's source strings are namespaced by hand and no registry ever normalised them."""
    parts = {t for t in re.split(r"[:|/\\.]", str(source or "")) if t}
    return {t.lower() for t in parts if len(t) >= 3}


def _match_index(cen: dict[str, dict[str, Any]]) -> dict[str, list[str]]:
    """token -> the modules a source carrying that token is attributed to."""
    idx: dict[str, list[str]] = defaultdict(list)
    for rel, row in cen.items():
        stem = str(row["stem"]).lower()
        idx[stem].append(rel)
        for suffix in ("_miner", "_factory", "_engine", "_worker", "_runner", "_sweep"):
            if stem.endswith(suffix):
                idx[stem[: -len(suffix)]].append(rel)
    return dict(idx)


def graph_yield(graph: Path, cen: dict[str, dict[str, Any]], since7: datetime,
                since30: datetime) -> tuple[dict[str, dict[str, float]], bool, set[str]]:
    """Candidates, novel cells, admissions and survivors per module, streamed once; plus the
    graph's WHOLE source vocabulary, which is the set of names the desk can credit at all.

    NOVEL means the (family, symbol) cell had not been occupied by ANY earlier row in the graph:
    an organ that re-mints a cell three other organs already minted has produced candidates and
    no mechanism, and the two numbers must not read the same."""
    idx = _match_index(cen)
    per: dict[str, dict[str, float]] = defaultdict(
        lambda: {"candidates_7d": 0.0, "candidates_30d": 0.0, "novel_30d": 0.0,
                 "admissions_30d": 0.0, "survivors_30d": 0.0})
    seen_cells: set[str] = set()
    vocab: set[str] = set()
    if not graph.exists():
        return {}, False, vocab
    try:
        fh = graph.open("r", encoding="utf-8", errors="replace")
    except OSError:
        return {}, False, vocab
    with fh:
        for ln in fh:
            ln = ln.strip()
            if not ln:
                continue
            try:
                r = json.loads(ln)
            except ValueError:
                continue
            if not isinstance(r, dict):
                continue
            cell = f"{r.get('family')}|{r.get('symbol')}"
            fresh = cell not in seen_cells
            seen_cells.add(cell)
            toks = source_tokens(r.get("source", ""))
            vocab |= toks
            t = _at(r.get("at"))
            if t is None or t < since30:
                continue
            hits: list[str] = []
            for tok in toks:
                hits += idx.get(tok, [])
            fate = str(r.get("fate") or "").upper()
            judged = bool(r.get("gates")) or fate in ("FAILED", "CERTIFIED")
            for rel in set(hits):
                d = per[rel]
                d["candidates_30d"] += 1
                if t >= since7:
                    d["candidates_7d"] += 1
                d["novel_30d"] += float(fresh)
                d["admissions_30d"] += float(judged)
                d["survivors_30d"] += float(fate == "CERTIFIED")
    return dict(per), True, vocab


def registry_yield() -> tuple[dict[str, dict[str, float]], str | None]:
    """generator -> the registry's own attribution. Absent registry is UNMEASURED, not zero."""
    try:
        from libs.moat import registry
    except ImportError as exc:
        return {}, f"libs.moat.registry not importable: {exc}"
    try:
        rows = registry.generator_yields()
    except Exception as exc:
        # A missing, locked or unmigratable sqlite file is a MEASUREMENT (the registry is not
        # readable here), never a reason for the whole rent report to die.
        return {}, f"registry unreadable: {type(exc).__name__}: {exc}"
    out: dict[str, dict[str, float]] = {}
    for r in rows:
        gen = str(r.get("generator") or "").lower()
        if not gen:
            continue
        out[gen] = {"generated": float(r.get("generated") or 0.0),
                    "judged": float(r.get("judged") or 0.0),
                    "survivors": float(r.get("survivors") or 0.0),
                    "delta_n_eff": float(r.get("delta_n_eff") or 0.0)}
    return out, None


def defects(cen: dict[str, dict[str, Any]], logs: Path, stall: Path) -> dict[str, int]:
    """A module's name on a FAILED line, or inside a stall_watch heal action."""
    stems = {str(r["stem"]).lower(): rel for rel, r in cen.items()}
    out: dict[str, int] = defaultdict(int)
    lines: list[str] = []
    if logs.is_dir():
        for p in sorted(logs.glob("*.log")):
            try:
                size = p.stat().st_size
                with p.open("rb") as fh:
                    if size > LOG_TAIL_BYTES:
                        fh.seek(size - LOG_TAIL_BYTES)
                    blob = fh.read().decode("utf-8", errors="replace")
            except OSError:
                continue
            lines += [ln for ln in blob.splitlines() if "FAILED" in ln]
    acts = _read_json(stall).get("actions")
    if isinstance(acts, list):
        lines += [str(a) for a in acts if isinstance(a, (str, int, float))]
    for ln in lines:
        for tok in {t.lower() for t in _WORD_RE.findall(ln)}:
            rel = stems.get(tok)
            if rel is not None:
                out[rel] += 1
    return dict(out)


def _git_name_only(root: Path, budget_s: float) -> str | None:
    """ONE bounded git call for the whole census -- never one per module."""
    areas = [a for a in (*ORGAN_AREAS, "libs") if (root / a).exists()]
    cmd = ["git", "-C", str(root), "log", "--since=30.days", "--no-merges",
           "--name-only", "--pretty=format:", "--", *areas]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=max(5.0, budget_s),
                           check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout if r.returncode == 0 else None


def maintenance(root: Path, budget_s: float) -> tuple[dict[str, int], str | None]:
    blob = _git_name_only(root, budget_s)
    if blob is None:
        return {}, "git log unavailable on this host"
    out: dict[str, int] = defaultdict(int)
    for ln in blob.splitlines():
        ln = ln.strip()
        if ln:
            out[ln] += 1
    return dict(out), None


# --------------------------------------------------------------------------- ROI and verdicts
def attribution_of(stem: str, text: str, credited: set[str]) -> str:
    """Which channel could ever credit this module with downstream research.

    THE FLOOD THIS ENDS. The first pass on this tree read 693 RETIRE_CANDIDATEs out of 1,143
    modules, because the hypothesis graph carries 27 distinct `source` strings and everything
    else therefore scored zero by construction. That is an attribution gap, not a rent finding,
    and calling it zero would have put a retirement flag on the allocator, the cost model and
    the tape recorder. A module with no channel is UNMEASURED here, said by name."""
    if stem.lower() in credited:
        return "credited"
    low = text.lower()
    if any(m in low for m in PRODUCER_MARKS):
        return "declared_producer"
    return "none"


def artifact_keys(text: str) -> set[str]:
    """The artifact basenames a module names in its own source: its outputs and its inputs."""
    return {m.lower() for m in _KEY_RE.findall(text)}


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def roi(useful: dict[str, float], cost: dict[str, float]) -> float:
    num = sum(WEIGHTS[k] * float(useful.get(k, 0.0)) for k in WEIGHTS)
    den = max(float(cost.get("compute_h", 0.0)) + float(cost.get("maintenance", 0.0))
              + float(cost.get("complexity", 0.0)) / 1000.0, MIN_COST)
    return num / den


def merge_pairs(rows: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """Two organs whose artifact keys overlap by > MERGE_JACCARD, or that share >=
    MERGE_SHARED_IMPORTS imports AND still land on near-identical output keys."""
    inv: dict[str, list[str]] = defaultdict(list)
    for rel, r in rows.items():
        for k in r.get("keys", ()):
            inv[k].append(rel)
    cand: set[tuple[str, str]] = set()
    for members in inv.values():
        if len(members) > 40:          # a universally-read artifact pairs nobody
            continue
        for i, a in enumerate(members):
            for b in members[i + 1:]:
                cand.add((a, b) if a < b else (b, a))
    out: list[dict[str, Any]] = []
    for a, b in sorted(cand):
        ka, kb = set(rows[a].get("keys", ())), set(rows[b].get("keys", ()))
        if len(ka) < MERGE_MIN_KEYS or len(kb) < MERGE_MIN_KEYS \
                or len(ka & kb) < MERGE_MIN_SHARED:
            continue
        jk = jaccard(ka, kb)
        shared = set(rows[a].get("imports", ())) & set(rows[b].get("imports", ()))
        if jk > MERGE_JACCARD:
            why = f"{len(ka & kb)} artifact keys shared, overlap {jk:.0%} (> {MERGE_JACCARD:.0%})"
        elif len(shared) >= MERGE_SHARED_IMPORTS and jk > 0.0:
            why = (f"{len(shared)} shared imports ({', '.join(sorted(shared)[:3])}) and "
                   f"{jk:.0%} overlapping artifact keys")
        else:
            continue
        out.append({"a": a, "b": b, "jaccard": round(jk, 3), "why": why})
    out.sort(key=lambda d: -float(d["jaccard"]))
    return out


def exemption_for(rel: str, extra: dict[str, str],
                  never: tuple[str, ...]) -> tuple[str, Exemption] | None:
    """(key, exemption) covering `rel`, in the same precedence `exempt_reason` always used.

    The two borrowed registries arrive as bare strings, so the inherited declaration supplies the
    falsifier and `replace` carries the borrowed reason into it -- there is no path by which a
    module reaches the retire decision behind an excuse with no condition on it.
    """
    if rel in extra:
        # THE BORROWED REASON IS STAMPED WITH ITS REGISTRY, and not only for the reader:
        # `replace` re-runs the constructor, so a wiring_ceo entry whose reason is under the
        # `why` bar ("a CLI a person runs", 19 chars) would RAISE and take the whole rent build
        # down. A bar this file sets for its own declarations must never be enforced against a
        # string another organ owns -- the suffix makes the row informative and the crash
        # impossible in the same move.
        return rel, replace(INHERITED["wiring_ceo.EXEMPT"],
                            why=f"{extra[rel]} (wiring_ceo.EXEMPT)")
    low = rel.lower()
    for tok, ex in EXEMPTIONS.items():
        if tok in low:
            return tok, ex
    for tok in never:
        if tok in low:
            return tok, replace(
                INHERITED["wiring_ceo.NEVER_PROBATION"],
                why=f"never exercised blind (wiring_ceo.NEVER_PROBATION token {tok!r})")
    return None


def exempt_reason(rel: str, extra: dict[str, str], never: tuple[str, ...]) -> str | None:
    """The reason only, for callers that ask "is this excused at all" (simplifier.dead)."""
    hit = exemption_for(rel, extra, never)
    return None if hit is None else hit[1].why


def _check_mints_cells(row: dict[str, Any], dead: dict[str, Any] | None) -> tuple[bool | None,
                                                                                 str]:
    """The premise-refuter. UNMEASURED when this host has no channel that could credit it."""
    c = row.get("candidates_30d")
    if c is None:
        return None, ("no measured downstream channel on this host (attribution "
                      f"{row.get('attribution')!r}): absence is not a zero")
    n_c, n_a = int(c), int(row.get("admissions_30d") or 0)
    n_s = int(row.get("survivors_30d") or 0)
    if n_c + n_a + n_s > 0:
        return True, (f"minted {n_c} candidate(s), {n_a} admission(s), {n_s} survivor(s) in 30 "
                      "days: it moves the cells yardstick after all")
    return False, "measured zero candidates, admissions and survivors in 30 days"


def _check_output_reaches_nobody(row: dict[str, Any],
                                 dead: dict[str, Any] | None) -> tuple[bool | None, str]:
    """dead_architecture's own verdict, never recomputed. UNREACHED is explicitly NOT death."""
    if not dead:
        return None, f"{DEAD.name} judges no row for this module"
    v = str(dead.get("verdict") or "")
    if v == "BURNING":
        arts = ", ".join(str(a) for a in (dead.get("artifacts") or [])[:3])
        return True, (f"dead_architecture: BURNING -- on a clock, no reader found for "
                      f"{arts or 'anything it writes'}")
    if v in ("LIVE", "NO_CLOCK"):
        return False, f"dead_architecture: {v} ({dead.get('n_consumers')} consumer(s))"
    return None, (f"dead_architecture: {v or 'no verdict'} -- not a verdict of death by that "
                  "census's own rule, so it cannot delete an exemption")


def _check_gains_a_clock(row: dict[str, Any],
                         dead: dict[str, Any] | None) -> tuple[bool | None, str]:
    """Always measurable: the clock index is a wiring fact, not a market one."""
    clock = str(row.get("clock") or "none")
    if clock != "none":
        return True, f"a clock names it ({clock}): 'a person runs this by hand' is false"
    return False, "on no clock: the claim still holds"


_RETIRE_FN: dict[str, Any] = {
    "mints_cells": _check_mints_cells,
    "output_reaches_nobody": _check_output_reaches_nobody,
    "gains_a_clock": _check_gains_a_clock,
}


def retire_if_fires(ex: Exemption, row: dict[str, Any],
                    dead: dict[str, Any] | None) -> tuple[bool | None, str]:
    """Has this exemption's falsifier arrived for THIS module? True / False / None=UNMEASURED.

    ANY declared check firing retires the row. A check that cannot be measured leaves the answer
    UNMEASURED even when a sibling check reads False: "half of the condition could not be looked
    at" is not "the condition does not hold" (L1.28a). UNMEASURED keeps the shield -- absence
    never deletes -- and is published so the gap has a name instead of a green tick.
    """
    unmeasured: list[str] = []
    for name in ex.checks:
        fired, why = _RETIRE_FN[name](row, dead)
        if fired is True:
            return True, f"{name}: {why}"
        if fired is None:
            unmeasured.append(f"{name}: {why}")
    if unmeasured:
        return None, "UNMEASURED -- " + "; ".join(unmeasured)
    return False, "every declared falsifier measured; none fired"


def exemption_status(rel: str, row: dict[str, Any], dead: dict[str, Any] | None,
                     extra: dict[str, str], never: tuple[str, ...]) -> dict[str, Any] | None:
    """The whole exemption verdict for one module, or None when nothing excuses it."""
    hit = exemption_for(rel, extra, never)
    if hit is None:
        return None
    key, ex = hit
    fired, why = retire_if_fires(ex, row, dead)
    return {"key": key, "source": ex.source, "why": ex.why, "retire_if": ex.retire_if,
            "checks": list(ex.checks), "declared_utc": ex.declared_utc,
            "unmeasured_note": ex.unmeasured or None,
            "fired": fired, "fired_why": why}


def validate_exemptions() -> list[str]:
    """Every declaration re-checked as data, so a fence can REPORT what the constructor RAISES.

    The constructor already refuses a falsifier-less row, which means a malformed one cannot
    exist at runtime -- so this walks the live registry and returns problems rather than relying
    on an exception nobody sees. A fence that can only crash is a fence that gets commented out.
    """
    problems: list[str] = []
    for key, ex in [*EXEMPTIONS.items(), *INHERITED.items()]:
        if not ex.retire_if.strip():
            problems.append(f"{key}: no retire_if -- a permanent excuse")
        elif len(ex.retire_if.strip()) < MIN_RETIRE_IF_CHARS:
            problems.append(f"{key}: retire_if is {len(ex.retire_if.strip())} chars, "
                            f"under the {MIN_RETIRE_IF_CHARS}-char bar for a condition")
        if not ex.checks:
            problems.append(f"{key}: retire_if names no measured check")
        for c in ex.checks:
            if c not in RETIRE_CHECKS:
                problems.append(f"{key}: check {c!r} is not measured by this module")
            elif c not in _RETIRE_FN:
                problems.append(f"{key}: check {c!r} is declared but has no implementation")
        if len(ex.why.strip()) < MIN_WHY_CHARS:
            problems.append(f"{key}: reason too thin to be a decision")
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", ex.declared_utc.strip()):
            problems.append(f"{key}: declared_utc {ex.declared_utc!r} is not a date")
    return problems


def exemption_census(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Per DECLARATION: who it covers, whose falsifier arrived, and what a person should do.

        RETIRE          the falsifier fired for every module it still covers -- delete the row
        PARTIAL         it fired for some; those modules are no longer shielded and are named
        COVERS_NOTHING  it shields no module in today's census: inert, and a reader should know
        UNMEASURED      nothing it covers could be measured on this host (never a pass)
        HOLDS           measured, and the claim survived
    """
    per: dict[str, dict[str, Any]] = {}
    for r in rows:
        key = r.get("exempt_key")
        if not key:
            continue
        d = per.setdefault(str(key), {
            "key": str(key), "source": r.get("exempt_source"), "why": r.get("exempt_why_declared"),
            "retire_if": r.get("exempt_retire_if"), "checks": r.get("exempt_checks"),
            "declared_utc": r.get("exempt_declared_utc"),
            "unmeasured_note": r.get("exempt_unmeasured_note"),
            "n_covered": 0, "n_fired": 0, "n_unmeasured": 0, "fired_modules": []})
        d["n_covered"] += 1
        if r.get("exempt_fired") is True:
            d["n_fired"] += 1
            if len(d["fired_modules"]) < 40:
                d["fired_modules"].append({"module": r["module"], "why": r.get("exempt_fired_why")})
        elif r.get("exempt_fired") is None:
            d["n_unmeasured"] += 1
    out: list[dict[str, Any]] = []
    # THE 21 OWNED DECLARATIONS ARE SEEDED so one that covers nothing is still SAID; the two
    # INHERITED entries are TEMPLATES, not declarations -- they carry the falsifier for a
    # borrowed row and the row itself is keyed by its own path or token, so they appear here
    # only through the modules they actually covered.
    for key, ex in EXEMPTIONS.items():
        d = per.pop(key, {"key": key, "n_covered": 0, "n_fired": 0, "n_unmeasured": 0,
                          "fired_modules": []})
        # THE DECLARATION IS READ FROM THE REGISTRY, NEVER FROM THE ROWS. A census that took
        # `retire_if` from whatever the last row happened to carry would print an empty condition
        # the moment a row was written by an older build -- and an exemption whose falsifier is
        # missing FROM THE REPORT reads exactly like one that never had a falsifier.
        d.update({"source": ex.source, "why": ex.why, "retire_if": ex.retire_if,
                  "checks": list(ex.checks), "declared_utc": ex.declared_utc,
                  "unmeasured_note": ex.unmeasured or None, "kind": "declared"})
        out.append(d)
    for d in sorted(per.values(), key=lambda d: str(d["key"])):
        d["kind"] = "inherited"
        out.append(d)
    for d in out:
        n_cov, n_fire, n_un = d["n_covered"], d["n_fired"], d["n_unmeasured"]
        n_meas = n_cov - n_un
        d["n_measured"] = n_meas
        if n_cov == 0:
            d["verdict"] = "COVERS_NOTHING"
            d["why_verdict"] = ("shields no module in today's census: inert, and an inert "
                                "declaration is a claim the desk cannot cash (L1.49)")
        elif n_fire == n_cov:
            d["verdict"] = "RETIRE"
            d["why_verdict"] = ("the falsifier arrived for every module this row still covers: "
                                "delete the declaration, do not amend it")
        elif n_fire:
            d["verdict"] = "PARTIAL"
            d["why_verdict"] = (f"{n_fire} of {n_cov} covered module(s) are no longer shielded; "
                                f"the declaration still covers the rest ({n_un} UNMEASURED)")
        elif n_un == n_cov:
            d["verdict"] = "UNMEASURED"
            d["why_verdict"] = ("nothing it covers could be measured on this host: the claim is "
                                "untested, which is not the same as surviving a test (L1.28a)")
        else:
            d["verdict"] = "HOLDS"
            d["why_verdict"] = (f"the claim survived on all {n_meas} module(s) it could be "
                                f"measured on; {n_un} of {n_cov} read UNMEASURED")
    out.sort(key=lambda d: (d["verdict"] != "RETIRE", d["verdict"] != "PARTIAL", str(d["key"])))
    return out


def _wiring_exempt() -> tuple[dict[str, str], tuple[str, ...]]:
    try:
        import wiring_ceo
        return dict(wiring_ceo.EXEMPT), tuple(wiring_ceo.NEVER_PROBATION)
    except (ImportError, AttributeError):
        return {}, ()


def _dead_rows(p: Path) -> dict[str, dict[str, Any]]:
    """module -> dead_architecture's row. Absent file is UNMEASURED for every module, not LIVE."""
    org = _read_json(p).get("organs")
    if not isinstance(org, dict):
        return {}
    return {str(k): v for k, v in org.items() if isinstance(v, dict)}


# --------------------------------------------------------------------------- the build
def build(root: Path | None = None, *, budget_s: float = 240.0,
          now: datetime | None = None) -> dict[str, Any]:
    t0 = time.monotonic()
    rt = Path(root) if root is not None else ROOT
    at = now or datetime.now(tz=UTC)
    since7, since30 = at - timedelta(days=7), at - timedelta(days=30)
    unmeasured: list[str] = []

    pp = paths_for(rt)
    cen = census(rt)
    ledger_rows = _jsonl(pp["compute"])
    if not ledger_rows:
        unmeasured.append("compute_ledger: absent or empty; every compute_h reads UNMEASURED")
    h7 = compute_hours(ledger_rows, since7)
    h30 = compute_hours(ledger_rows, since30)
    gy, graph_ok, vocab = graph_yield(pp["graph"], cen, since7, since30)
    if not graph_ok:
        unmeasured.append(f"hypothesis_graph: {pp['graph']} absent; candidates are UNMEASURED")
    ry, reg_why = registry_yield()
    if reg_why:
        unmeasured.append(f"registry generator_yield: {reg_why}")
    credited = vocab | set(ry)
    dfx = defects(cen, pp["logs"], pp["stall"])
    maint, maint_why = maintenance(rt, min(60.0, budget_s / 4.0))
    if maint_why:
        unmeasured.append(f"maintenance: {maint_why}; commit counts read UNMEASURED")
    extra_exempt, never = _wiring_exempt()
    dead_rows = _dead_rows(pp["dead"])
    if not dead_rows:
        unmeasured.append(
            f"dead_architecture: {pp['dead']} absent or empty; the `output_reaches_nobody` half "
            "of every governance/publication/health exemption reads UNMEASURED, so those "
            "exemptions keep shielding on one measured check instead of two")
    schema_problems = validate_exemptions()
    if schema_problems:
        unmeasured.append("exemption schema: " + "; ".join(schema_problems))

    # per-module raw
    rows: dict[str, dict[str, Any]] = {}
    fan_in: dict[str, int] = defaultdict(int)
    for rel, c in cen.items():
        try:
            text = c["path"].read_text(encoding="utf-8", errors="replace")
        except OSError:
            text = ""
        bare, _ = _imports(c["path"])
        loc = len(text.splitlines())
        rows[rel] = {"stem": c["stem"], "kind": c["kind"], "clock": c["clock"], "loc": loc,
                     "keys": artifact_keys(text), "imports": bare,
                     "attribution": attribution_of(c["stem"], text, credited)}
    stems = {r["stem"]: rel for rel, r in rows.items()}
    stem_set = set(stems)
    for rel, r in rows.items():
        for imp in r["imports"]:
            target = stems.get(imp)
            if target and target != rel:
                fan_in[target] += 1

    pairs = merge_pairs(rows)
    in_pair: dict[str, str] = {}
    for p in pairs:
        in_pair.setdefault(p["a"], p["b"])
        in_pair.setdefault(p["b"], p["a"])

    out_rows: list[dict[str, Any]] = []
    for rel, r in sorted(rows.items()):
        stem = r["stem"]
        leg_h7 = h7.get(stem)
        leg_h30 = h30.get(stem)
        g = gy.get(rel, {})
        reg = ry.get(stem.lower(), {})
        cands = g.get("candidates_30d", 0.0) + reg.get("generated", 0.0)
        adm = g.get("admissions_30d", 0.0) + reg.get("judged", 0.0)
        sur = g.get("survivors_30d", 0.0) + reg.get("survivors", 0.0)
        nov = g.get("novel_30d", 0.0)
        fan = fan_in.get(rel, 0) + len(r["imports"] & stem_set)
        complexity = float(r["loc"]) + COMPLEXITY_FAN_WEIGHT * float(fan)
        measured_num = (graph_ok or bool(ry)) and r["attribution"] != "none"
        useful = {"survivors": sur, "admissions": adm, "novel_mechanisms": nov,
                  "candidates": cands}
        cost = {"compute_h": float(leg_h30 or 0.0),
                "maintenance": float(maint.get(rel, 0)),
                "complexity": complexity}
        value = roi(useful, cost) if measured_num else None
        out_row: dict[str, Any] = {
            "module": rel, "clock": r["clock"], "attribution": r["attribution"],
            "compute_h_7d": None if leg_h7 is None else round(leg_h7, 4),
            "compute_h_30d": None if leg_h30 is None else round(leg_h30, 4),
            "candidates_7d": int(g.get("candidates_7d", 0.0)) if graph_ok else None,
            "candidates_30d": int(cands) if measured_num else None,
            "novel_mechanisms_30d": int(nov) if graph_ok else None,
            "admissions_30d": int(adm) if measured_num else None,
            "survivors_30d": int(sur) if measured_num else None,
            "delta_n_eff": reg.get("delta_n_eff"),
            "defects_30d": int(dfx.get(rel, 0)),
            "maintenance_commits_30d": None if maint_why else int(maint.get(rel, 0)),
            "loc": r["loc"], "fan": fan, "complexity": round(complexity, 1),
            "roi": None if value is None else round(value, 4),
            "merge_with": in_pair.get(rel),
        }
        # THE EXEMPTION IS EVALUATED, NOT ASSERTED, and it is evaluated AFTER the row exists
        # because its falsifiers read the row's own measurements. A fired falsifier clears
        # `exempt_why` in the same pass it fires -- an excuse that has been shown false must stop
        # shielding immediately, or the condition is decoration -- while the declaration itself
        # is only ever NAMED here. Deleting the source line is a person's act, made against
        # `exemptions` in this report, exactly as retiring a module is.
        st = exemption_status(rel, out_row, dead_rows.get(rel), extra_exempt, never)
        if st is None:
            out_row.update({"exempt_why": None, "exempt_key": None, "exempt_retire_if": None,
                            "exempt_fired": None, "exempt_fired_why": None})
        else:
            out_row.update({
                "exempt_why": None if st["fired"] else st["why"],
                "exempt_key": st["key"], "exempt_source": st["source"],
                "exempt_why_declared": st["why"], "exempt_retire_if": st["retire_if"],
                "exempt_checks": st["checks"], "exempt_declared_utc": st["declared_utc"],
                "exempt_unmeasured_note": st["unmeasured_note"],
                "exempt_fired": st["fired"], "exempt_fired_why": st["fired_why"]})
        out_rows.append(out_row)

    measured_roi = np.array([r["roi"] for r in out_rows if r["roi"] is not None], dtype=float)
    measured_h = np.array([r["compute_h_30d"] for r in out_rows
                           if r["compute_h_30d"] is not None], dtype=float)
    med_roi = float(np.median(measured_roi)) if measured_roi.size else None
    med_h = float(np.median(measured_h)) if measured_h.size else None
    if med_roi is None:
        unmeasured.append("census median ROI: no module has a measured numerator; "
                          "every verdict reads UNMEASURED")
    n_none = sum(1 for r in out_rows if r["attribution"] == "none")
    if n_none:
        unmeasured.append(
            f"attribution: {n_none} of {len(out_rows)} modules have no channel that could ever "
            f"credit them with downstream research (the graph carries {len(vocab)} distinct "
            f"source tokens); their ROI is UNMEASURED and none can be a RETIRE_CANDIDATE")

    for r in out_rows:
        r["verdict"], r["why"] = _verdict(r, med_roi, med_h)

    by_verdict: dict[str, int] = defaultdict(int)
    for r in out_rows:
        by_verdict[r["verdict"]] += 1
    exemptions = exemption_census(out_rows)
    out_rows.sort(key=lambda d: (-(d["roi"] if d["roi"] is not None else -1.0), d["module"]))
    doc = {
        "at": at.isoformat(timespec="seconds"),
        "n_modules": len(out_rows),
        "elapsed_s": round(time.monotonic() - t0, 2),
        "weights": dict(WEIGHTS),
        "median_roi": None if med_roi is None else round(med_roi, 4),
        "median_compute_h_30d": None if med_h is None else round(med_h, 4),
        "rows": out_rows,
        "by_verdict": dict(sorted(by_verdict.items())),
        "merge_pairs": pairs[:60],
        "exemptions": exemptions,
        "exemption_schema_problems": schema_problems,
        "exemptions_summary": {
            "n_rows": len(exemptions),
            "n_declared_here": len(EXEMPTIONS),
            "n_inherited_keys": sum(1 for e in exemptions if e.get("kind") == "inherited"),
            "n_retire": sum(1 for e in exemptions if e["verdict"] == "RETIRE"),
            "n_partial": sum(1 for e in exemptions if e["verdict"] == "PARTIAL"),
            "n_covers_nothing": sum(1 for e in exemptions if e["verdict"] == "COVERS_NOTHING"),
            "n_unmeasured": sum(1 for e in exemptions if e["verdict"] == "UNMEASURED"),
            "n_modules_unshielded": sum(1 for r in out_rows if r.get("exempt_fired") is True),
            "rule": ("every exemption carries `retire_if` and the MEASURED checks behind it; a "
                     "fired falsifier stops shielding in the same pass, and RETIRE/PARTIAL rows "
                     "name a declaration a person should delete from the source"),
        },
        "unmeasured": unmeasured,
        "formula": ("ROI = (survivors x 10 + admissions + novel x 3 + candidates x 0.1) / "
                    "(compute hours + maintenance commits + complexity / 1000)"),
        "rule": ("every module pays rent in measured downstream research; low-ROI machinery is "
                 "reduced, merged or retired -- by a later decision, never silently"),
    }
    return doc


def _verdict(r: dict[str, Any], med_roi: float | None,
             med_h: float | None) -> tuple[str, str]:
    if r["roi"] is None:
        if r.get("attribution") == "none":
            return "UNMEASURED", ("no channel could credit this module with downstream research "
                                  "(it names no candidate-minting path and the graph has never "
                                  "carried its name): UNMEASURED, not zero (L1.28a)")
        return "UNMEASURED", ("no readable source of downstream research on this host; absence "
                              "is not a zero (L1.28a)")
    downstream = (int(r["candidates_30d"] or 0) + int(r["admissions_30d"] or 0)
                  + int(r["survivors_30d"] or 0))
    clocked = r["clock"] != "none"
    if downstream == 0 and clocked and not r.get("exempt_why"):
        return "RETIRE_CANDIDATE", (f"zero measured candidates, admissions and survivors in 30 "
                                    f"days while on a clock ({r['clock']}), and not exempt")
    if r.get("merge_with"):
        return "MERGE", f"near-duplicate of {r['merge_with']}: merge the pair or name the split"
    if med_roi is not None and r["roi"] < med_roi and med_h is not None \
            and (r["compute_h_30d"] or 0.0) > med_h:
        return "REDUCE", (f"ROI {r['roi']:.3f} below the census median {med_roi:.3f} on "
                          f"{r['compute_h_30d']:.2f}h (above the median {med_h:.2f}h): "
                          f"halve its cadence and re-measure")
    if med_roi is not None and r["roi"] >= med_roi:
        return "KEEP", f"ROI {r['roi']:.3f} at or above the census median {med_roi:.3f}"
    return "KEEP", (f"ROI {r['roi']:.3f} below the median {med_roi:.3f} but cheap "
                    f"({r['compute_h_30d'] if r['compute_h_30d'] is not None else 0.0}h): "
                    f"nothing to reclaim by reducing it")


def append_history(doc: dict[str, Any], ledger: Path | None = None) -> int:
    """One row per module per day, appended once: a verdict is only evidence with a history."""
    p = ledger or LEDGER
    day = str(doc["at"])[:10]
    have: set[str] = set()
    try:
        with p.open("r", encoding="utf-8", errors="replace") as fh:
            for ln in fh:
                try:
                    r = json.loads(ln)
                except ValueError:
                    continue
                if isinstance(r, dict) and r.get("day") == day:
                    have.add(str(r.get("module")))
    except OSError:
        pass
    n = 0
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as fh:
        for r in doc["rows"]:
            if r["module"] in have:
                continue
            fh.write(json.dumps({"at": doc["at"], "day": day, "module": r["module"],
                                 "clock": r["clock"], "roi": r["roi"], "verdict": r["verdict"],
                                 "compute_h_7d": r["compute_h_7d"],
                                 "candidates_30d": r["candidates_30d"],
                                 "survivors_30d": r["survivors_30d"], "loc": r["loc"],
                                 # An excuse that lapsed needs a DATE, or "it was already like
                                 # that" is unanswerable the next time someone reads the row.
                                 "exempt_key": r.get("exempt_key"),
                                 "exempt_fired": r.get("exempt_fired")},
                                default=str) + "\n")
            n += 1
    return n


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dry-run", action="store_true", help="measure and print; write nothing")
    ap.add_argument("--budget-s", type=float, default=240.0,
                    help="wall budget; the git call is bounded by a quarter of it")
    ap.add_argument("--top", type=int, default=12)
    a = ap.parse_args(argv)
    doc = build(budget_s=a.budget_s)
    print(f"module rent: {doc['n_modules']} module(s) in {doc['elapsed_s']}s; median ROI "
          f"{doc['median_roi']}; " + ", ".join(f"{k}={v}" for k, v in doc["by_verdict"].items()))
    for r in doc["rows"][:a.top]:
        print(f"  {r['module']:<58} roi={r['roi']!s:>8} {r['verdict']:<17} {r['why'][:60]}")
    es = doc["exemptions_summary"]
    print(f"  exemptions: {es['n_declared_here']} declared + {es['n_inherited_keys']} inherited "
          f"key(s); {es['n_retire']} RETIRE, "
          f"{es['n_partial']} PARTIAL, {es['n_covers_nothing']} COVERS_NOTHING, "
          f"{es['n_unmeasured']} UNMEASURED; {es['n_modules_unshielded']} module(s) unshielded")
    for e in doc["exemptions"]:
        if e["verdict"] in ("RETIRE", "PARTIAL", "COVERS_NOTHING"):
            print(f"    {e['verdict']:<15} {e['key']:<46} {e['why_verdict'][:52]}")
    for p in doc["exemption_schema_problems"]:
        print(f"  EXEMPTION SCHEMA BREACH: {p}")
    for u in doc["unmeasured"]:
        print(f"  UNMEASURED: {u}")
    if a.dry_run:
        return 0
    _atomic(OUT, doc)
    n = append_history(doc)
    print(f"-> {OUT} (+{n} history row(s) -> {LEDGER})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

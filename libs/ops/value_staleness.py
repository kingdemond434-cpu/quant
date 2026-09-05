"""A LIVE PRODUCER TALKING TO A DEAF CONSUMER (L1.66) -- the value half of code staleness.

``check_stale_daemons`` (``max_audit.py:893``) asks one question of every long-lived process on
this desk: **is the running CODE the committed code?** It walks the transitive import closure,
compares source mtime to process start, and has measured 5 of 18 daemons stale. It is a good
detector and it answers half the question. Nothing has ever asked the other half: **are the
running VALUES the values on disk?**

THE DEFECT CLASS. A module-scope read executes exactly once, when python first imports the
module::

    _VENUE_MIN_NOTIONAL_USD = max(venue_min_notional_usd() or 10.0, 10.0)   # runs at import

Every later reference is to a value frozen at process start. Edit the artifact, and the file on
disk and the value in memory disagree for the entire life of the process -- silently, with no
exception, no log line, and no gauge anywhere going amber. The daemon is not running stale code;
it is running current code over a stale number.

WHY THREE EXISTING INSTRUMENTS ARE EACH BLIND TO IT BY CONSTRUCTION, WHICH IS WHY IT SURVIVED:

  * ``check_stale_daemons`` compares SOURCE mtime to process start. The source here is
    current -- often committed months ago and never touched again. The line is not stale; the
    value it produced once is. Code staleness and value staleness are independent, and the
    detector for one cannot see the other.
  * ``check_freshness`` (L1.44) audits ``data/freshness_contracts.jsonl``, a registry that
    BUILDS ITSELF FROM READS -- its proudest property and, here, precisely the blindness. A
    value read once at import emits one contract row that is byte-identical to the row emitted
    by a healthy per-tick read. *A registry that builds itself from reads cannot see a value
    that is read once and never read again.*
  * ``input_provenance`` (L1.55) asks whether MY inputs were present when I wrote my artifact.
    For a frozen read the answer is always yes: the input was present, at import, and was read
    correctly. The artifact is fine. The PRODUCER is fine. The consumer is deaf.

Every artifact-side and producer-side gauge on this desk reads green on this defect. That is
what makes it a distinct blindness rather than a variation on L1.44: the lens is INVERTED. The
desk has spent five laws on frozen producers feeding live consumers, and none on a live producer
talking to a consumer that stopped listening at import.

THE DESK'S OWN POSITIVE CONTROL, AND WHY IT EXISTS. ``run_cashcarry_executor._live_params``
(``:2398``, called at ``:2527`` INSIDE ``while forever``) re-reads ``data/cashcarry_config.json``
every rebalance: *"Changing a param used to require the flatten+restart the 2026-07-10 churn fix
needed; now just write the JSON and the running loop picks it up next cycle."* That is the
correct pattern, it was built by hand after an incident, it is on the money path, and NOTHING
verifies the pattern holds anywhere else. This module is that verification.

WHAT IT MEASURES, STATED NARROWLY, BECAUSE OVERSTATING IS HOW A FENCE GETS SWITCHED OFF (L1.43).
This fence measures **EXPOSURE, NOT DAMAGE**, and the distinction is load-bearing. A frozen read
whose artifact has changed since process start means the desk **CANNOT PROVE** the in-memory
value matches disk -- not that it provably differs. Measured on this box while building: all
three recorders freeze ``_SYMBOLS = _universe()`` from ``data/cashcarry_positions.json``, a state
file rewritten continuously, so an mtime test calls all three STALE -- while a set comparison of
the recomputed universe against the symbols actually receiving tape showed **zero difference**.
Reporting that as damage would be a false alarm three times over on the first run, and a detector
that cries wolf gets acked into silence (R0356, and L1.37 in terms).

So the verdict vocabulary says exactly what is known:

  FROZEN-STALE       the input changed after this process started. The in-memory value is
                     UNVERIFIABLE from outside the process. This is the finding.
  FROZEN-CURRENT     the input has not changed since start. Exposed, not yet bitten.
  REFRESHED          the import-time binding is a SEED -- the module re-runs its producer inside
                     a function body, so a live re-read path exists. Not a defect; the evidence
                     is published as a line number so the cadence claim can be checked.
  FROZEN-UNRESOLVED  the read is real but its artifact cannot be resolved statically. NEVER
                     silently dropped -- the first version of this analyser dropped exactly
                     these and reported a clean zero (see THE INSTRUMENT CAME FIRST, below).
  EXEMPT             tagged ``# frozen-ok: <reason>`` -- reported, never hidden.

THE REPAIR IS UPWARD, NEVER DOWNWARD (L1.49). The fix for a FROZEN-STALE pair is to move the
read inside the function that consumes it -- the ``_live_params`` shape -- after which the pair
stops being a frozen read and leaves this fence's denominator honestly. The fix is NEVER to
delete the detector, loosen the status, or restart the daemon and call it closed: a restart
re-freezes the same value one tick later.

THE INSTRUMENT CAME FIRST, AND ITS FIRST VERSION WAS WRONG IN THE DESK'S SIGNATURE WAY (L1.25).
The prototype of this analyser reported **0 frozen reads across all 13 live daemons**. Read as a
result that would have been "the class is real but this desk does not have it" -- a null that
retires a search. Run against three sites verified BY HAND minutes earlier, it scored **0 of 3**.
Two bugs, both worth naming because both are classes rather than typos:

  1. Reading functions were resolved only WITHIN the module under analysis. The dominant real
     shape is ``from libs.x import f`` at the top and ``_V = f()`` below, so the analyser was
     blind to the majority case. Resolution is now transitive across repo modules, exactly like
     ``_import_closure``.
  2. A frozen read whose artifact path could not be resolved was **silently dropped** -- the
     ``continue`` that makes "I could not tell" and "there is nothing here" byte-identical. That
     is WS-005, this desk's most-repeated defect class, committed by the instrument built to
     detect a cousin of it. Unresolvable reads are now a COUNTED status.

ANTI-TIMIDITY READING, THE ENTIRE PURPOSE (L1.28, required of every restraint clause). This is a
MEASUREMENT duty and a SCOPE EXPANSION. It lifts nothing, sizes nothing, promotes nothing, opens
no gate, loosens no statistical bar, and has NO VOCABULARY for changing any value it reads or for
turning a failing verdict into a passing one. Its whole effect is to make "this daemon's config
is live" distinguishable from "this daemon last read its config at boot and nobody has checked
since" -- byte-identical on this desk until now, and only one of them is evidence. Every verdict
it emits argues for MORE control surface: making "edit the JSON" a reliable desk-wide actuator is
the precondition for L1.28c's event-driven cadences and for retuning anything without a
flatten+restart.
"""

from __future__ import annotations

import ast
import os
import re
import subprocess
import time
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

from libs.ops.box_state import data_root

# -- pair-level verdicts -------------------------------------------------------------------
FROZEN_STALE = "FROZEN-STALE"
FROZEN_CURRENT = "FROZEN-CURRENT"
FROZEN_UNRESOLVED = "FROZEN-UNRESOLVED"
REFRESHED = "REFRESHED"
SOURCE_DRIFTED = "SOURCE-DRIFTED"
EXEMPT = "EXEMPT"

# -- report-level verdicts -----------------------------------------------------------------
OK = "OK"
UNVERIFIABLE = "UNVERIFIABLE"          # >=1 FROZEN-STALE pair
UNRESOLVED = "UNRESOLVED"              # >=1 read we could not resolve; never a clean pass
NO_DAEMONS_HERE = "NO-DAEMONS-HERE"    # honest declared refusal: nothing of ours is running
UNMEASURED = "UNMEASURED"              # daemons running, nothing examined -- never OK (L1.28a)

#: Only a fully measured, fully current desk passes. Every refusal status is structurally absent
#: from this set, which is what the wiring test pins.
PASSING = frozenset({OK})

#: Attribute/name calls that constitute reading something off disk. Deliberately broad: a false
#: POSITIVE here costs one line in a report that a human reads, while a false NEGATIVE is the
#: defect this module exists to end and is invisible by construction.
READ_VERBS = frozenset({
    "read_text", "read_bytes", "read_json", "read_csv", "read_parquet", "read_fresh",
    "load", "loads", "open", "iterdir", "glob", "rglob", "load_policy", "read",
})

#: A repo-local package whose modules we follow. Mirrors ``max_audit._import_closure`` -- anything
#: outside this ships with the interpreter and cannot change under a running process.
_FIRST_PARTY = frozenset({"libs", "app", "scripts", "api"})

#: ``# frozen-ok: <reason>`` -- the exemption, which MUST carry a reason. A bare tag is not a tag.
#: Mirrors L1.60's ``attrition-ok`` deliberately: exempt sites are REPORTED, never hidden, because
#: an invisible exemption is this defect wearing a comment.
_EXEMPT_TAG = re.compile(r"#\s*frozen-ok:\s*(\S.*)$")

_MAX_DEPTH = 6          # transitive call resolution; cycles are guarded separately
_MIN_UPTIME_H = 1.0     # a just-started process loaded fresh values by definition


@dataclass(frozen=True)
class FrozenRead:
    """One module-scope binding whose value is decided once per process."""

    module: str          # repo-relative
    name: str
    lineno: int
    kind: str            # module-scope | memoized | default-arg
    artifacts: tuple[str, ...] = ()
    exempt_reason: str = ""
    #: Line of a call to this binding's producer from INSIDE a function body -- i.e. a live
    #: re-read path that supersedes the import-time value. 0 when there is none.
    refresh_line: int = 0

    @property
    def resolved(self) -> bool:
        return bool(self.artifacts)


@dataclass(frozen=True)
class Daemon:
    """A live repo process, discovered from the process table -- never from a hand roster."""

    script: str          # repo-relative
    pids: tuple[int, ...]
    started: float
    age_h: float


@dataclass(frozen=True)
class Pair:
    """A (daemon, frozen-read) pair -- the unit this fence counts and grades."""

    daemon: str
    read: FrozenRead
    status: str
    artifact: str = ""
    drift_h: float = 0.0     # hours between process start and the artifact's last change
    why: str = ""

    def as_dict(self) -> dict[str, object]:
        return {
            "daemon": self.daemon, "module": self.read.module, "name": self.read.name,
            "lineno": self.read.lineno, "kind": self.read.kind, "status": self.status,
            "artifact": self.artifact, "drift_h": round(self.drift_h, 2), "why": self.why,
        }


@dataclass
class Report:
    status: str
    pairs: list[Pair] = field(default_factory=list)
    daemons: list[Daemon] = field(default_factory=list)
    basis: str = ""
    root: str = ""
    attempted: int = 0        # L1.60: iterations entered
    skipped: int = 0          # L1.60: iterations abandoned, counted rather than invisible
    notes: list[str] = field(default_factory=list)

    @property
    def n_pairs(self) -> int:
        return len(self.pairs)

    def _n(self, status: str) -> int:
        return sum(1 for p in self.pairs if p.status == status)

    @property
    def n_stale(self) -> int:
        return self._n(FROZEN_STALE)

    @property
    def n_current(self) -> int:
        return self._n(FROZEN_CURRENT)

    @property
    def n_unresolved(self) -> int:
        return self._n(FROZEN_UNRESOLVED)

    @property
    def n_exempt(self) -> int:
        return self._n(EXEMPT)

    @property
    def n_refreshed(self) -> int:
        return self._n(REFRESHED)

    @property
    def n_source_drifted(self) -> int:
        return self._n(SOURCE_DRIFTED)

    def as_dict(self) -> dict[str, object]:
        return {
            "law": "L1.66",
            "status": self.status,
            "measures": ("EXPOSURE, not damage: a FROZEN-STALE pair means the in-memory value "
                         "cannot be PROVEN to match disk, never that it provably differs"),
            "basis": self.basis,
            "root": self.root,
            "n_daemons": len(self.daemons),
            "n_pairs": self.n_pairs,
            "n_frozen_stale": self.n_stale,
            "n_frozen_current": self.n_current,
            "n_frozen_unresolved": self.n_unresolved,
            "n_refreshed": self.n_refreshed,
            "n_source_drifted": self.n_source_drifted,
            "n_exempt": self.n_exempt,
            "attempted": self.attempted,
            "skipped": self.skipped,
            "daemons": [{"script": d.script, "pids": list(d.pids), "age_h": round(d.age_h, 2)}
                        for d in self.daemons],
            "pairs": [p.as_dict() for p in self.pairs],
            "notes": list(self.notes),
            "repair": ("move the read inside the function that consumes it (the "
                       "run_cashcarry_executor._live_params shape); a restart only re-freezes "
                       "the same value one tick later"),
        }


# ---------------------------------------------------------------------------------------------
# process discovery
# ---------------------------------------------------------------------------------------------
def proc_start(pid: int) -> float | None:
    """Wall-clock epoch a process started, or None if it is gone.

    Field 22 of /proc/<pid>/stat in clock ticks since boot, plus /proc/stat's btime. ``comm``
    can contain spaces and parens so the split starts after the LAST ')'. This is a deliberate
    second copy of ``max_audit._proc_start`` rather than an import: ``max_audit`` is a 5000-line
    module whose import has side effects, and a fence that has to import the audit engine to
    read a pid is a fence with an outage waiting in it. The subtlety it encodes -- that
    ``Path("/proc/<pid>").stat().st_mtime`` is NOT a start time and reads ~now for any polled
    process (L0070, a 10-day zero-recall bug) -- is pinned by this module's own test.
    """
    try:
        st = Path(f"/proc/{pid}/stat").read_text("utf-8")
        starttime = int(st[st.rindex(")") + 2:].split()[19])
        btime = next(int(ln.split()[1])
                     for ln in Path("/proc/stat").read_text("utf-8").splitlines()
                     if ln.startswith("btime "))
    except (OSError, ValueError, StopIteration, IndexError):
        return None
    return btime + starttime / os.sysconf("SC_CLK_TCK")


def live_daemons(root: Path, *, min_uptime_h: float = _MIN_UPTIME_H,
                 now: float | None = None) -> tuple[list[Daemon], int, int]:
    """Repo scripts currently running, from the PROCESS TABLE, never a hand list.

    Returns (daemons, attempted, skipped). R0668 is the standing reason: three live recorder
    units sat in NO supervision roster, so a roster-driven scan returned an empty plan and a
    recorder fix could never ship. ``ps`` cannot miss a process for want of registration.
    """
    now = time.time() if now is None else now
    attempted = skipped = 0
    try:
        out = subprocess.run(["ps", "-eo", "pid,args"], capture_output=True, text=True,
                             timeout=20, check=False).stdout
    except (OSError, subprocess.SubprocessError):
        return [], 0, 0
    by_script: dict[str, list[int]] = {}
    for line in out.splitlines()[1:]:
        attempted += 1
        parts = line.split()
        if len(parts) < 2 or not parts[0].isdigit():
            skipped += 1                      # attrition-ok: ps header or a malformed row
            continue
        if "python" not in Path(parts[1]).name:
            skipped += 1                      # attrition-ok: not a python process
            continue
        rel = _script_arg(parts[2:], root)
        if rel is None:
            skipped += 1                      # attrition-ok: no repo script in argv (-c, -m, REPL)
            continue
        by_script.setdefault(rel, []).append(int(parts[0]))

    daemons: list[Daemon] = []
    for rel, pids in sorted(by_script.items()):
        starts = [s for s in (proc_start(p) for p in pids) if s is not None]
        if not starts:
            skipped += 1                      # attrition-ok: every pid exited mid-scan
            continue
        started = min(starts)
        age_h = (now - started) / 3600.0
        if age_h < min_uptime_h:
            skipped += 1                      # attrition-ok: too young to hold a stale value
            continue
        daemons.append(Daemon(rel, tuple(sorted(pids)), started, age_h))
    return daemons, attempted, skipped


def _script_arg(argv: Iterable[str], root: Path) -> str | None:
    """The repo-relative .py this argv is running, if any."""
    for a in argv:
        if a.startswith("-") or not a.endswith(".py"):
            continue
        cand = Path(a)
        p = cand if cand.is_absolute() else root / cand
        try:
            if p.exists():
                return str(p.resolve().relative_to(root.resolve()))
        except (OSError, ValueError):
            return None
    return None


# ---------------------------------------------------------------------------------------------
# static analysis
# ---------------------------------------------------------------------------------------------
class _Analyser:
    """Resolves artifact reads across module boundaries, memoised per root.

    Kept as a class purely so the parse/resolve caches die with the run. A module-level cache
    would make a long-lived importer of THIS module hold a stale view of the tree -- which would
    be this module committing its own defect.
    """

    def __init__(self, root: Path) -> None:
        self.root = root
        self._parsed: dict[Path, ast.Module | None] = {}
        self._reads: dict[tuple[str, str], tuple[frozenset[str], bool]] = {}

    # -- parsing ------------------------------------------------------------------------
    def parse(self, path: Path) -> ast.Module | None:
        if path not in self._parsed:
            try:
                self._parsed[path] = ast.parse(path.read_text("utf-8", errors="ignore"))
            except (OSError, SyntaxError, ValueError):
                # A module we cannot parse is UNKNOWN, not clean. The caller counts it as a skip
                # so it lands in the attrition figure rather than vanishing (L1.60).
                self._parsed[path] = None
        return self._parsed[path]

    def resolve_module(self, dotted: str) -> Path | None:
        if dotted.split(".")[0] not in _FIRST_PARTY:
            return None
        for cand in (self.root / (dotted.replace(".", "/") + ".py"),
                     self.root / dotted.replace(".", "/") / "__init__.py"):
            if cand.exists():
                return cand
        return None

    def import_closure(self, entry: Path, seen: set[Path] | None = None) -> set[Path]:
        """Repo-local modules an entry point imports, transitively."""
        seen = set() if seen is None else seen
        if entry in seen or not entry.exists():
            return seen
        seen.add(entry)
        tree = self.parse(entry)
        if tree is None:
            return seen
        for node in ast.walk(tree):
            mods: set[str] = set()
            if isinstance(node, ast.Import):
                mods = {a.name for a in node.names}
            elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
                mods = {node.module}
            for m in mods:
                target = self.resolve_module(m)
                if target is not None:
                    self.import_closure(target, seen)
        return seen

    # -- artifact resolution ------------------------------------------------------------
    def _bindings(self, mod: Path) -> dict[str, tuple[Path, str]]:
        """Imported name -> (defining module, original name). THE FIX FOR BUG 1.

        Without this, ``from libs.x import f`` followed by ``_V = f()`` is invisible -- and that
        is the majority shape on this desk, which is why the first prototype scored 0 of 3.
        """
        tree = self.parse(mod)
        out: dict[str, tuple[Path, str]] = {}
        if tree is None:
            return out
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and not node.level:
                target = self.resolve_module(node.module)
                if target is None:
                    continue
                for a in node.names:
                    out[a.asname or a.name] = (target, a.name)
        return out

    def _module_constants(self, mod: Path) -> dict[str, set[str]]:
        """Module-level names bound to artifact-looking path literals."""
        tree = self.parse(mod)
        out: dict[str, set[str]] = {}
        if tree is None:
            return out
        for node in tree.body:
            if not isinstance(node, ast.Assign):
                continue
            lits = _artifact_literals(node)
            if not lits:
                continue
            for tgt in node.targets:
                if isinstance(tgt, ast.Name):
                    out[tgt.id] = lits
        return out

    def function_reads(self, mod: Path, name: str, depth: int = 0,
                       stack: frozenset[tuple[str, str]] = frozenset(),
                       ) -> tuple[frozenset[str], bool]:
        """(artifacts, reads_something) for a function, followed transitively across modules."""
        key = (str(mod), name)
        if key in self._reads:
            return self._reads[key]
        if key in stack or depth > _MAX_DEPTH:
            return frozenset(), False
        tree = self.parse(mod)
        if tree is None:
            return frozenset(), False
        fn = next((n for n in ast.walk(tree)
                   if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef) and n.name == name),
                  None)
        if fn is None:
            return frozenset(), False
        self._reads[key] = (frozenset(), False)      # cycle guard before recursing
        arts, reads = self._scan_calls(fn, mod, tree, depth, stack | {key})
        out = (frozenset(arts), reads)
        self._reads[key] = out
        return out

    def _scan_calls(self, node: ast.AST, mod: Path, tree: ast.Module, depth: int,
                    stack: frozenset[tuple[str, str]]) -> tuple[set[str], bool]:
        """Artifacts and read-ness of an arbitrary subtree, following first-party calls."""
        consts = self._module_constants(mod)
        binds = self._bindings(mod)
        local = {n.name for n in ast.walk(tree)
                 if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef)}
        arts: set[str] = set(_artifact_literals(node))
        for nm in {x.id for x in ast.walk(node) if isinstance(x, ast.Name)}:
            arts |= consts.get(nm, set())
        reads = False
        for call in (n for n in ast.walk(node) if isinstance(n, ast.Call)):
            fn = call.func
            attr = fn.attr if isinstance(fn, ast.Attribute) else (
                fn.id if isinstance(fn, ast.Name) else "")
            if attr in READ_VERBS:
                reads = True
            if not isinstance(fn, ast.Name):
                continue
            if fn.id in local:
                sub_arts, sub_reads = self.function_reads(mod, fn.id, depth + 1, stack)
            elif fn.id in binds:
                target, orig = binds[fn.id]
                sub_arts, sub_reads = self.function_reads(target, orig, depth + 1, stack)
            else:
                continue
            arts |= sub_arts
            reads = reads or sub_reads
        return arts, reads

    # -- the detector -------------------------------------------------------------------
    def frozen_reads(self, mod: Path) -> list[FrozenRead]:
        """Every binding in ``mod`` whose value is decided once, at import."""
        tree = self.parse(mod)
        if tree is None:
            return []
        try:
            rel = str(mod.resolve().relative_to(self.root.resolve()))
        except ValueError:
            rel = str(mod)
        lines = mod.read_text("utf-8", errors="ignore").splitlines()
        found: list[FrozenRead] = []
        frozen_names: set[str] = set()
        # THE REFINEMENT THAT KEEPS THIS FENCE FROM CRYING WOLF, and it was learned the hard way:
        # a module-scope binding is only frozen IN EFFECT if nothing re-runs its producer later.
        # `run_recorder.py` seeds `_SYMBOLS = _universe()` at import AND re-polls `_universe()`
        # inside its loop, so the seed is a seed, not a frozen value. Reporting it would have made
        # the first run 2 false alarms out of 3 -- and a detector that cries wolf gets acked into
        # silence (R0356). See `_live_reread_lines`.
        rereads = _live_reread_lines(tree)

        for node in tree.body:
            if isinstance(node, ast.Assign):
                arts, reads = self._scan_calls(node, mod, tree, 0, frozenset())
                if not reads:
                    continue
                names = [t.id for t in node.targets if isinstance(t, ast.Name)]
                if not names:
                    continue
                refresh = max((rereads.get(p, 0) for p in _called_names(node)), default=0)
                for nm in names:
                    found.append(FrozenRead(rel, nm, node.lineno, "module-scope",
                                            tuple(sorted(arts)), _exempt_reason(lines, node.lineno),
                                            refresh))
                    frozen_names.add(nm)
            elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                if not _is_memoised(node):
                    continue
                m_arts, m_reads = self.function_reads(mod, node.name)
                if m_reads:
                    found.append(FrozenRead(rel, node.name, node.lineno, "memoized",
                                            tuple(sorted(m_arts)),
                                            _exempt_reason(lines, node.lineno)))

        # DEFAULT ARGUMENTS ARE EVALUATED ONCE, AT DEFINITION -- the double-freeze. A frozen
        # name rebound as a default (``def f(..., floors=FLOORS)``) cannot be retuned even by a
        # caller that re-read the artifact, because the default was captured at import.
        by_name = {f.name: f for f in found}
        for fnode in ast.walk(tree):
            if not isinstance(fnode, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            defaults = [*fnode.args.defaults,
                        *[d for d in fnode.args.kw_defaults if d is not None]]
            for d in defaults:
                if not isinstance(d, ast.Name) or d.id not in frozen_names:
                    continue
                src = by_name.get(d.id)
                found.append(FrozenRead(rel, f"{fnode.name}(...={d.id})", fnode.lineno,
                                        "default-arg", src.artifacts if src else (),
                                        _exempt_reason(lines, fnode.lineno)))
        return found


def _called_names(node: ast.AST) -> set[str]:
    """Bare-name functions called anywhere under ``node``."""
    return {c.func.id for c in ast.walk(node)
            if isinstance(c, ast.Call) and isinstance(c.func, ast.Name)}


def _live_reread_lines(tree: ast.Module) -> dict[str, int]:
    """function name -> line where it is called from INSIDE some function body.

    A call at module scope runs once, at import. A call inside a function body can run again --
    every tick of a loop, every rebalance, every request -- so the artifact behind it has a live
    re-read path and the import-time binding is a SEED rather than a frozen value.

    THIS IS DELIBERATELY GENEROUS, and the direction is chosen rather than accidental. It does
    not prove the enclosing function is ever called, nor that it is called on a useful cadence;
    it proves the desk WROTE a re-read path. A false REFRESHED costs one missed row in a report;
    a false FROZEN-STALE costs the fence's credibility, and a fence nobody believes enforces
    nothing (L1.43). The evidence is published as a line number precisely so a human can check
    the cadence claim rather than take it on trust.
    """
    out: dict[str, int] = {}
    for fn in ast.walk(tree):
        if not isinstance(fn, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        for call in ast.walk(fn):
            if not isinstance(call, ast.Call) or not isinstance(call.func, ast.Name):
                continue
            if call.func.id == fn.name:
                continue                       # recursion is not a re-read path
            out.setdefault(call.func.id, call.lineno)
    return out


def _artifact_literals(node: ast.AST) -> set[str]:
    """String constants under ``node`` that look like repo artifact paths."""
    out: set[str] = set()
    for n in ast.walk(node):
        if not isinstance(n, ast.Constant) or not isinstance(n.value, str):
            continue
        v = n.value
        if 3 < len(v) < 200 and "\n" not in v and (
                "data/" in v or v.startswith("ops/") or "/ops/" in v):
            out.add(v)
    return out


def _is_memoised(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    names: set[str] = set()
    for d in node.decorator_list:
        if isinstance(d, ast.Name):
            names.add(d.id)
        elif isinstance(d, ast.Attribute):
            names.add(d.attr)
        elif isinstance(d, ast.Call):
            f = d.func
            names.add(f.attr if isinstance(f, ast.Attribute)
                      else (f.id if isinstance(f, ast.Name) else ""))
    return bool(names & {"cache", "lru_cache", "cached_property"})


def _exempt_reason(lines: list[str], lineno: int) -> str:
    """``# frozen-ok: <reason>`` on the line or the two above it. A bare tag is not a tag."""
    for i in range(max(0, lineno - 3), min(len(lines), lineno)):
        m = _EXEMPT_TAG.search(lines[i])
        if m:
            return m.group(1).strip()
    return ""


# ---------------------------------------------------------------------------------------------
# the report
# ---------------------------------------------------------------------------------------------
def build_report(root: Path | None = None, *, now: float | None = None) -> Report:
    """Grade every (live daemon, frozen read) pair on the box.

    ``root`` defaults to the BOX's main checkout, not this process's tree: a linked worktree has
    a gitignored ``data/`` and the running daemons import the main checkout's modules, so a
    worktree run that measured its own tree would fabricate a verdict about source nothing is
    executing and artifacts that do not exist (R0521, the standing worktree-blind-fence defect).
    """
    here = Path(__file__).resolve().parent.parent.parent if root is None else root
    box, basis = data_root(here)
    now = time.time() if now is None else now

    rep = Report(status=UNMEASURED, basis=basis, root=str(box))
    daemons, attempted, skipped = live_daemons(box, now=now)
    rep.attempted, rep.skipped = attempted, skipped
    rep.daemons = daemons

    if not daemons:
        # AN HONEST DECLARED REFUSAL, NOT A VACUOUS PASS. Off the box -- CI, a fresh clone, a
        # container that cannot see the process table -- there is genuinely nothing of ours
        # running, and the status says so rather than reporting a clean desk. Distinct from OK,
        # and structurally absent from PASSING.
        rep.status = NO_DAEMONS_HERE
        rep.notes.append("no long-lived repo processes visible from this vantage point; "
                         "this is a statement about the vantage point, never about the desk")
        return rep

    an = _Analyser(box)
    seen: set[tuple[str, str, int, str]] = set()
    for d in daemons:
        entry = box / d.script
        for mod in sorted(an.import_closure(entry)):
            rep.attempted += 1
            if an.parse(mod) is None:
                rep.skipped += 1              # attrition-ok: unparseable module, counted not hidden
                continue
            for fr in an.frozen_reads(mod):
                key = (d.script, fr.module, fr.lineno, fr.name)
                if key in seen:
                    continue
                seen.add(key)
                rep.pairs.extend(_grade(d, fr, box, now))

    if rep.n_stale:
        rep.status = UNVERIFIABLE
    elif rep.n_unresolved or rep.n_source_drifted:
        # NOT folded into UNVERIFIABLE, and not waved through either. "This daemon holds a value
        # whose input moved" and "this daemon is running source we did not analyse" are different
        # claims needing different repairs (move the read / restart the daemon), and only the
        # first is this law's finding. Both are refusals to certify, so neither reads as OK.
        rep.status = UNRESOLVED
    elif rep.n_pairs:
        rep.status = OK
    else:
        # Daemons ARE running and not one frozen read was found. That is a real possible state,
        # but it is also exactly what a broken analyser returns -- and this one returned it once
        # already, against three hand-verified positives. It reads UNMEASURED, never OK (L1.28a).
        rep.status = UNMEASURED
        rep.notes.append(f"{len(daemons)} daemon(s) running and ZERO frozen reads found -- "
                         "verify the analyser against tests/ops/test_value_staleness.py's "
                         "positive controls before reading this as a clean desk (L1.25)")
    return rep


def _grade(d: Daemon, fr: FrozenRead, box: Path, now: float) -> list[Pair]:
    # THE FALSE GREEN THIS FENCE WOULD OTHERWISE CREATE WITH ITS OWN REPAIRS, and it is the
    # subtlest thing in this module. Every verdict below is derived from SOURCE ON DISK, while
    # the claim being made is about VALUES IN A RUNNING PROCESS. Patch a frozen read into a
    # refreshing one and this fence flips to REFRESHED the instant the file is saved -- while
    # the daemon goes right on holding the frozen value until it restarts. The fix would report
    # itself fixed, which is L0004 exactly ("the --hold-top 3000 churn fix sat committed and dead
    # for 2 days") wearing a green checkmark. If the module's source post-dates the process, no
    # static verdict about that process's values is valid, and saying so is the only honest move.
    # This is the seam where this fence and `check_stale_daemons` compose: it needs the code
    # answer to earn the right to give a value answer.
    src = box / fr.module
    try:
        if src.stat().st_mtime > d.started:
            return [Pair(d.script, fr, SOURCE_DRIFTED,
                         drift_h=(src.stat().st_mtime - d.started) / 3600.0,
                         why=(f"{fr.module} was edited "
                              f"{(src.stat().st_mtime - d.started) / 3600.0:.1f}h after this "
                              "process started, so the running process is executing DIFFERENT "
                              "source than was analysed; no value verdict is valid until it "
                              "restarts (compose with check_stale_daemons)"))]
    except OSError:
        pass          # attrition-ok: unreadable source falls through to the value verdicts below
    if fr.exempt_reason:
        return [Pair(d.script, fr, EXEMPT, why=f"frozen-ok: {fr.exempt_reason}")]
    if fr.refresh_line:
        return [Pair(d.script, fr, REFRESHED,
                     why=(f"import-time binding is a SEED: its producer is re-run at "
                          f"{fr.module}:{fr.refresh_line}, inside a function body"))]
    if not fr.resolved:
        return [Pair(d.script, fr, FROZEN_UNRESOLVED,
                     why=("reads an artifact whose path is not statically resolvable; "
                          "UNRESOLVED is counted, never dropped (L1.28a)"))]
    out: list[Pair] = []
    for a in fr.artifacts:
        p = box / a.lstrip("/")
        try:
            mtime = p.stat().st_mtime
        except OSError:
            out.append(Pair(d.script, fr, FROZEN_UNRESOLVED, artifact=a,
                            why="named artifact is not readable from here"))
            continue
        if mtime > d.started:
            out.append(Pair(d.script, fr, FROZEN_STALE, artifact=a,
                            drift_h=(mtime - d.started) / 3600.0,
                            why=(f"{a} changed {(mtime - d.started) / 3600.0:.1f}h AFTER this "
                                 f"process started (up {d.age_h:.1f}h); the in-memory value "
                                 "cannot be proven to match disk")))
        else:
            out.append(Pair(d.script, fr, FROZEN_CURRENT, artifact=a,
                            why="artifact unchanged since process start -- exposed, not bitten"))
    return out

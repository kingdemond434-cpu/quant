"""DORMANCY HUNTER -- the standing version of the discovery that reframed 2026-07-30.

WHY THIS EXISTS. On 2026-07-30 the desk's named "highest-ROI MISSING subsystems" -- research
meta-learning, capital-allocation learning, agent health monitoring, information-advantage
measurement, an alpha-decay lab, experiment ERV ranking -- turned out to be BUILT ALREADY with
ZERO CALLERS. That was found because someone happened to grep for callers. Depending on a human
noticing is not a mechanism, and the class of failure is large enough to deserve one: a capability
that exists and never executes is indistinguishable, from the outside, from a capability that was
never built -- except that the desk has already paid for it.

THE PRIORITY THIS ENCODES (principal, 2026-07-30): **find unused capability before inventing new
capability.** So this module answers, mechanically and every cycle, the question that produced the
find: *which modules does nothing import, and which scripts does nothing schedule?*

REACHABILITY, not popularity. A module is DORMANT only if NOTHING outside its own package imports
it AND nothing schedules it. That is deliberately strict in one direction and forgiving in the
other: a library imported by one live caller is reachable and therefore not dormant, however small
it is. The desk does not want to churn small components -- it wants to find the ones that are
disconnected.

WHAT IT DOES NOT DO: it never deletes, retires, or edits anything. It reports, with the exact
proving command, and the disposition (activate / merge / retire) stays a decision made under the
L2.9 exits with a written reason. An auto-retiring sweep would eventually delete a capability that
was dormant only because its unlock condition had not arrived yet -- which is precisely the state
several of these are legitimately in (0 validated alphas).

Pure stdlib. import from libs.self_improvement.dormancy.
"""
from __future__ import annotations

import ast
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]

# Packages whose modules are expected to be imported from outside; a module here with no external
# importer is a genuine reachability finding rather than a naming artifact.
_LIB_SCOPE = ("libs/self_improvement", "libs/alpha", "libs/signal_engine", "libs/portfolio",
              "libs/discovery", "libs/autodiscovery", "libs/features", "libs/store",
              "libs/monitoring", "libs/research", "libs/validation", "libs/risk",
              "libs/execution", "libs/costs", "libs/regime", "libs/backtest")

# Scripts that are legitimately invoked by a human or another organ on demand rather than by a
# scheduler. Listed EXPLICITLY with a reason, because "it's a CLI tool" is otherwise the excuse
# that would let any dormant script escape the check.
_ON_DEMAND: dict[str, str] = {
    "scripts/research_memory.py": "CLI logger called ad hoc by every organ (doctrine duty)",
    "scripts/recommendations.py": "CLI ledger writer called by organs at disposition time",
    "scripts/track_findings.py": "CLI findings writer called by organs",
    "scripts/blind_spot.py": "CLI origin logger called by organs",
    "scripts/run_ci.py": "developer/commit gate, invoked by hand and by pre-push",
    "scripts/run_mutation.py": "measurement harness, invoked when a bar needs re-measuring",
    "scripts/check_scheduler_manifest.py": "invoked by deploy/reconstitute_cron.sh and by hand",
}


@dataclass
class Dormant:
    path: str
    kind: str                      # "module" | "script"
    reason: str
    proving_command: str
    lines: int = 0
    suggested_exit: str = "activate-or-record-unlock-condition"


@dataclass
class DormancyReport:
    dormant: list[Dormant] = field(default_factory=list)
    n_modules_scanned: int = 0
    n_scripts_scanned: int = 0

    @property
    def counts(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for d in self.dormant:
            out[d.kind] = out.get(d.kind, 0) + 1
        return out


def _grep(pattern: str, *paths: str) -> list[str]:
    """rg-free grep -rl; returns matching file paths (empty on no match)."""
    try:
        p = subprocess.run(["grep", "-rl", "-E", pattern, *paths],
                           cwd=_ROOT, capture_output=True, text=True, timeout=60, check=False)
    except (subprocess.TimeoutExpired, OSError):
        return []
    return [ln for ln in (p.stdout or "").splitlines() if ln.strip()]


def _external_importers(rel: str) -> list[str]:
    """Files OUTSIDE the module's own package that import it."""
    pkg = str(Path(rel).parent)
    mod = Path(rel).stem
    dotted = pkg.replace("/", ".") + "." + mod
    pattern = rf"(import\s+{re.escape(dotted)}|from\s+{re.escape(dotted)}\s+import|"
    pattern += rf"from\s+{re.escape(pkg.replace('/', '.'))}\s+import\s+[^\n]*\b{re.escape(mod)}\b)"
    hits = _grep(pattern, "scripts", "libs", "app", "api", "tests")
    # Its own package and its own tests do not make it reachable from the running desk.
    return [h for h in hits if not h.startswith(pkg) and not h.startswith("tests/")]


def _scheduled(rel: str) -> bool:
    name = Path(rel).name
    for src in ("ops/crontab.manifest", "scripts/run_cadence.py",
                "scripts/daily_research_cycle.py", "scripts/research_cycle.py"):
        p = _ROOT / src
        if p.exists() and name in p.read_text("utf-8", errors="ignore"):
            return True
    # A unit or shell runner that names it also counts as scheduling.
    return bool(_grep(re.escape(name), "ops"))


def _invoked_by_a_script(rel: str) -> bool:
    """Another script importing it or shelling out to it makes it reachable."""
    name = Path(rel).name
    stem = Path(rel).stem
    hits = _grep(rf"({re.escape(name)}|import\s+{re.escape(stem)}\b)", "scripts", "libs")
    return bool([h for h in hits if h != rel])


def scan(*, include_modules: bool = True, include_scripts: bool = True) -> DormancyReport:
    """Find capabilities nothing imports and nothing schedules."""
    rep = DormancyReport()
    if include_modules:
        for pkg in _LIB_SCOPE:
            d = _ROOT / pkg
            if not d.is_dir():
                continue
            for f in sorted(d.glob("*.py")):
                if f.name.startswith("_"):
                    continue
                rel = f"{pkg}/{f.name}"
                rep.n_modules_scanned += 1
                if _external_importers(rel):
                    continue
                rep.dormant.append(Dormant(
                    path=rel, kind="module",
                    reason="no module outside its own package imports it",
                    proving_command=(f"grep -rl '{pkg.replace('/', '.')}.{f.stem}' scripts/ libs/ "
                                     f"| grep -v {pkg}/"),
                    lines=len(f.read_text('utf-8', errors='ignore').splitlines())))
    if include_scripts:
        sd = _ROOT / "scripts"
        for f in sorted(sd.glob("*.py")):
            rel = f"scripts/{f.name}"
            rep.n_scripts_scanned += 1
            if rel in _ON_DEMAND or _scheduled(rel) or _invoked_by_a_script(rel):
                continue
            rep.dormant.append(Dormant(
                path=rel, kind="script",
                reason="nothing schedules it and no other script invokes or imports it",
                proving_command=(f"grep -c {f.name} ops/crontab.manifest scripts/run_cadence.py "
                                 f"scripts/daily_research_cycle.py"),
                lines=len(f.read_text('utf-8', errors='ignore').splitlines())))
    return rep


def summarise(rep: DormancyReport) -> dict[str, object]:
    """Report shape for the intelligence cycle. Biggest first -- a 500-line dormant subsystem is
    a larger paid-for-and-unused asset than a 20-line one."""
    ranked = sorted(rep.dormant, key=lambda d: -d.lines)
    return {
        "scanned": {"modules": rep.n_modules_scanned, "scripts": rep.n_scripts_scanned},
        "counts": rep.counts,
        "priority": "find unused capability BEFORE inventing new capability (principal 2026-07-30)",
        "exits": "activate / merge / retire -- never auto-deleted; several are legitimately "
                 "waiting on an unlock condition (e.g. 0 validated alphas) and that is a DATA gap",
        "dormant": [{"path": d.path, "kind": d.kind, "lines": d.lines, "reason": d.reason,
                     "proving_command": d.proving_command} for d in ranked[:40]],
        "total_dormant_lines": sum(d.lines for d in rep.dormant),
    }


# --------------------------------------------------------------------------------------------
# THREE STRANDING STATES (L1.54(a)) -- because "does anything import it" answers ONE of them.
#
# MEASURED 2026-08-08, on this module's own author. A consumer was written for four orphan
# modules; three were genuinely wired and the fourth, `convergence`, stayed orphaned because the
# new consumer DESCRIBED its verdict in a hand-typed string instead of calling it. The importer
# count would eventually have read 1 and the scan would have gone quiet -- a capability reported
# as reachable while nothing on the desk had ever run it.
#
# So the states are separated, and the fix differs for each:
#
#     ORPHAN              nothing imports it            -> build a consumer
#     INERT               a consumer exists, never ran  -> schedule it (L1.49)
#     CONVERSION_FAILURE  it runs, output changes nothing -> wire the output to a decision
#
# The third is the one that hides: it passes every test an importer count can run.

STRANDING_STATES: tuple[str, ...] = ("ORPHAN", "INERT", "CONVERSION_FAILURE", "WIRED", "UNMEASURED")


def stranding(*, importers: int, callers: int, executions: int | None,
              output_consumers: int | None) -> tuple[str, str]:
    """(state, why) for one capability. PURE -- takes counts, returns a verdict.

    `executions` and `output_consumers` are `int | None` on purpose and the None case is the
    whole point of L1.28a: a capability nobody has instrumented is UNMEASURED, never WIRED.
    Defaulting an unknown execution count to "probably ran" is how a dormant subsystem reports
    itself healthy, and it is the exact failure this module was built to end.

    ORDER OF CHECKS IS LOAD-BEARING. Callers are tested before executions, because a module that
    is imported for its NAME but never called is an ORPHAN wearing an importer -- and that is the
    case measured on 2026-08-08, not a hypothetical.
    """
    if importers <= 0:
        return "ORPHAN", "nothing imports it -- the fix is a consumer, not a schedule"
    if callers <= 0:
        return "ORPHAN", (f"{importers} importer(s) but ZERO call sites: imported for its name and "
                          "never invoked. An importer count would read this as reachable")
    if executions is None:
        return "UNMEASURED", (f"{callers} call site(s), but no execution record exists. That is an "
                              "ABSENCE OF EVIDENCE (L1.28a), never a clean bill -- instrument the "
                              "consumer before believing this runs")
    if executions <= 0:
        return "INERT", (f"{callers} call site(s) that have NEVER executed -- a gate that never "
                         "ran is a claim the desk cannot cash (L1.49). The fix is a schedule")
    if output_consumers is None:
        return "UNMEASURED", (f"executed {executions}x, but nothing measures whether its output is "
                              "read. The expensive stranding state is invisible from here")
    if output_consumers <= 0:
        return "CONVERSION_FAILURE", (
            f"executed {executions}x and its output changes NOTHING downstream. This passes every "
            "test an importer count can run, which is why it is the state that hides -- the fix "
            "is to wire the output to a decision, not to run it more often")
    return "WIRED", (f"{callers} call site(s), {executions} execution(s), {output_consumers} "
                     "downstream consumer(s) of its output")


def call_sites(rel: str) -> list[str]:
    """Files that IMPORT this module and actually INVOKE one of the names they imported.

    PARSED WITH `ast`, NOT MATCHED WITH A REGEX, and that is a correction rather than a
    preference. The regex version shipped two false-positive bugs in one hour, both silent and
    both in the flattering direction -- it read ZERO imported names and therefore reported the
    module never-called:

        `from x import (\n  render,\n  update,\n)`      the `(` ended the capture
        `from x import name  # noqa: E402`             the comment rode into the name

    Each made a WIRED module look stranded. A heuristic whose failure mode is "sees nothing,
    concludes nothing is used" manufactures findings, and a findings list that is mostly wrong is
    how a fence gets ignored -- which costs more than never having built it.

    The `ast` walk asks the question exactly: which names did this file import from the module,
    and does a Call node anywhere name one of them (directly, or as an attribute of the module).
    A file that fails to parse is skipped rather than guessed at.
    """
    stem = Path(rel).stem
    out: list[str] = []
    for f in _external_importers(rel):
        try:
            tree = ast.parse((_ROOT / f).read_text("utf-8", errors="ignore"))
        except (OSError, SyntaxError, ValueError):
            continue
        names: set[str] = set()
        aliases: set[str] = {stem}
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and stem in (node.module or "").split("."):
                names |= {a.asname or a.name for a in node.names}
            elif isinstance(node, ast.ImportFrom):
                # THE MODULE-AS-ALIAS FORM, which is how the desk imports half of `libs/research`:
                # `from libs.research import marginal_admission as ma` binds the MODULE, not a
                # name inside it, so every later use is `ma.evaluate(...)`. Missing this branch
                # flagged two genuinely wired modules -- the third false positive from the same
                # heuristic, and the reason it is now an exhaustive walk over import FORMS rather
                # than the one form that happened to be in front of me.
                aliases |= {a.asname or a.name for a in node.names if a.name == stem}
            elif isinstance(node, ast.Import):
                for a in node.names:
                    if stem in a.name.split("."):
                        aliases.add(a.asname or a.name.split(".")[-1])
        called = False
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            fn = node.func
            # WALK THE WHOLE ATTRIBUTE CHAIN TO ITS ROOT NAME. `canary_mod.CanaryState.load(...)`
            # is Attribute(Attribute(Name)), so stopping at the first `.value` missed it and
            # reported a live money-path guard as stranded -- the fourth shape this check got
            # wrong. Root-walking makes the depth irrelevant instead of adding a case per depth.
            root = fn
            while isinstance(root, ast.Attribute):
                root = root.value
            if isinstance(root, ast.Name) and (root.id in names or root.id in aliases):
                called = True
        # A name used as a TYPE or a base class is a real use even with no Call node -- counting
        # it as stranded would flag every dataclass and protocol the desk imports.
        if not called and names:
            called = any(
                isinstance(n, ast.Name) and n.id in names and not isinstance(n.ctx, ast.Store)
                for n in ast.walk(tree)) and any(
                isinstance(n, ast.AnnAssign | ast.ClassDef | ast.arg) for n in ast.walk(tree))
        if called:
            out.append(f)
    return out


def imported_but_never_called(*, scope: tuple[str, ...] = _LIB_SCOPE) -> list[Dormant]:
    """Modules the plain scan calls REACHABLE that nothing actually invokes.

    This is the blind spot in `scan()`, and it is a measured one rather than a suspected one: the
    plain scan asks "does anything import it", so a consumer that imports a module and then only
    mentions it in prose flips it from dormant to reachable while the desk has still never run it.
    A module in this list is an ORPHAN with an importer, and the fix is the orphan fix -- call it.
    """
    out: list[Dormant] = []
    for pkg in scope:
        d = _ROOT / pkg
        if not d.is_dir():
            continue
        for f in sorted(d.glob("*.py")):
            if f.name.startswith("_"):
                continue
            rel = f"{pkg}/{f.name}"
            importers = _external_importers(rel)
            if not importers or call_sites(rel):
                continue
            state, why = stranding(importers=len(importers), callers=0,
                                   executions=None, output_consumers=None)
            out.append(Dormant(
                path=rel, kind=f"module:{state}", reason=why,
                proving_command=f"grep -rn '{f.stem}' {' '.join(importers[:3])}",
                lines=len(f.read_text("utf-8", errors="ignore").splitlines()),
                suggested_exit="call it from the consumer that already imports it"))
    return out

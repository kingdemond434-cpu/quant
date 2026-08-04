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

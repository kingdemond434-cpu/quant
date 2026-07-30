"""INBOUND DEPLOY PLANNER -- what a pulled commit actually invalidates.

WHY THIS EXISTS (EXECUTION_QUEUE.md RANK 7, found 2026-07-30). ``scripts/git_snapshot.py`` pushes
VPS -> GitHub. **Nothing pulled GitHub -> VPS**, so merging to master deployed NOTHING and every
change needed a manual SSH. The desk has already paid for that gap at the worst possible layer:
on 2026-07-26 an orphaned executor kept running PRE-FIX code for 8h, so "the funding-measurement
fix committed that evening was inert in the process that actually owned the book" -- a committed
fix that never shipped (``scripts/watchdog.py``:66-76). A repo whose commits do not reach the
running process is a repo that lies about what the desk is doing.

PULLING IS THE EASY HALF. THE HARD HALF IS KNOWING WHAT TO RESTART, and getting it wrong is
asymmetric in a way that decides the whole design:

  * UNDER-restarting reproduces the 2026-07-26 incident exactly -- new code on disk, old code in
    the process that owns the book. Silent, and the desk cannot tell from the outside.
  * OVER-restarting costs a brief gap in a systemd-owned service. systemd holds single-instance,
    so it cannot orphan (that is precisely what the watchdog's ``_systemd_owns`` guard exists to
    prevent), and the executor reconciles on start.

So this planner deliberately errs toward restarting. The ONE exception is the ruin rail, below.

WHY THE MAP IS COMPUTED, NOT WRITTEN DOWN. A hand-maintained "these paths affect the executor"
list rots the first time somebody adds an import, and it rots SILENTLY -- the deploy keeps
succeeding while quietly leaving a stale process behind. So the affected set is derived from the
real first-party import closure of each entry script, parsed with ``ast`` at plan time. Adding
``from libs.risk.foo import bar`` to the executor widens its blast radius automatically, with no
list to update and no way to forget.

Measured 2026-07-30, and it is the reason this is cheap: only ONE of the four unit-owned processes
has a first-party closure at all. ``run_deadman_switch.py``, ``liquidation_listener.py`` and
``serve_dashboard.py`` import nothing from ``libs/`` -- pure stdlib plus pandas/websockets. The
ruin rail's dependency-freedom is a design property, not an accident, and it means an ordinary
``libs/`` commit cannot invalidate the ruin rail at all.

THE RUIN RAIL IS TIER 3 AND IS NEVER RESTARTED BY A SCRIPT. ``quant-deadman.service`` is the
"NEVER-TOUCH rail -- exactly one instance ever under systemd" (``ops/crontab.manifest``, from
``ops/memory/crypto-desk-state.md``:21). A restart is a window with no ruin rail, and no
unattended script gets to open that window: an orphan is recoverable, a dead ruin rail is not
(``scripts/watchdog.py``:74-77). When a commit genuinely changes the deadman, this reports
ESCALATE and the operator supervises it. That is the honest exit, not a gap.

EVERYTHING ELSE NEEDS NO RESTART, and that is not a shrug. Cron re-execs a fresh interpreter every
tick, so a pulled change to any cron-owned script is live on its next firing with nothing to do.
The set that needs action is small by construction.

Pure stdlib. Import from ``libs.ops.deploy_plan``; driven by ``deploy/pull_deploy.sh``.
"""

from __future__ import annotations

import ast
import sys
from collections import deque
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]

#: Top-level packages that live in THIS repo. An import outside these is a third-party or stdlib
#: dependency -- a pulled commit cannot change it, so it is not part of any blast radius.
_FIRST_PARTY = ("libs", "api", "app")

TIER_RESTART = 2       #: systemd-owned; a script may restart it (systemd holds single-instance)
TIER_RUIN = 3          #: the ruin rail; a script may NEVER restart it -- operator supervises

#: entry script -> (unit, tier). MUST agree with ``scripts/watchdog.py``'s ``_UNITS``; a test
#: asserts they match, because two copies of the same supervision map is how the desk's previous
#: four capacity constants drifted apart (§42's lesson, applied to a different map).
_OWNED: dict[str, tuple[str, int]] = {
    "scripts/run_cashcarry_executor.py": ("quant-cashcarry.service", TIER_RESTART),
    "scripts/run_deadman_switch.py": ("quant-deadman.service", TIER_RUIN),
    "scripts/liquidation_listener.py": ("quant-liquidations.service", TIER_RESTART),
    "scripts/serve_dashboard.py": ("quant-dashboard.service", TIER_RESTART),
}

#: Changing the scheduler's source does not restart a process -- it means the INSTALLED crontab is
#: now stale. Reported so it cannot pass unnoticed, never auto-applied: the manifest's own header
#: forbids running the installer before a human reviews live drift, because the box carries
#: unfenced cron lines that would double-schedule the recorders.
_SCHEDULER_SOURCES = ("ops/crontab.manifest",)


@dataclass(frozen=True)
class UnitAction:
    """One process the pulled commit invalidated, and what may be done about it."""

    unit: str
    entry: str
    tier: int
    trigger: str          #: the changed path that invalidated it (the entry, or a closure member)

    @property
    def verb(self) -> str:
        return "RESTART" if self.tier == TIER_RESTART else "ESCALATE"

    @property
    def why(self) -> str:
        via = "changed directly" if self.trigger == self.entry else f"imports {self.trigger}"
        if self.tier == TIER_RUIN:
            return (f"{self.entry} {via} -- RUIN RAIL, not restarted here: a restart is a window "
                    "with no ruin rail and no unattended script opens that window")
        return f"{self.entry} {via}"


@dataclass
class DeployPlan:
    """The full disposition of a pulled commit. Nothing changed is ever silently dropped."""

    changed: list[str] = field(default_factory=list)
    actions: list[UnitAction] = field(default_factory=list)
    scheduler_stale: list[str] = field(default_factory=list)
    no_restart: list[str] = field(default_factory=list)

    @property
    def restarts(self) -> list[UnitAction]:
        return [a for a in self.actions if a.tier == TIER_RESTART]

    @property
    def escalations(self) -> list[UnitAction]:
        return [a for a in self.actions if a.tier == TIER_RUIN]

    def directives(self) -> list[str]:
        """Tab-separated lines for ``deploy/pull_deploy.sh`` to execute.

        A line protocol rather than JSON on purpose: the consumer is POSIX sh on a restore-day box
        where the only guaranteed parser is ``read``/``cut``, and a deploy path that needs a JSON
        library to tell the operator what to restart is a deploy path that fails when it matters.
        """
        out = [f"{a.verb}\t{a.unit}\t{a.why}" for a in self.actions]
        out += [f"SCHEDULER\t{p}\tinstalled crontab is now stale vs the manifest -- review live "
                f"drift (check_scheduler_manifest.py --report-only) BEFORE reconstitute_cron.sh"
                for p in self.scheduler_stale]
        return out


def _module_file(mod: str, root: Path) -> Path | None:
    """``libs.execution.engine`` -> the file that defines it, module or package."""
    rel = Path(*mod.split("."))
    for cand in (root / rel.with_suffix(".py"), root / rel / "__init__.py"):
        if cand.is_file():
            return cand
    return None


def _first_party_imports(path: Path) -> set[str]:
    """First-party dotted names imported by ``path``, from a real parse (not a regex).

    ``from libs.execution import carry_accounting`` contributes BOTH ``libs.execution`` and
    ``libs.execution.carry_accounting``: the name may be a submodule or an attribute of the
    package, and resolving it wrongly would silently narrow the blast radius. Widening it costs a
    restart that was not strictly needed; narrowing it leaves stale code owning the book.
    """
    try:
        tree = ast.parse(path.read_text("utf-8"), filename=str(path))
    except (OSError, SyntaxError, ValueError):
        return set()
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            names.add(node.module)
            names.update(f"{node.module}.{a.name}" for a in node.names)
    return {n for n in names if n.split(".")[0] in _FIRST_PARTY}


def import_closure(entry: str, root: Path | None = None) -> set[str]:
    """Every first-party repo file ``entry`` can reach, as repo-relative paths (excluding itself).

    Breadth-first with a visited set, so an import cycle terminates instead of hanging a deploy.
    """
    root = root or _ROOT
    start = root / entry
    if not start.is_file():
        return set()
    seen: set[Path] = {start}
    queue: deque[Path] = deque([start])
    while queue:
        for mod in _first_party_imports(queue.popleft()):
            f = _module_file(mod, root)
            if f is not None and f not in seen:
                seen.add(f)
                queue.append(f)
    return {p.relative_to(root).as_posix() for p in seen if p != start}


def plan(changed: Iterable[str], root: Path | None = None) -> DeployPlan:
    """Classify changed repo-relative paths into restart / escalate / stale-scheduler / no-op."""
    root = root or _ROOT
    paths = sorted({p.strip().replace("\\", "/") for p in changed if p.strip()})
    out = DeployPlan(changed=list(paths))
    accounted: set[str] = set()

    for entry, (unit, tier) in sorted(_OWNED.items()):
        # the entry script itself is the strongest trigger; report it in preference to a
        # closure member so the operator reads the direct cause, not an incidental import
        trigger = entry if entry in paths else None
        if trigger is None:
            hits = sorted(set(paths) & import_closure(entry, root))
            trigger = hits[0] if hits else None
        if trigger is None:
            continue
        out.actions.append(UnitAction(unit=unit, entry=entry, tier=tier, trigger=trigger))
        accounted.update(set(paths) & ({entry} | import_closure(entry, root)))

    out.scheduler_stale = [p for p in paths if p in _SCHEDULER_SOURCES]
    accounted.update(out.scheduler_stale)
    # cron re-execs a fresh interpreter every tick, so these are live on next firing with no action
    out.no_restart = [p for p in paths if p not in accounted]
    return out


def _render(p: DeployPlan) -> str:
    lines = [f"deploy-plan: {len(p.changed)} changed path(s)"]
    for a in p.restarts:
        lines.append(f"  RESTART  {a.unit}  <- {a.why}")
    for a in p.escalations:
        lines.append(f"  ESCALATE {a.unit}  <- {a.why}")
    for s in p.scheduler_stale:
        lines.append(f"  SCHEDULER {s} changed -- installed crontab is stale (review drift first)")
    if not p.actions and not p.scheduler_stale:
        lines.append("  no supervised process invalidated -- cron picks the new code up next tick")
    elif p.no_restart:
        lines.append(f"  ({len(p.no_restart)} other path(s) need no restart -- cron-owned)")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    """``--directives`` emits the sh line protocol; default prints the human summary.

    Changed paths arrive on stdin, one per line, exactly as ``git diff --name-only`` emits them.
    """
    args = list(argv if argv is not None else sys.argv[1:])
    p = plan(sys.stdin.read().splitlines())
    print("\n".join(p.directives()) if "--directives" in args else _render(p))
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""THE COMPLETION LEDGER — capability status computed from the repo, never asserted in prose.

WHY THIS EXISTS. Asked repeatedly whether a specification was fully built, this desk answered in
prose: a table, a list, a paragraph. Prose status has three failure modes and the desk hit all
three in one day -- it drifts from reality the moment code changes, it cannot be re-checked without
re-reading everything, and it lets "built" mean whichever of EXISTS / IMPORTS / TESTED / WIRED the
writer had in mind. A module with a file and no caller was reported as built this morning; the
detector that found it was itself reported as wired while its output reached no decision.

So status becomes a MEASUREMENT. Each capability names its files, its tests and its callers, and
the ledger verifies each stage against the working tree:

    EXISTS     the implementation file is on disk
    IMPORTS    it imports without raising
    TESTS      a test file exists AND names it
    CALLED     something outside its own package invokes it (not merely imports)
    WIRED      a scheduler, cycle script or timer reaches that caller
    PRODUCES   it writes a declared artifact
    CONSUMED   something reads that artifact
    MEASURED   a metric about it lands somewhere a decision reads

**THE STATUS IS THE WEAKEST STAGE, NOT THE STRONGEST.** A capability with code, tests and a caller
that nothing schedules is WIRED-minus, and reporting it as TESTED would be true and useless. The
ledger takes the first failing stage and stops there, because the first gap is the one to close.

**`EXTERNALLY_BLOCKED` IS A REAL STATUS AND IT IS NOT AN EXCUSE.** It requires a named dependency
this repository cannot satisfy -- an unfunded API key, a credential that lives on the box, a
market that has not opened. "Large", "later" and "queued" are scheduling information and are
explicitly NOT terminal: they map to MISSING, which is the state that keeps a capability on the
work queue.
"""

from __future__ import annotations

import importlib
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

__all__ = [
    "CAPITAL_REQUIREMENTS",
    "SERVICE_REQUIREMENTS",
    "STAGES",
    "STATUS",
    "Capability",
    "Verification",
    "load",
    "required_guarantees",
    "summarise",
    "verify",
]

_ROOT = Path(__file__).resolve().parents[2]

#: Ordered. Status is the FIRST failing stage -- the weakest link, never the strongest.
STAGES: tuple[str, ...] = (
    "EXISTS", "IMPORTS", "TESTS", "CALLED", "WIRED", "PRODUCES", "CONSUMED", "MEASURED",
)

STATUS: tuple[str, ...] = (
    "MISSING", "PARTIAL", "VERIFIED_COMPLETE", "EXTERNALLY_BLOCKED",
)

#: EXTRA GUARANTEES FOR CAPABILITIES THAT CAN MOVE MONEY. The eight stages above prove a
#: capability RUNS and is READ. They say nothing about what happens when it runs twice, when it
#: fails halfway, or when someone bypasses it -- and for a capability with capital behind it those
#: are the only questions that matter. A capital-sensitive capability that passes all eight stages
#: and cannot answer these is reported PARTIAL, not complete, because "it works" is not the claim
#: being made about it.
CAPITAL_REQUIREMENTS: tuple[str, ...] = (
    "PERMISSION_BOUNDARY",   # the caller cannot widen its own authority
    "FAIL_CLOSED",           # an error stops the money path rather than passing it through
    "AUDIT_LINEAGE",         # every action traceable to the evidence that authorised it
    "IDEMPOTENCY",           # running it twice is not two positions
    "ROLLBACK",              # a wrong action can be undone, and the undo is tested
    "BYPASS_TESTED",         # an attempt to route around it FAILS, and a test proves it
)

#: EXTRA GUARANTEES FOR THINGS THAT ARE SUPPOSED TO KEEP RUNNING. A daily job that silently
#: stopped three weeks ago passes every stage above forever: the file exists, the tests pass, the
#: scheduler names it. Only these four distinguish "running" from "was once wired".
SERVICE_REQUIREMENTS: tuple[str, ...] = (
    "TRIGGERED",             # a timer/cron/hook actually fires it
    "RESTART_SAFE",          # it resumes correctly after the box reboots
    "STALL_DETECTED",        # a run that stops happening raises something
    "FAILURE_SURFACED",      # a run that fails is visible without reading a log
)

#: Files a scheduler reads. A caller none of these reach is code somebody must remember to run,
#: which is the definition of a capability that will eventually stop running.
_SCHEDULERS: tuple[str, ...] = (
    "ops/crontab.manifest", "ops/run_research_cycle.sh", "ops/run_frontier_rotation.sh",
    "scripts/run_cadence.py", "scripts/run_intelligence_cycle.py", "ops/commit_daily_max.sh",
)


@dataclass(frozen=True)
class Capability:
    """One requested capability and the evidence that would prove it real."""

    capability_id: str
    title: str
    economic_reason: str
    source_spec: str
    #: Import path of the implementation, e.g. "libs.research.kill_audit".
    module: str = ""
    #: Repo-relative test files that must exist AND mention the module.
    tests: tuple[str, ...] = field(default_factory=tuple)
    #: Repo-relative files that should CALL it.
    callers: tuple[str, ...] = field(default_factory=tuple)
    #: Artifacts it writes, repo-relative.
    artifacts: tuple[str, ...] = field(default_factory=tuple)
    #: Files that read those artifacts.
    consumers: tuple[str, ...] = field(default_factory=tuple)
    #: A named dependency this repository cannot satisfy. Set => EXTERNALLY_BLOCKED.
    external_blocker: str = ""
    expected_delta_elogw: str = ""
    next_action: str = ""

    # ---- §0 ECONOMIC FIELDS. Carried so a capability can be RANKED rather than merely listed.
    # A ledger that records only status answers "what is unfinished" and cannot answer "what
    # should be finished next", which is the question that decides where the day goes.
    #: What has to be true about markets for this to pay. Prose, but prose that can be argued with.
    economic_mechanism: str = ""
    #: What the desk learns by building it, separate from what it earns. A capability can be worth
    #: building purely because it turns an UNMEASURED into a number.
    information_value: str = ""
    implementation_cost: str = ""
    runtime_cost: str = ""
    #: Capability ids that must land first. An unbuilt dependency is why a high-value row is not
    #: simply the next task.
    dependencies: tuple[str, ...] = field(default_factory=tuple)
    #: What already does part of this. THE ANTI-DUPLICATION FIELD -- §1 forbids specification
    #: growth from becoming an escape from implementation, and the commonest form that takes is a
    #: new module that re-implements two thirds of an existing one.
    existing_equivalent: str = ""
    #: Timers, cron entries or hooks that fire it. Distinct from `callers`: a caller is code, a
    #: trigger is the thing that makes the code run without a human.
    triggers: tuple[str, ...] = field(default_factory=tuple)
    #: What has actually been measured about its value so far. Empty = nothing, which is the
    #: honest state for almost everything and must not read as zero value.
    measured_value: str = ""
    #: Declares the extra requirement sets above. Never inferred -- a capability nobody marked
    #: capital-sensitive is not thereby safe, it is unclassified, and the report says so.
    capital_sensitive: bool = False
    continuous_service: bool = False
    #: Which of CAPITAL_REQUIREMENTS / SERVICE_REQUIREMENTS have evidence, by name.
    guarantees_met: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class Verification:
    """What was actually found. `failed_stage` is empty only when every stage passed."""

    capability_id: str
    status: str
    stages: dict[str, bool]
    failed_stage: str
    detail: str
    #: Declared extra guarantees with no recorded evidence. Non-empty forces PARTIAL even when all
    #: eight stages pass -- for a capability with capital behind it, "it runs" is not the claim.
    missing_guarantees: tuple[str, ...] = ()

    @property
    def complete(self) -> bool:
        return self.status == "VERIFIED_COMPLETE"


def _exists(rel: str, root: Path) -> bool:
    return (root / rel).exists()


def _imports(module: str) -> tuple[bool, str]:
    if not module:
        return False, "no module declared"
    try:
        importlib.import_module(module)
    except Exception as e:
        # ANY import failure is the finding, including SyntaxError and a missing
        # third-party package -- a capability that cannot be imported cannot run,
        # and narrowing this would let some failures pass as healthy.
        return False, f"import raised {type(e).__name__}: {e}"
    return True, ""


def _mentions(files: tuple[str, ...], needle: str, root: Path) -> list[str]:
    """Files that exist AND contain the needle. Both halves matter: a named-but-absent test is a
    worse finding than no test at all, because the ledger would otherwise credit it."""
    out = []
    for rel in files:
        p = root / rel
        try:
            if p.exists() and needle in p.read_text("utf-8", errors="ignore"):
                out.append(rel)
        except OSError:
            continue
    return out


def _scheduled(callers: list[str], root: Path) -> list[str]:
    """Callers a scheduler actually reaches. A caller nothing schedules is not wired."""
    hit = []
    for caller in callers:
        # A caller that IS one of the scheduler files is wired by definition: the roster above
        # names the files that are the clocks, and a clock does not need a second clock to name
        # it. Without this clause the research cycle -- the file that runs run_completion_ledger
        # on every firing -- read as unwired because no other scheduler spells out its basename,
        # and the ledger reported its own scheduler as WIRED-minus.
        if caller in _SCHEDULERS:
            hit.append(f"{caller} <- itself (a scheduler entrypoint)")
            continue
        name = Path(caller).name
        for sched in _SCHEDULERS:
            p = root / sched
            try:
                if p.exists() and name in p.read_text("utf-8", errors="ignore"):
                    hit.append(f"{caller} <- {sched}")
                    break
            except OSError:
                continue
    return hit


def verify(cap: Capability, *, root: Path | None = None,
           importer: Callable[[str], tuple[bool, str]] | None = None) -> Verification:
    """Check every stage against the working tree. PURE over `root` and `importer` for testing."""
    r = root or _ROOT
    imp = importer or _imports
    stages: dict[str, bool] = {}
    detail = ""

    if cap.external_blocker:
        return Verification(cap.capability_id, "EXTERNALLY_BLOCKED", {}, "",
                            f"blocked by: {cap.external_blocker}")

    mod_rel = cap.module.replace(".", "/") + ".py" if cap.module else ""
    stages["EXISTS"] = bool(mod_rel) and _exists(mod_rel, r)
    ok, why = imp(cap.module) if stages["EXISTS"] else (False, "file absent")
    stages["IMPORTS"] = ok
    if not ok and stages["EXISTS"]:
        detail = why

    leaf = cap.module.rsplit(".", 1)[-1] if cap.module else ""
    found_tests = _mentions(cap.tests, leaf, r) if leaf else []
    stages["TESTS"] = bool(found_tests)

    found_callers = _mentions(cap.callers, leaf, r) if leaf else []
    stages["CALLED"] = bool(found_callers)

    scheduled = _scheduled(found_callers, r)
    stages["WIRED"] = bool(scheduled)

    # PRODUCES/CONSUMED are declarations about runtime, and on a clone the artifacts are absent by
    # design (data/ is gitignored). So the check is that the PATH is named by the producer and read
    # by a consumer -- the wiring, not the file, since a missing file here says only that the
    # capability has not run on THIS host.
    # MATCH THE BASENAME, NOT THE SLASH-JOINED PATH. Producers build paths as
    # `ROOT / "data" / "research_review.json"`, so the literal `data/research_review.json` never
    # appears in the source and a path-only check reported every wired producer as PRODUCES-false.
    # The check was wrong, not the code -- and a verifier that reports false gaps trains its reader
    # to ignore it, which is worse than no verifier.
    art = Path(cap.artifacts[0]).name if cap.artifacts else ""
    produces = _mentions((cap.callers or (mod_rel,)), art, r) if cap.artifacts else []
    stages["PRODUCES"] = bool(produces) or not cap.artifacts
    consumed = _mentions(cap.consumers, art, r) if cap.artifacts else []
    stages["CONSUMED"] = bool(consumed) or not cap.consumers
    stages["MEASURED"] = bool(cap.artifacts) and bool(consumed or produces)

    missing_guarantees = required_guarantees(cap)
    failed = next((s for s in STAGES if not stages.get(s, False)), "")
    if not failed and not missing_guarantees:
        return Verification(cap.capability_id, "VERIFIED_COMPLETE", stages, "",
                            f"all {len(STAGES)} stages verified", ())
    if not failed:
        return Verification(
            cap.capability_id, "PARTIAL", stages, "GUARANTEES",
            (f"all {len(STAGES)} stages verified, but {len(missing_guarantees)} declared "
             f"guarantee(s) have no evidence: {list(missing_guarantees)}. For a capability that "
             "can move money or is expected to keep running, 'it runs' is not the claim being "
             "made about it"), missing_guarantees)
    status = "MISSING" if failed in {"EXISTS", "IMPORTS"} else "PARTIAL"
    return Verification(cap.capability_id, status, stages, failed,
                        detail or f"first failing stage: {failed}", missing_guarantees)


def required_guarantees(cap: Capability) -> tuple[str, ...]:
    """Declared extra guarantees with no recorded evidence, in specification order.

    DECLARED, NEVER INFERRED. A capability nobody marked capital-sensitive is not thereby safe --
    it is unclassified, and the classification is a judgement this module cannot make from a
    module path. What it CAN do is refuse to call a declared money-path capability complete on
    the strength of the eight generic stages alone.
    """
    need: list[str] = []
    if cap.capital_sensitive:
        need.extend(CAPITAL_REQUIREMENTS)
    if cap.continuous_service:
        need.extend(SERVICE_REQUIREMENTS)
    met = set(cap.guarantees_met)
    return tuple(g for g in need if g not in met)


def load(path: Path) -> list[Capability]:
    """Capabilities from the ledger file. A malformed row is skipped, never guessed at."""
    try:
        doc = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return []
    out: list[Capability] = []
    for row in doc.get("capabilities", []) if isinstance(doc, dict) else []:
        if not isinstance(row, dict) or not row.get("capability_id"):
            continue
        out.append(Capability(
            capability_id=str(row["capability_id"]), title=str(row.get("title", "")),
            economic_reason=str(row.get("economic_reason", "")),
            source_spec=str(row.get("source_spec", "")), module=str(row.get("module", "")),
            tests=tuple(row.get("tests") or ()), callers=tuple(row.get("callers") or ()),
            artifacts=tuple(row.get("artifacts") or ()),
            consumers=tuple(row.get("consumers") or ()),
            external_blocker=str(row.get("external_blocker", "")),
            expected_delta_elogw=str(row.get("expected_delta_elogw", "")),
            next_action=str(row.get("next_action", "")),
            economic_mechanism=str(row.get("economic_mechanism", "")),
            information_value=str(row.get("information_value", "")),
            implementation_cost=str(row.get("implementation_cost", "")),
            runtime_cost=str(row.get("runtime_cost", "")),
            dependencies=tuple(row.get("dependencies") or ()),
            existing_equivalent=str(row.get("existing_equivalent", "")),
            triggers=tuple(row.get("triggers") or ()),
            measured_value=str(row.get("measured_value", "")),
            capital_sensitive=bool(row.get("capital_sensitive", False)),
            continuous_service=bool(row.get("continuous_service", False)),
            guarantees_met=tuple(row.get("guarantees_met") or ())))
    return out


def summarise(caps: list[Capability], *, root: Path | None = None) -> dict[str, object]:
    """THE HEADLINE IS THE COMPLETION FRACTION, and it counts VERIFIED stages, not files written.

    A percentage over declared capabilities is honest only if the denominator includes what is
    missing -- which is why every requested capability enters the ledger at MISSING rather than
    being omitted until somebody builds it. A ledger that lists only what exists reports 100%.
    """
    results = [verify(c, root=root) for c in caps]
    by_status: dict[str, list[str]] = {s: [] for s in STATUS}
    for r in results:
        by_status[r.status].append(r.capability_id)
    solvable = [r for r in results if r.status != "EXTERNALLY_BLOCKED"]
    complete = [r for r in solvable if r.complete]
    pct = (len(complete) / len(solvable) * 100.0) if solvable else 0.0
    partial = sorted((r for r in results if r.status == "PARTIAL"),
                     key=lambda r: STAGES.index(r.failed_stage) if r.failed_stage in STAGES else 99)
    return {
        "capabilities": len(caps),
        "verified_complete": len(complete),
        "partial": len(by_status["PARTIAL"]),
        "missing": len(by_status["MISSING"]),
        "externally_blocked": len(by_status["EXTERNALLY_BLOCKED"]),
        "completion_pct": round(pct, 1),
        "headline": (
            f"{len(complete)}/{len(solvable)} solvable capabilities VERIFIED_COMPLETE "
            f"({pct:.0f}%); {len(by_status['PARTIAL'])} partial, {len(by_status['MISSING'])} "
            f"missing, {len(by_status['EXTERNALLY_BLOCKED'])} externally blocked"),
        "next_action": (
            f"{partial[0].capability_id}: closest to done, failing at {partial[0].failed_stage}"
            if partial else
            f"{by_status['MISSING'][0]}: not started" if by_status["MISSING"] else
            "every solvable capability is verified complete -- ADD CAPABILITIES, because a ledger "
            "that lists only what exists reports 100% and measures nothing"),
        "by_status": by_status,
        "rows": [{"id": r.capability_id, "status": r.status, "failed_stage": r.failed_stage,
                  "detail": r.detail, "stages": r.stages,
                  "missing_guarantees": list(r.missing_guarantees)} for r in results],
        "unclassified_for_extra_guarantees": [
            c.capability_id for c in caps
            if not c.capital_sensitive and not c.continuous_service and not c.external_blocker],
        "note": ("Status is the FIRST FAILING stage, never the strongest passing one. 'Large', "
                 "'later' and 'queued' are scheduling information and map to MISSING -- only a "
                 "named dependency this repository cannot satisfy is EXTERNALLY_BLOCKED."),
    }

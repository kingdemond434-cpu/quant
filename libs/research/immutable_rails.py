"""THE EVOLVABLE / IMMUTABLE BOUNDARY (LAWS 5m), AS DATA THE MACHINE CAN BE FENCED BY.

    "The system may evolve its research machinery -- hypothesis generators, feature generators,
    agent prompts and programs, model architectures, experiment allocation, research code,
    representations, search algorithms, simulation populations, cross-breeding rules,
    data-acquisition priorities, curricula, ontologies, invented tools -- but NEVER its rails:
    point-in-time requirements, look-ahead and leakage checks, data provenance, effective-trial
    records, holdout boundaries, forward clocks, independent replication requirements,
    risk-limit authority, live-promotion rules, audit logs, legal/licensing gates. A
    self-improving system that could weaken its evaluator would improve its score by weakening
    the truth; the evaluator is immutable and separately authorised."      -- LAWS 5m

WHY A SECOND LIST BESIDE THE SEALED EVALUATOR, AND WHY IT IS NOT A SECOND SEAL. The evaluator
(`scripts/check_immutable_evaluator.py`) HASHES eighteen judge files into a signed manifest and
goes red when one drifts without a re-signing. That answers "did the judge change?". The boundary
the law draws is wider and asks a different question: "may THIS ORGAN change THIS PATH?" -- a
mutation proposal from `research_evolution` that reaches for the forward-clock ledger or the
registry's trial records is refused BEFORE it is applied, by name, whether or not a hash would
later have caught it. The sealed set is therefore INCLUDED here (loaded from the evaluator's own
tuple, never copied, so the two cannot disagree) and extended with the rails the evaluator does
not hash: state ledgers a checkout does not carry, symbol-scoped rails inside files that are
otherwise research code, and the legal gates.

WHAT A RAIL IS. A `Rail` names one repo-relative path (or a directory, or a glob) and optionally
the SYMBOLS inside it that are immutable. A rail with no symbols guards the whole file. A rail
with symbols guards those names and leaves the rest of the file evolvable -- `libs/moat/registry.py`
is research code the registry may grow, but `record_trial` and `verify_trial_chain` are the
effective-trial record and may not be touched by anything that evolves. A change set that names
the file and NO symbols is read as touching every symbol in it: a whole-file rewrite cannot
launder a rail edit by declining to say which names it moved.

PURE. Nothing here reads the trading box's state or writes anything; the fence
(`scripts/check_immutable_rails.py`) and the evolution organ call `check_change_set` and act on
the verdict. UNCLASSIFIED is a real answer: a path in neither set is reported as such and is NOT
refused -- the law enumerates what is immutable, and a fence that refused everything unlisted
would refuse the next organ anyone builds.
"""
from __future__ import annotations

import fnmatch
import importlib.util
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
EVALUATOR_SCRIPT = ROOT / "scripts" / "check_immutable_evaluator.py"

#: The category the evaluator's own signed tuple lands in when it is merged into the rails.
SEALED_CATEGORY = "sealed_evaluator"

IMMUTABLE_STATUS = "IMMUTABLE"
EVOLVABLE_STATUS = "EVOLVABLE"
UNCLASSIFIED_STATUS = "UNCLASSIFIED"


@dataclass(frozen=True)
class Rail:
    """One immutable path. `symbols` empty guards the whole file; `state` marks a box-written
    ledger or artifact that a clean checkout legitimately does not carry."""

    category: str
    path: str
    symbols: tuple[str, ...] = ()
    why: str = ""
    state: bool = False

    def matches(self, rel: str) -> bool:
        rel = norm(rel)
        p = self.path
        if p.endswith("/"):
            return rel.startswith(p)
        if any(ch in p for ch in "*?["):
            return fnmatch.fnmatchcase(rel, p)
        return rel == p

    def as_dict(self) -> dict[str, Any]:
        return {"category": self.category, "path": self.path, "symbols": list(self.symbols),
                "why": self.why, "state": self.state}


def norm(rel: str | Path) -> str:
    """Repo-relative, forward slashes, no leading './' -- the one spelling every comparison uses."""
    s = str(rel).replace("\\", "/")
    root = str(ROOT).replace("\\", "/").rstrip("/") + "/"
    if s.startswith(root):
        s = s[len(root):]
    while s.startswith("./"):
        s = s[2:]
    return s.strip("/") + ("/" if str(rel).endswith(("/", "\\")) else "")


# ------------------------------------------------------------------------------ the evolvable set
#: Category -> the organs and libraries the research system MAY rewrite, by path. These are the
#: law's fourteen classes, each anchored to the files that implement it in this tree.
EVOLVABLE: dict[str, tuple[str, ...]] = {
    "hypothesis_generators": (
        "desks/mt5/research/alpha_evolution.py", "desks/mt5/research/discovery_compiler.py",
        "desks/mt5/research/trajectory_evolution.py", "desks/mt5/research/joint_evolution.py",
        "desks/mt5/research/alpha_lineage_search.py", "desks/mt5/research/alpha_recombination.py",
        "desks/mt5/research/graveyard_resurrection.py", "desks/mt5/research/program_alpha_lane.py",
        "desks/mt5/research/descendants.py", "desks/mt5/research/proposer_common.py",
        "desks/mt5/research/breadth_sweep.py", "desks/mt5/research/qd_frontier.py"),
    "feature_generators": (
        "desks/mt5/research/representation_forge.py", "libs/data/feature_store.py",
        "libs/data/feature_lifecycle.py"),
    "agent_prompts_programs": (
        "desks/mt5/research/deepening_worker.py", "desks/mt5/research/understanding_seat.py",
        "libs/research/agents.py"),
    "model_architectures": (
        "desks/mt5/research/world_model.py", "desks/mt5/research/factor_model_coevolution.py"),
    "experiment_allocation": (
        "desks/mt5/research/meta_controller.py", "desks/mt5/research/research_roi.py",
        "desks/mt5/research/research_departments.py", "desks/mt5/research/miner_specialisation.py",
        "desks/mt5/research/compute_economics.py", "libs/research/bandit.py"),
    "research_code": (
        "desks/mt5/research/research_evolution.py",
        "desks/mt5/research/missed_trade_archaeologist.py"),
    "representations": (
        "libs/research/program_ir.py", "libs/research/alpha_grammar.py",
        "libs/research/alpha_genome.py"),
    "search_algorithms": (
        "libs/research/mcts.py", "desks/mt5/research/research_tree.py"),
    "simulation_populations": (
        "desks/mt5/research/adversary_evolution.py",),
    "cross_breeding_rules": (
        "libs/research/coevolution.py",),
    "data_acquisition_priorities": (
        "libs/research/forests.py", "desks/mt5/research/deep_forest_miner.py",
        "desks/mt5/data/deep_forest_sources.json"),
    "curricula": (
        "desks/mt5/research/coverage_tensor.py", "desks/mt5/research/residual_hunt.py",
        "desks/mt5/research/research_gap_map.py", "desks/mt5/research/unseen_frontier.py"),
    "ontologies": (
        "desks/mt5/research/axis_registry.py", "desks/mt5/research/axis_proposer.py"),
    "invented_tools": (
        "libs/research/external_federation.py",),
}


# ------------------------------------------------------------------------------ the immutable set
#: The eleven rail classes of LAWS 5m, each anchored to paths -- plus the evaluator's sealed set,
#: merged at read time by `immutable_rails()`.
DECLARED_RAILS: tuple[Rail, ...] = (
    # point-in-time requirements
    Rail("point_in_time_requirements", "libs/data/pit.py",
         why="the point-in-time contract every series is admitted under"),
    Rail("point_in_time_requirements", "libs/data/pit_certificate.py",
         why="what a PIT certificate asserts"),
    Rail("point_in_time_requirements", "libs/data/pit_stamp.py",
         why="how an observation is stamped with when it became knowable"),
    Rail("point_in_time_requirements", "desks/mt5/research/pit_audit.py",
         why="the audit that says which money-path data is PIT-certified"),
    # look-ahead and leakage checks
    Rail("lookahead_leakage_checks", "libs/validation/lookahead.py",
         why="the look-ahead test a cell must pass"),
    Rail("lookahead_leakage_checks", "libs/validation/lookahead_audit.py",
         why="the audit of look-ahead across a campaign"),
    Rail("lookahead_leakage_checks", "libs/validation/shift_leak.py",
         why="the timestamp-shift leak detector"),
    # data provenance
    Rail("data_provenance", "libs/data/input_identity.py",
         why="the bars every verdict was measured on, pinned"),
    Rail("data_provenance", "libs/research/clock_provenance.py",
         why="which clock produced which observation"),
    Rail("data_provenance", "libs/research/citation_integrity.py",
         why="a claim's citation must resolve"),
    Rail("data_provenance", "libs/research/artifact_chain.py",
         why="the artifact chain from input to verdict"),
    Rail("data_provenance", "libs/ops/compute_ledger.py",
         symbols=("close_run", "_append", "commit_sha", "_sha256_files", "_config_hash"),
         why="the provenance envelope every run publishes"),
    # effective-trial records
    Rail("effective_trial_records", "libs/moat/registry.py",
         symbols=("record_trial", "verify_trial_chain", "trials_ledger", "content_hash",
                  "record_run"),
         why="the effective-trial record and its hash chain; the rest of the registry is "
             "research code and may grow"),
    Rail("effective_trial_records", "libs/validation/dsr.py",
         why="the deflated-Sharpe charge for the trials actually run"),
    Rail("effective_trial_records", "libs/validation/family_multiplicity.py",
         why="the family-wise error budget"),
    Rail("effective_trial_records", "libs/validation/fdr.py",
         why="the false-discovery control over the trial stream"),
    Rail("effective_trial_records", "desks/mt5/data/hypotheses/gate_verdict_ledger.jsonl",
         state=True, why="every verdict ever handed down"),
    Rail("effective_trial_records", "desks/mt5/data/hypothesis_graph.jsonl", state=True,
         why="every hypothesis ever born and its fate"),
    # holdout boundaries
    Rail("holdout_boundaries", "libs/validation/lockbox.py",
         why="the sealed windows no generator may read"),
    Rail("holdout_boundaries", "libs/validation/cpcv.py",
         why="the purged, embargoed cross-validation boundary"),
    Rail("holdout_boundaries", "libs/validation/campaign_window.py",
         why="where a campaign's in-sample ends"),
    # forward clocks
    Rail("forward_clocks", "desks/mt5/research/shadow_forward.py",
         why="the forward clock that accrues the only evidence promotion reads"),
    Rail("forward_clocks", "desks/mt5/research/forward_reconcile.py",
         why="which clocks may accrue evidence"),
    Rail("forward_clocks", "libs/research/clock_registry.py", why="the roster of clocks"),
    Rail("forward_clocks", "libs/research/clock_retirement.py",
         why="how a clock leaves the roster"),
    Rail("forward_clocks", "desks/mt5/reports/shadow/", state=True,
         why="the forward ledgers themselves"),
    Rail("forward_clocks", "desks/mt5/data/forward_reconcile.json", state=True,
         why="the reconciled forward roster"),
    # independent replication requirements
    Rail("independent_replication", "desks/mt5/research/lead_replication.py",
         why="a lead is reproduced by a second implementation before it is believed"),
    Rail("independent_replication", "desks/mt5/research/blind_reviewer.py",
         why="the blind review of a candidate"),
    Rail("independent_replication", "libs/research/cohort_independence.py",
         why="what counts as an independent cohort"),
    # risk-limit authority
    Rail("risk_limit_authority", "desks/mt5/research/pf_allocator.py",
         why="the one authority that sizes"),
    # live-promotion rules
    Rail("live_promotion_rules", "libs/validation/gauntlet.py",
         why="the ten gates a certificate is made of"),
    Rail("live_promotion_rules", "desks/mt5/data/sleeves.json", state=True,
         why="the LIVE roster the gateway trades"),
    # audit logs
    Rail("audit_logs", "desks/mt5/data/decision_ledger.jsonl", state=True,
         why="every decision the desk made, taken or not"),
    Rail("audit_logs", "desks/mt5/data/live_ledger.jsonl", state=True,
         why="every live fill"),
    Rail("audit_logs", "desks/mt5/data/compute_ledger.jsonl", state=True,
         why="what every run cost"),
    Rail("audit_logs", "desks/mt5/data/blind_review_ledger.jsonl", state=True,
         why="every blind review"),
    Rail("audit_logs", "desks/mt5/data/IMMUTABLE_MANIFEST.json", state=True,
         why="the evaluator's signed manifest"),
    Rail("audit_logs", "ops/principal_doctrine.txt", why="the sealed doctrine"),
    Rail("audit_logs", "docs/LAWS.md", why="the law compendium"),
    # legal / licensing gates
    Rail("legal_licensing_gates", "libs/research/access_classifier.py",
         why="which sources the desk may lawfully read"),
    Rail("legal_licensing_gates", "desks/mt5/research/evidence_router.py",
         why="the provenance states and the BLOCKED list"),
    Rail("legal_licensing_gates", "libs/data/paywall.py",
         why="what sits behind a licence"),
    Rail("legal_licensing_gates", "scripts/check_external_federation.py",
         why="the federation's sandbox and admission policy"),
)

IMMUTABLE_CATEGORIES: tuple[str, ...] = (
    "point_in_time_requirements", "lookahead_leakage_checks", "data_provenance",
    "effective_trial_records", "holdout_boundaries", "forward_clocks",
    "independent_replication", "risk_limit_authority", "live_promotion_rules", "audit_logs",
    "legal_licensing_gates", SEALED_CATEGORY)


def evaluator_immutable(script: Path | None = None) -> tuple[str, ...]:
    """`check_immutable_evaluator.IMMUTABLE`, loaded by file path -- `scripts/` is not a package.
    An empty tuple means the evaluator could not be read, and the fence reports that as a breach
    rather than as a clean wall."""
    path = script or EVALUATOR_SCRIPT
    try:
        spec = importlib.util.spec_from_file_location("_rails_evaluator", path)
        if spec is None or spec.loader is None:
            return ()
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return tuple(str(x) for x in getattr(mod, "IMMUTABLE", ()))
    except Exception:
        return ()


def immutable_rails(*, include_sealed: bool = True,
                    script: Path | None = None) -> tuple[Rail, ...]:
    """Every rail: the declared eleven classes plus the evaluator's sealed tuple, deduplicated on
    path (a sealed path that is also declared keeps the declared, narrower, category)."""
    seen = {norm(r.path) for r in DECLARED_RAILS}
    out = list(DECLARED_RAILS)
    if include_sealed:
        for rel in evaluator_immutable(script):
            if norm(rel) not in seen:
                out.append(Rail(SEALED_CATEGORY, norm(rel),
                                why="hashed into IMMUTABLE_MANIFEST.json by the evaluator"))
                seen.add(norm(rel))
    return tuple(out)


def evolvable_paths() -> tuple[str, ...]:
    return tuple(sorted({norm(p) for ps in EVOLVABLE.values() for p in ps}))


def evolvable_category(rel: str) -> str | None:
    rel = norm(rel)
    for cat, paths in EVOLVABLE.items():
        if rel in {norm(p) for p in paths}:
            return cat
    return None


# ------------------------------------------------------------------------------ classification
@dataclass(frozen=True)
class Classification:
    path: str
    status: str
    category: str | None
    rails: tuple[Rail, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {"path": self.path, "status": self.status, "category": self.category,
                "rails": [r.as_dict() for r in self.rails]}


def rails_for(rel: str, rails: Iterable[Rail] | None = None) -> tuple[Rail, ...]:
    src = tuple(rails) if rails is not None else immutable_rails()
    return tuple(r for r in src if r.matches(rel))


def classify(rel: str, rails: Iterable[Rail] | None = None) -> Classification:
    """IMMUTABLE when any rail guards the path (whole or by symbol); EVOLVABLE when the law lists
    it; UNCLASSIFIED otherwise -- three answers, none of them a default."""
    rel = norm(rel)
    hits = rails_for(rel, rails)
    whole = tuple(r for r in hits if not r.symbols)
    if whole:
        return Classification(rel, IMMUTABLE_STATUS, whole[0].category, hits)
    cat = evolvable_category(rel)
    if hits and cat is None:
        # symbol-scoped rails only, on a file the law does not list as evolvable: the file is
        # immutable in those names and otherwise research code by the registry's own reading
        return Classification(rel, IMMUTABLE_STATUS, hits[0].category, hits)
    if cat is not None:
        return Classification(rel, EVOLVABLE_STATUS, cat, hits)
    return Classification(rel, UNCLASSIFIED_STATUS, None, ())


# ------------------------------------------------------------------------------ change sets
@dataclass(frozen=True)
class Touch:
    """One path a mutation proposal changes, and which names inside it. No symbols = the
    whole file."""

    path: str
    symbols: tuple[str, ...] = ()


@dataclass(frozen=True)
class Refusal:
    path: str
    category: str
    symbol: str | None
    why: str

    def as_dict(self) -> dict[str, Any]:
        return {"path": self.path, "category": self.category, "symbol": self.symbol,
                "why": self.why}


@dataclass(frozen=True)
class Verdict:
    ok: bool
    refused: tuple[Refusal, ...] = ()
    allowed: tuple[str, ...] = ()
    unclassified: tuple[str, ...] = ()
    touches: tuple[Touch, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, Any]:
        return {"ok": self.ok, "refused": [r.as_dict() for r in self.refused],
                "allowed": list(self.allowed), "unclassified": list(self.unclassified),
                "touches": [{"path": t.path, "symbols": list(t.symbols)} for t in self.touches]}


def as_touch(x: Touch | str | Mapping[str, Any]) -> Touch:
    if isinstance(x, Touch):
        return Touch(norm(x.path), tuple(str(s) for s in x.symbols))
    if isinstance(x, str):
        return Touch(norm(x))
    path = str(x.get("path") or x.get("file") or "")
    syms = x.get("symbols") or x.get("names") or ()
    if isinstance(syms, str):
        syms = (syms,)
    return Touch(norm(path), tuple(str(s) for s in syms))


def check_change_set(touches: Iterable[Touch | str | Mapping[str, Any]],
                     rails: Iterable[Rail] | None = None) -> Verdict:
    """The verdict on a change set: every touch of a whole-file rail is refused; a touch of a
    symbol-scoped rail is refused when it names a guarded symbol OR names none (a whole-file
    change touches every symbol); everything else is allowed, with the unclassified named."""
    src = tuple(rails) if rails is not None else immutable_rails()
    refused: list[Refusal] = []
    allowed: list[str] = []
    unclassified: list[str] = []
    seen_touches: list[Touch] = []
    for raw in touches:
        t = as_touch(raw)
        seen_touches.append(t)
        if not t.path:
            continue
        hits = rails_for(t.path, src)
        if not hits:
            allowed.append(t.path)
            if evolvable_category(t.path) is None:
                unclassified.append(t.path)
            continue
        refused_here = False
        for r in hits:
            if not r.symbols:
                refused.append(Refusal(t.path, r.category, None,
                                       f"{t.path} is an immutable rail ({r.category}): {r.why}"))
                refused_here = True
                continue
            if not t.symbols:
                refused.append(Refusal(
                    t.path, r.category, None,
                    f"{t.path} holds the guarded names {', '.join(r.symbols)} ({r.category}) and "
                    f"the change set names no symbol, so it is read as touching all of them"))
                refused_here = True
                continue
            for s in t.symbols:
                if s in r.symbols:
                    refused.append(Refusal(
                        t.path, r.category, s,
                        f"{t.path}::{s} is an immutable rail ({r.category}): {r.why}"))
                    refused_here = True
        if not refused_here:
            allowed.append(t.path)
    return Verdict(ok=not refused, refused=tuple(refused), allowed=tuple(allowed),
                   unclassified=tuple(unclassified), touches=tuple(seen_touches))


def refuse_proposal(proposal: Mapping[str, Any],
                    rails: Iterable[Rail] | None = None) -> Verdict:
    """A mutation proposal is `{"touches": [{"path", "symbols"} | str, ...], ...}`; a proposal
    with no `touches` at all is refused, because a change that says it touches nothing cannot be
    checked and an uncheckable change is not applied."""
    raw = proposal.get("touches")
    if not isinstance(raw, (list, tuple)) or not raw:
        return Verdict(ok=False, refused=(Refusal(
            "", "undeclared_change_set", None,
            "the proposal declares no `touches`; an uncheckable change set is refused"),))
    return check_change_set(raw, rails)


def rails_report(rails: Iterable[Rail] | None = None) -> dict[str, Any]:
    """The boundary as one document: counts per class, the paths, and the evolvable set."""
    src = tuple(rails) if rails is not None else immutable_rails()
    by_cat: dict[str, list[dict[str, Any]]] = {c: [] for c in IMMUTABLE_CATEGORIES}
    for r in src:
        by_cat.setdefault(r.category, []).append(r.as_dict())
    return {
        "law": "LAWS 5m -- THE EVOLVABLE / IMMUTABLE BOUNDARY",
        "immutable": by_cat,
        "n_immutable": len(src),
        "evolvable": {k: list(v) for k, v in EVOLVABLE.items()},
        "n_evolvable": len(evolvable_paths()),
        "rule": ("an evolvable organ may rewrite any evolvable path; a change set that touches an "
                 "immutable path or a guarded symbol is refused by name before it is applied; "
                 "a path in neither set is UNCLASSIFIED, reported, and not refused"),
    }

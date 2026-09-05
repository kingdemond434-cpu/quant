"""THE REJECTED-TRADE LEDGER — the desk's decisions are currently only legible where they said yes.

WHAT IS MISSING WITHOUT THIS. Every artifact on this desk records what was DONE: fills, positions,
P&L, survivors. Nothing records what was declined. That asymmetry has three consequences and all
three cost money.

    1. THE REJECTION POPULATION IS THE LARGEST DATASET THE DESK GENERATES AND IT IS DISCARDED.
       750 of 762 cells died at one gate in the last sweep. The 12 that lived have a report; the
       750 left no per-decision record at all, so "is that gate correct" was unanswerable until
       kill_audit forced the cells to be retained. The same hole exists one layer down, at every
       signal that fired and was not traded.

    2. A SYSTEMATIC REJECTION REASON IS INVISIBLE UNTIL IT IS CATASTROPHIC. If the cost model is
       15% too pessimistic, the desk does not observe a bias -- it observes fewer trades, which
       looks like a quiet market. The counterfactual outcomes attached here are what turn that
       into a measurement.

    3. THE FIRST QUESTION AFTER A BAD DAY IS ALWAYS "WHAT DID WE NOT DO", and the honest answer
       has always been that nobody knows.

**COUNTERFACTUALS ARE ATTACHED, NOT PROMOTED, AND THE DISTINCTION IS THE WHOLE SAFETY ARGUMENT.**
Knowing that a rejected signal would have made 40bp is information about the REJECTOR. It is not
evidence about the signal, because the signal was selected for the counterfactual by having been
rejected -- the population is conditioned on the very thing being tested. `promotion_is_forbidden`
exists as a named function so that any future caller reaching for "but it would have worked" hits
a wall with the reason written on it. The legitimate use is `systematic_bias`, which asks whether
a rejection REASON is wrong across its whole population, and the new-hypothesis path, which sends
the finding back through preregistration on untouched data.

Records and measures. Trades nothing, promotes nothing, and cannot.

THE FULL DECISION RECORD (2026-09-05, the principal's counterfactual-world order). The gateway's
`_record_decision` writes a hand-rolled dict -- sleeve, side, price, stop, target, taken, reason
-- and nothing on the desk could price "what if 0.5x / limit / trail / partial" from it, because
the size chosen, the execution chosen, the exit rule and the portfolio context at the moment
were never on the row. `Decision` now carries every one of those as a field with a default, so
a row written today is a superset of a row written last month and `read()` accepts both.
`write_decision` is the one writer: the gateway's replacement for its own dict is one call that
never raises, because a ledger fault must cost a row and never an order.
"""

from __future__ import annotations

import json
import math
from collections.abc import Callable, Iterable, Mapping
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

__all__ = [
    "DEFAULT_REJECTION",
    "MIN_POPULATION_FOR_BIAS",
    "OUTCOMES",
    "REASON_TO_OUTCOME",
    "REJECTION_CLASSES",
    "SCHEMA_VERSION",
    "Decision",
    "counterfactual_summary",
    "decision_from_row",
    "outcome_for",
    "promotion_is_forbidden",
    "read",
    "summarise",
    "systematic_bias",
    "write_decision",
]

#: The row schema the desk's decision dataset keys on. Bumped only when a field changes meaning;
#: adding a defaulted field is not a bump, because every old row still reads under it.
SCHEMA_VERSION: int = 1

#: Every terminal state a candidate opportunity can reach. EXECUTED is one of ten, which is roughly
#: the share of the decision surface it actually occupies -- nine ways to decline, one to act.
OUTCOMES: tuple[str, ...] = (
    "EXECUTED",
    "SIGNAL_REJECTED",
    "VALIDATION_REJECTED",
    "PORTFOLIO_REJECTED",
    "RISK_REJECTED",
    "COST_REJECTED",
    "CAPACITY_REJECTED",
    "EXECUTION_REJECTED",
    "VENUE_UNAVAILABLE",
    "MISSED_LATENCY",
)

REJECTION_CLASSES: frozenset[str] = frozenset(o for o in OUTCOMES if o != "EXECUTED")

#: Below this many decisions sharing a rejection reason, a bias estimate is noise. The whole point
#: of this ledger is to stop small samples being read as findings, and it would be absurd for the
#: ledger itself to produce one.
MIN_POPULATION_FOR_BIAS: int = 50

#: THE GATEWAY'S REASON STRINGS, EACH IN ITS CLASS. The gateway names the gate that said no in
#: its own vocabulary (`reason=` on `_record_decision`); the ledger counts by class. The map is
#: written down so the two vocabularies cannot drift apart silently, and so a reader of the
#: dataset can see that "shadow_not_armed" was a venue the process could not reach, not a
#: signal the desk disliked. A reason not listed here lands in DEFAULT_REJECTION with its text
#: intact -- the class is a coarse count, the reason is the fact.
REASON_TO_OUTCOME: Mapping[str, str] = {
    "placed": "EXECUTED",
    # a rejection returned by the venue, after the desk wanted the trade
    "broker_rejected": "EXECUTION_REJECTED",
    # the bracket level sat inside the broker's freeze band: the market did not offer it
    "entry_inside_freeze_band": "VENUE_UNAVAILABLE",
    # the regime monitor silenced the sleeve for the day
    "regime_hibernate": "SIGNAL_REJECTED",
    # a conditioned sleeve could not confirm its state
    "state_gate": "VALIDATION_REJECTED",
    "margin_guard": "RISK_REJECTED",
    # the process could not send: shadow mode, or the release identity refused new risk
    "shadow_not_armed": "VENUE_UNAVAILABLE",
    "release_identity_refused": "VENUE_UNAVAILABLE",
}
DEFAULT_REJECTION: str = "VALIDATION_REJECTED"


def outcome_for(reason: str, taken: bool) -> str:
    """The ledger class of a gateway reason. Taken is EXECUTED whatever the reason says."""
    if taken:
        return "EXECUTED"
    out = REASON_TO_OUTCOME.get(str(reason or ""), DEFAULT_REJECTION)
    return out if out != "EXECUTED" else DEFAULT_REJECTION


@dataclass(frozen=True)
class Decision:
    """One evaluated opportunity, executed or not, with the exact reason and the state it saw.

    Every field after `intended_notional` was added for the counterfactual world and defaults,
    so a row written before it existed still constructs. They are what `counterfactual_world`
    needs to price the road not taken: the size the desk chose (`size_mult`, against the
    allocator's 1.0x), how it chose to execute, which exit rule governed, the veto that fired,
    the portfolio the decision was made inside, and where in which ledger the row came from.
    """

    decision_id: str
    strategy_id: str
    symbol: str
    #: ISO timestamp of the DECISION, not of the record being written.
    decided_at: str
    outcome: str
    #: The specific reason string, e.g. "spread 14bp > modelled edge 9bp". Free text on purpose:
    #: the class is for counting, the reason is for reading.
    reason: str = ""
    #: Feature values the decision saw. Kept so a bias can be conditioned on state.
    features: dict[str, float] = field(default_factory=dict)
    regime: str = ""
    #: Signal strength in bps, as estimated at decision time.
    signal_bps: float = 0.0
    #: Modelled all-in cost in bps at decision time.
    modelled_cost_bps: float = 0.0
    #: Realised forward return of the instrument over the intended horizon, in bps, filled in
    #: LATER. None = not yet resolved, which is the honest state for a recent decision.
    counterfactual_bps: float | None = None
    #: Size that would have been taken, for weighting the counterfactual.
    intended_notional: float = 0.0
    # ------------------------------------------------------------------ the full record
    #: The sleeve that produced the signal (the gateway's `sleeve`); `strategy_id` stays the
    #: family-level identity for the bias test.
    sleeve: str = ""
    #: "buy" | "sell" | "buy_stop" | "sell_stop" | "" (a refusal recorded before a side existed).
    side: str = ""
    #: The bracket the desk would have placed (or placed): level, stop, target, lot.
    price: float | None = None
    sl: float | None = None
    tp: float | None = None
    lot: float | None = None
    #: The id of the state vector current at the decision -- the WorldState join key.
    world_state_id: str = ""
    release_id: str = ""
    #: Every action the desk could have taken here, as the dataset's CandidateActions.
    candidate_actions: list[dict[str, Any]] = field(default_factory=list)
    #: The one it took: {"kind": "enter"|"skip", ...}. Empty means "derive from taken/reason".
    chosen_action: dict[str, Any] = field(default_factory=dict)
    #: The size multiplier the desk applied against the allocator's normal size (the capital
    #: modifier's category: 0.5x REDUCE, 1.5x BOOST ...). 1.0 is "as the allocator said".
    size_mult: float = 1.0
    #: How the order was (or would have been) sent: market | pending_stop | limit | delayed.
    execution: str = ""
    #: The exit rule that governed the position: fixed_tp (the bracket) | trail | hold | partial.
    exit_rule: str = ""
    #: The gate that refused, when one did; empty on an executed decision.
    veto_reason: str = ""
    #: The book the decision was made inside: allocator heat, the sleeve's fraction, the
    #: sleeve's position before this decision, the capital-modifier category.
    portfolio_context: dict[str, Any] = field(default_factory=dict)
    #: Where the record came from: ledger name -> physical line offsets (append-only ledgers, so
    #: an offset is a stable address).
    provenance: dict[str, Any] = field(default_factory=dict)
    ticket: int | None = None
    retcode: int | None = None
    schema_version: int = SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.outcome not in OUTCOMES:
            raise ValueError(f"outcome must be one of {OUTCOMES}, got {self.outcome!r}")

    @property
    def rejected(self) -> bool:
        return self.outcome in REJECTION_CLASSES

    @property
    def resolved(self) -> bool:
        return self.counterfactual_bps is not None

    @property
    def taken(self) -> bool:
        return self.outcome == "EXECUTED"

    def to_row(self) -> dict[str, Any]:
        """The JSON line. Every field, in declaration order, so a row reads like the class."""
        return asdict(self)


def decision_from_row(row: Mapping[str, Any]) -> Decision:
    """A `Decision` from a ledger line -- this module's own, or the gateway's hand-rolled one.

    The gateway's legacy row has no `outcome`: it has `taken` and `reason`, and the class is
    derived through `outcome_for`. Its `time` is the decision time. Its `sleeve` stands in for
    `strategy_id` because the family identity was never on the row; a reader that needs the
    family derives it from the sleeve name, as the desk's other engines do.
    """
    r = dict(row)
    taken = bool(r.get("taken", r.get("outcome") == "EXECUTED"))
    reason = str(r.get("reason") or "")
    outcome = str(r.get("outcome") or outcome_for(reason, taken))
    sleeve = str(r.get("sleeve") or r.get("strategy_id") or "")
    decided_at = str(r.get("decided_at") or r.get("time") or "")
    side = str(r.get("side") or "")
    decision_id = str(r.get("decision_id") or f"{sleeve}|{side}|{decided_at}")

    def _f(key: str) -> float | None:
        v = r.get(key)
        if v is None or isinstance(v, bool):
            return None
        try:
            x = float(v)
        except (TypeError, ValueError):
            return None
        return x if math.isfinite(x) else None

    def _i(key: str) -> int | None:
        v = r.get(key)
        if v is None or isinstance(v, bool):
            return None
        try:
            return int(v)
        except (TypeError, ValueError):
            return None

    veto = str(r.get("veto_reason") or ("" if taken else reason))
    # 0.0 is a real multiplier (STRONG_VETO), so absence is tested, never falsiness.
    size_mult = _f("size_mult")
    return Decision(
        decision_id=decision_id, strategy_id=str(r.get("strategy_id") or sleeve),
        symbol=str(r.get("symbol") or ""), decided_at=decided_at, outcome=outcome,
        reason=reason, features=dict(r.get("features") or {}), regime=str(r.get("regime") or ""),
        signal_bps=float(r.get("signal_bps") or 0.0),
        modelled_cost_bps=float(r.get("modelled_cost_bps") or 0.0),
        counterfactual_bps=_f("counterfactual_bps"),
        intended_notional=float(r.get("intended_notional") or 0.0),
        sleeve=sleeve, side=side, price=_f("price"), sl=_f("sl"), tp=_f("tp"), lot=_f("lot"),
        world_state_id=str(r.get("world_state_id") or r.get("state_vector_id") or ""),
        release_id=str(r.get("release_id") or ""),
        candidate_actions=list(r.get("candidate_actions") or []),
        chosen_action=dict(r.get("chosen_action") or {}),
        size_mult=size_mult if size_mult is not None else 1.0,
        execution=str(r.get("execution") or ""), exit_rule=str(r.get("exit_rule") or ""),
        veto_reason=veto, portfolio_context=dict(r.get("portfolio_context") or {}),
        provenance=dict(r.get("provenance") or {}), ticket=_i("ticket"), retcode=_i("retcode"),
        schema_version=int(r.get("schema_version") or SCHEMA_VERSION))


def write_decision(path: Path | str, decision: Decision | Mapping[str, Any], *,
                   log: Callable[[str], None] | None = None) -> bool:
    """Append one decision as one JSON line. NEVER raises: on the money path a ledger fault
    costs a row, and a row is cheaper than an order. Returns whether the line was written.

    Accepts a `Decision` or the gateway's keyword dict (`sleeve=, side=, taken=, reason=...`),
    which is normalised through `decision_from_row` so the file holds one schema whichever
    caller wrote the line. Legacy keys (`state_vector_id`, `time`) are kept on the line beside
    their canonical names so `counterfactual_markout`'s join, keyed on them, keeps working.
    """
    try:
        d = decision if isinstance(decision, Decision) else decision_from_row(decision)
        row = d.to_row()
        # the two names the existing engines join on, kept verbatim
        row["time"] = d.decided_at
        row["state_vector_id"] = d.world_state_id
        row["taken"] = d.taken
        if not isinstance(decision, Decision):
            for k in ("detail",):
                if k in decision:
                    row[k] = decision[k]
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, default=str) + "\n")
        return True
    except Exception as exc:  # telemetry must not break the money path
        if log is not None:
            log(f"decision record failed (non-fatal): {type(exc).__name__}: {exc}")
        return False


def read(path: Path | str) -> list[Decision]:
    """Every readable decision in a ledger file, legacy rows included; a torn line is skipped."""
    out: list[Decision] = []
    try:
        lines: Iterable[str] = Path(path).read_text("utf-8").splitlines()
    except OSError:
        return out
    for ln in lines:
        ln = ln.strip()
        if not ln:
            continue
        try:
            r = json.loads(ln)
        except ValueError:
            continue
        if not isinstance(r, dict):
            continue
        try:
            out.append(decision_from_row(r))
        except ValueError:
            continue
    return out


def promotion_is_forbidden(d: Decision) -> str:
    """The reason a good counterfactual can never promote its own decision. Called for the message.

    Present as a function rather than a comment so that it appears in the report next to every
    attractive number, and so that a future caller looking for a promotion path finds this instead
    of writing one.
    """
    return (
        f"{d.decision_id} was REJECTED and its counterfactual is therefore conditioned on the "
        "rejection. The population of 'rejected things that would have worked' is selected by the "
        "outcome being tested, so its mean is biased upward by construction and no significance "
        "computed on it is valid. This number may be used to test whether the REASON "
        f"({d.outcome}) is systematically wrong across its whole population, and to seed a NEW "
        "preregistered hypothesis on untouched data. It may never reinstate this decision.")


def counterfactual_summary(decisions: list[Decision]) -> dict[str, dict[str, float | int | bool]]:
    """Resolved counterfactuals by rejection class. Descriptive; every number carries the caveat."""
    by_class: dict[str, list[float]] = {}
    for d in decisions:
        if d.rejected and d.resolved:
            by_class.setdefault(d.outcome, []).append(float(d.counterfactual_bps or 0.0))
    out: dict[str, dict[str, float | int | bool]] = {}
    for cls, vals in sorted(by_class.items()):
        n = len(vals)
        mean = sum(vals) / n
        sd = math.sqrt(sum((v - mean) ** 2 for v in vals) / n) if n > 1 else 0.0
        out[cls] = {
            "n_resolved": n,
            "mean_counterfactual_bps": round(mean, 3),
            "sd_bps": round(sd, 3),
            "positive_share": round(sum(1 for v in vals if v > 0) / n, 3),
            "sufficient_for_a_bias_claim": n >= MIN_POPULATION_FOR_BIAS,
        }
    return out


def systematic_bias(decisions: list[Decision]) -> list[dict[str, object]]:
    """Rejection reasons whose whole population was wrong in one direction. THE LEGITIMATE USE.

    This is a claim about the REJECTOR, not about any candidate, so the selection problem above
    does not apply in the same way: the question is whether a rule that fired N times produced a
    population whose mean forward return is inconsistent with the rule being correct. That is
    answerable, and it is how a 15%-too-pessimistic cost model gets found.

    Still requires MIN_POPULATION_FOR_BIAS. A rule that rejected 9 things is not a rule with a
    measurable bias, however lopsided those nine look.
    """
    summary = counterfactual_summary(decisions)
    findings: list[dict[str, object]] = []
    for cls, row in summary.items():
        n = int(row["n_resolved"])
        if n < MIN_POPULATION_FOR_BIAS:
            continue
        mean = float(row["mean_counterfactual_bps"])
        sd = float(row["sd_bps"])
        if sd <= 0:
            continue
        t = mean / (sd / math.sqrt(n))
        if abs(t) < 3.0:
            continue
        findings.append({
            "rejection_class": cls,
            "n": n,
            "mean_counterfactual_bps": mean,
            "t": round(t, 2),
            "finding": (
                f"{cls} rejected {n} opportunities whose mean forward return was {mean:+.2f}bp "
                f"(t={t:.1f}). A correct rejection rule should produce a population centred near "
                "zero net of costs; this one does not. The finding is about the RULE -- it "
                "licenses a preregistered test of a recalibrated rule on untouched data, and it "
                "reinstates nothing"),
        })
    findings.sort(key=lambda f: -abs(float(str(f["t"]))))
    return findings


def summarise(decisions: list[Decision]) -> dict[str, object]:
    """Report shape for `data/decision_ledger.json`."""
    if not decisions:
        return {"decisions": 0, "headline": (
            "no decisions recorded. The desk's decision surface is currently legible only where "
            "it said yes, which is the smallest and least informative part of it")}
    counts: dict[str, int] = {}
    for d in decisions:
        counts[d.outcome] = counts.get(d.outcome, 0) + 1
    executed = counts.get("EXECUTED", 0)
    rejected = len(decisions) - executed
    unresolved = sum(1 for d in decisions if d.rejected and not d.resolved)
    bias = systematic_bias(decisions)
    return {
        "decisions": len(decisions),
        "executed": executed,
        "rejected": rejected,
        "execution_share": round(executed / len(decisions), 4),
        "counts_by_outcome": dict(sorted(counts.items(), key=lambda kv: -kv[1])),
        "counterfactuals": counterfactual_summary(decisions),
        "unresolved_rejections": unresolved,
        "systematic_bias": bias,
        "headline": (
            f"{len(bias)} rejection rule(s) show a systematic bias across their populations: "
            f"{[b['rejection_class'] for b in bias]}" if bias else
            f"{executed} executed of {len(decisions)} evaluated ({executed / len(decisions):.1%}); "
            f"{unresolved} rejection(s) have no counterfactual attached yet, so whether any "
            "rejection rule is systematically wrong is UNMEASURED for those"),
        "note": ("A favourable counterfactual NEVER reinstates the decision it belongs to -- the "
                 "population is conditioned on the rejection being tested. Counterfactuals are "
                 "admissible only as evidence about a rejection RULE across at least "
                 f"{MIN_POPULATION_FOR_BIAS} decisions, and any resulting change must be "
                 "preregistered and tested on untouched data."),
    }

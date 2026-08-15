"""THE ALPHA STATE MACHINE — governance that an organ cannot route around.

THE GAP THIS CLOSES, named by the principal on 2026-08-08 and true when he named it: this desk's
governance is excellent as prose and thin as machinery. Every rule about what an alpha must survive
before it touches capital lives in documents that a script is free not to read. Nothing in the code
makes `DISCOVERED -> LIVE` impossible; it is merely undone. An undone thing and an impossible thing
look identical right up until the morning they do not.

So the transitions become an object. An alpha advances ONE rung at a time, each rung names the
evidence it requires, and a skipped rung is a hard refusal rather than an omission nobody notices.

    DISCOVERED -> IMPLEMENTED -> TESTED -> STATISTICALLY_VALID -> SHADOW
      -> OOS_VALIDATED -> INDEPENDENCE_CHECKED -> PORTFOLIO_VALIDATED -> CAPITAL_ELIGIBLE
      -> LIVE -> MONITORED  (and DEGRADED / RETIRED from anywhere)

WHAT THIS IS NOT. It is not a promoter. It grants nothing, sizes nothing and places nothing --
`CAPITAL_ELIGIBLE` is a statement about EVIDENCE, and arming live trading remains the principal's
act with the Tier-3 rail untouched. A module that could advance an alpha to LIVE would be the
bypass it exists to prevent.

THREE PROPERTIES, each chosen against a specific way this would otherwise rot:

  NO SKIPPING, INCLUDING UPWARD. `advance` refuses a jump even when the evidence for the higher
  rung is present, because the rung below has its own evidence and "we already know it passes" is
  precisely the reasoning that was never written down. The desk may only step.

  RETREAT IS ALWAYS LEGAL. DEGRADED and RETIRED are reachable from every state, and monitoring can
  push an alpha back down. A machine that only ratchets forward turns a decayed edge into a
  permanent one, which is worse than having no machine.

  EVIDENCE IS NAMED, NOT ASSERTED. Every transition requires the evidence KEYS its rung declares
  to be present and non-empty. A caller passing `{"oos": ""}` is refused, because an empty string
  is how a checkbox gets ticked by a script with nothing to say.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from pathlib import Path

__all__ = [
    "ORDER",
    "RUNGS",
    "TERMINAL",
    "AlphaRecord",
    "AlphaStateLedger",
    "Rung",
    "advance",
    "next_rung",
    "requirements",
    "retreat",
]


@dataclass(frozen=True)
class Rung:
    """One state, and the evidence a candidate owes to reach it."""

    name: str
    #: Evidence keys that must be present and non-empty. Empty tuple = entry state only.
    requires: tuple[str, ...]
    #: Why this rung exists as a separate step rather than being folded into its neighbour.
    why: str


#: The ladder. Order IS the law: `advance` walks it and refuses anything but the next entry.
RUNGS: tuple[Rung, ...] = (
    Rung("DISCOVERED", (),
         "the entry state -- a mechanism named. Costs nothing and proves nothing"),
    Rung("IMPLEMENTED", ("expression", "data_source"),
         "an idea that cannot be expressed against real data is not yet a candidate; forcing this "
         "rung is what stops a prose mechanism from being counted in the funnel"),
    Rung("TESTED", ("n_observations", "result"),
         "a result EXISTS. Says nothing about whether it is good -- separating existence from "
         "quality is what makes UNMEASURED reportable instead of collapsing into failure"),
    Rung("STATISTICALLY_VALID", ("t_stat", "deflated_hurdle", "trials_declared"),
         "cleared the DECLARED-universe hurdle. `trials_declared` is required by name because "
         "deflating on the executed count rather than the declared one is the most respectable "
         "route to a manufactured survivor (L1.52a)"),
    Rung("SHADOW", ("shadow_started_at",),
         "a pre-registered forward clock is running at zero capital. It must precede OOS: the "
         "clock is the producer of genuinely untouched observations, so requiring OOS before "
         "starting it is a circular gate that can never pay its own evidence debt"),
    Rung("OOS_VALIDATED", ("oos_result", "split_rule_preregistered"),
         "held on observations accrued after the zero-capital clock was registered, under a "
         "decision rule chosen before those observations arrived"),
    Rung("INDEPENDENCE_CHECKED", ("mechanism_cluster", "correlation_to_book"),
         "a distinct MECHANISM, not the fiftieth expression of a deployed alpha. Four formulas "
         "over one feature are one research family, and counting them as four is how a generator "
         "reports enormous productivity while re-searching one neighbourhood"),
    Rung("PORTFOLIO_VALIDATED", ("marginal_contribution", "capacity"),
         "improves the EXISTING book after correlation, cost and capacity. Standalone Sharpe "
         "cannot answer this and is routinely mistaken for an answer to it"),
    Rung("LIVE_CANARY", ("canary_size_quote_units", "principal_canary_authorisation"),
         "REAL FILLS AT LEARNING SIZE, and the rung that exists because simulation cannot answer "
         "the question it is asked. A canary is not there to make money -- it is there to test "
         "whether the market behaves like the simulator: fills, slippage, queue position, adverse "
         "selection, venue quirks, operational reliability. Months of shadow cannot produce that "
         "information at any price, so an alpha kept out of the market is not being validated, it "
         "is being starved of the one evidence class it most needs. It still requires the "
         "principal's authorisation -- at canary size, which is a smaller decision than capital, "
         "never no decision"),
    Rung("CAPITAL_ELIGIBLE", ("forward_observations", "forward_result", "risk_review",
                              "canary_execution_evidence"),
         "the EVIDENCE for capital is complete, INCLUDING evidence from real fills -- a strategy "
         "that has never traded has no execution evidence, and its forward record is a simulation "
         "of a simulation. This is a statement about evidence and never a grant: arming live "
         "trading is the principal's act"),
    Rung("LIVE", ("principal_authorisation", "size_quote_units"),
         "capital is deployed. Requires an explicit principal authorisation token that no organ "
         "can synthesise -- the one rung the machine refuses to reason its way onto"),
    Rung("MONITORED", ("monitor_since",),
         "under continuous decay, drift and execution-degradation watch. Not a resting place: "
         "it is the rung from which DEGRADED is reached"),
)

ORDER: tuple[str, ...] = tuple(r.name for r in RUNGS)

#: Reachable from ANY state. A machine that only ratchets forward makes a decayed edge permanent.
TERMINAL: tuple[str, ...] = ("DEGRADED", "RETIRED")

_BY_NAME: dict[str, Rung] = {r.name: r for r in RUNGS}


@dataclass(frozen=True)
class AlphaRecord:
    """One candidate's position on the ladder, with the evidence it has accumulated."""

    alpha_id: str
    state: str = "DISCOVERED"
    evidence: dict[str, str] = field(default_factory=dict)
    history: tuple[tuple[str, str], ...] = ()   # (state, iso timestamp)
    note: str = ""

    @property
    def is_terminal(self) -> bool:
        return self.state in TERMINAL

    @property
    def rung_index(self) -> int:
        """Position on the ladder; -1 for terminal states, which sit off it."""
        return ORDER.index(self.state) if self.state in ORDER else -1


class AlphaStateLedger:
    """Append-only durable materialisation of the canonical ladder.

    The transition function remains the sole authority. The ledger only persists transitions it
    accepted, so a restart or controller handoff resumes the same alpha rather than rebuilding an
    optimistic state from whichever report happens to be newest.
    """

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self.records = self._load()

    def _load(self) -> dict[str, AlphaRecord]:
        if not self.path.exists():
            return {}
        records: dict[str, AlphaRecord] = {}
        for number, line in enumerate(self.path.read_text("utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
                rec = AlphaRecord(
                    alpha_id=str(row["alpha_id"]), state=str(row["state"]),
                    evidence={str(k): str(v) for k, v in dict(row["evidence"]).items()},
                    history=tuple((str(a), str(b)) for a, b in row["history"]),
                    note=str(row.get("note", "")),
                )
            except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
                raise ValueError(f"malformed alpha-state ledger line {number}: {exc}") from exc
            if rec.state not in ORDER and rec.state not in TERMINAL:
                raise ValueError(f"malformed alpha-state ledger line {number}: unknown state")
            prior = records.get(rec.alpha_id, AlphaRecord(alpha_id=rec.alpha_id))
            if len(rec.history) != len(prior.history) + 1 or \
                    rec.history[:-1] != prior.history or rec.history[-1][0] != rec.state:
                raise ValueError(
                    f"malformed alpha-state ledger line {number}: history is not append-only"
                )
            if rec.state in TERMINAL:
                expected, _ = retreat(prior, rec.state, reason=rec.note or "ledgered retreat",
                                      now=rec.history[-1][1])
            else:
                expected, why = advance(prior, rec.state, rec.evidence, now=rec.history[-1][1])
                if expected.state != rec.state:
                    raise ValueError(
                        f"malformed alpha-state ledger line {number}: illegal transition ({why})"
                    )
            if expected.history != rec.history or expected.evidence != rec.evidence:
                raise ValueError(
                    f"malformed alpha-state ledger line {number}: snapshot does not match "
                    "transition"
                )
            records[rec.alpha_id] = rec
        return records

    def get(self, alpha_id: str) -> AlphaRecord:
        return self.records.get(alpha_id, AlphaRecord(alpha_id=alpha_id))

    def advance(self, alpha_id: str, to: str, evidence: dict[str, str], *,
                now: str = "") -> tuple[AlphaRecord, str]:
        current = self.get(alpha_id)
        moved, reason = advance(current, to, evidence, now=now)
        if moved == current:
            return moved, reason
        self._append(moved)
        self.records[alpha_id] = moved
        return moved, reason

    def _append(self, rec: AlphaRecord) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        row = json.dumps({
            "schema_version": 1, "alpha_id": rec.alpha_id, "state": rec.state,
            "evidence": rec.evidence, "history": rec.history, "note": rec.note,
        }, sort_keys=True)
        with self.path.open("a", encoding="utf-8", newline="\n") as fh:
            fh.write(row + "\n")
            fh.flush()
            os.fsync(fh.fileno())


def requirements(state: str) -> tuple[str, ...]:
    """Evidence keys a candidate owes to ENTER `state`. Unknown states owe nothing knowable."""
    r = _BY_NAME.get(state)
    return r.requires if r else ()


def next_rung(state: str) -> str | None:
    """The only state `advance` will accept from here. None at the top or off the ladder."""
    if state not in ORDER:
        return None
    i = ORDER.index(state)
    return ORDER[i + 1] if i + 1 < len(ORDER) else None


def _missing(required: tuple[str, ...], evidence: dict[str, str]) -> list[str]:
    """Keys absent or EMPTY. An empty value is how a checkbox gets ticked by a script with
    nothing to say, so it counts as missing rather than as present-but-blank."""
    return [k for k in required if not str(evidence.get(k, "")).strip()]


def advance(rec: AlphaRecord, to: str, evidence: dict[str, str], *,
            now: str = "") -> tuple[AlphaRecord, str]:
    """(record, reason). Moves EXACTLY one rung, or refuses and returns the record unchanged.

    SKIPPING IS REFUSED EVEN WHEN THE HIGHER RUNG'S EVIDENCE IS PRESENT. The rung below has its
    own evidence requirement, and "we already know it would pass" is exactly the reasoning that
    never gets written down -- which is the state this machine exists to make impossible rather
    than merely discouraged.
    """
    if rec.is_terminal:
        return rec, (f"{rec.alpha_id} is {rec.state}: a terminal state is not a pause. Re-entry "
                     "starts at DISCOVERED with a new record, so the retired history stays "
                     "readable as evidence rather than being overwritten")
    if to in TERMINAL:
        return retreat(rec, to, reason="advance() called with a terminal state", now=now)
    expected = next_rung(rec.state)
    if expected is None:
        return rec, f"{rec.alpha_id} is at {rec.state}; there is no rung above it"
    if to != expected:
        return rec, (f"REFUSED {rec.state} -> {to}: the only legal next rung is {expected}. "
                     "Skipping is refused even when the higher rung's evidence is in hand -- the "
                     f"rung below has its own bar ({', '.join(requirements(expected)) or 'none'}) "
                     "and stepping over it is how governance becomes prose")
    missing = _missing(requirements(to), evidence)
    if missing:
        return rec, (f"REFUSED {rec.state} -> {to}: missing evidence {missing}. "
                     f"{_BY_NAME[to].why}")
    stamp = now or datetime.now(tz=UTC).isoformat()
    return replace(rec, state=to, evidence={**rec.evidence, **evidence},
                   history=(*rec.history, (to, stamp))), f"{rec.state} -> {to}"


def retreat(rec: AlphaRecord, to: str, *, reason: str, now: str = "") -> tuple[AlphaRecord, str]:
    """Move DOWN or out. Always legal, and deliberately requires no evidence.

    Requiring evidence to retreat would make the safe direction the expensive one -- the desk would
    keep a decaying alpha live because retiring it needed a study. A reason is required instead,
    because a silent retirement loses the information the failure carries.
    """
    if not reason.strip():
        return rec, ("REFUSED: a retreat needs a stated reason. A silent retirement discards the "
                     "most specific information the desk owns about where an effect is NOT")
    if to not in TERMINAL and to not in ORDER:
        return rec, f"REFUSED: {to} is not a state"
    if to in ORDER and rec.rung_index >= 0 and ORDER.index(to) > rec.rung_index:
        return rec, (f"REFUSED: {to} is ABOVE {rec.state}. Retreat moves down or out; use "
                     "advance() to climb, one rung at a time")
    stamp = now or datetime.now(tz=UTC).isoformat()
    return replace(rec, state=to, history=(*rec.history, (to, stamp)),
                   note=reason), f"{rec.state} -> {to} ({reason})"


def render(rec: AlphaRecord) -> str:
    """One line for a human, naming what the NEXT rung costs -- never just where it sits."""
    if rec.is_terminal:
        return f"{rec.alpha_id}: {rec.state} -- {rec.note or 'no reason recorded'}"
    nxt = next_rung(rec.state)
    if nxt is None:
        return f"{rec.alpha_id}: {rec.state} (top of ladder)"
    missing = _missing(requirements(nxt), rec.evidence)
    owed = ", ".join(missing) if missing else "nothing -- advance it"
    return f"{rec.alpha_id}: {rec.state} -> {nxt} owes: {owed}"

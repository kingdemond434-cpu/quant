"""THE ALLOCATOR INTERRUPT -- a REQUEST to solve sooner, never an instruction about the answer.

WHAT CHANGED UNDER THIS MODULE, AND WHY IT MATTERS MORE THAN IT LOOKS. The allocator's fast leg
was 300s; it is now 60s (`research_supervisor.PERIODIC`, cadence_s fast=60). The baseline
staleness an interrupt has to beat therefore fell by a factor of five, and most of the case for
interrupting went with it. An interrupt is only worth firing when the information's value decays
inside the wait -- so the question is not "is this important" but "will this be worth
measurably less in sixty seconds than it is now".

WHICH EVENTS GENUINELY NEED TO PREEMPT A ONE-MINUTE CLOCK. On the evidence available, very few,
and the honest answer is worth more than an eager one:

    yes    an unscheduled central-bank action or intervention reaching the desk on a
           low-latency feed -- the SNB-in-2015 shape, where the unpriced fraction halves in
           seconds
    yes    a scheduled release the desk receives structured and same-second, where the first
           sixty seconds ARE the event
    no     anything arriving via RSS. Measured on this box, every source is a first-party feed
           generated after the release; median arrival is tens of seconds to minutes behind the
           tape, so by the time the item exists the sixty-second wait costs a small fraction of
           what is left. An interrupt here buys nothing and spends a solve.
    no     anything whose horizon is hours or days -- a policy shift, a trade measure, a harvest
           report. A sixty-second wait is free.

So `should_fire` requires a MEASURED decay half-life shorter than the clock. Not a guessed one:
an event class whose decay the ledger has not measured cannot preempt, because the whole
justification for preempting is a number nobody has.

THE ECONOMIC GATE, WHICH IS THE ONE THAT STOPS THIS BEING AN EXPENSIVE CLOCK. Rebalancing for a
gain smaller than the execution cost is a loss with extra steps, and the allocator already knows
that -- `pf_allocator.no_trade` charges turnover at `TURNOVER_COST_R` and only moves when the
growth bought over the no-trade horizon exceeds it. The interrupt applies the SAME test to the
narrower question it is actually asking: does solving now rather than in `wait_s` buy more than
the turnover it would cause? If not, the answer is HOLD and the fast clock handles it. This
module never loosens the no-trade region; it defers to it and adds its own cost on top.

WHAT THE ARTIFACT IS AND IS NOT. A request file. It says "an event of this importance arrived,
consider solving now" plus the evidence. It contains no weights, no direction, no instrument
targets, and the supervisor's only permitted response is to launch a fast pass earlier than it
otherwise would. Everything about what the book should be stays where it already is.

THE SUPERVISOR HOOK IS SPECIFIED HERE AND NOT APPLIED. `SUPERVISOR_HOOK` is the exact patch
`desks/mt5/research/research_supervisor.py` needs -- ten lines, purely additive, and incapable of
making the allocator run less often than it does today.
"""

from __future__ import annotations

import json
import time
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .ledger import MACRO_DIR, write_json_atomic
from .schema import Status, now_iso, parse_ts

INTERRUPT_PATH = MACRO_DIR / "allocator_interrupt.json"
INTERRUPT_LOG = MACRO_DIR / "interrupt_log.jsonl"

#: The supervisor's fast cadence. MUST track `research_supervisor.PERIODIC[0]["cadence_s"]
#: ["fast"]`; `desks/mt5/tests/test_macro_interrupt_contract.py` fails if the two drift apart,
#: because a stale copy here would size the interrupt's economics against a clock that no longer
#: exists -- and would do it silently.
FAST_CLOCK_S = 60

#: `pf_allocator.TURNOVER_COST_R` -- round-trip price of a unit of heat moved, account fraction.
#: Duplicated rather than imported because importing the allocator pulls numpy, pandas and a
#: module-level solve into a capture path that must stay light. The same test pins the two
#: values together, so the duplication cannot rot into a disagreement.
TURNOVER_COST_R = 0.06

#: Rate limits. An interrupt that fires constantly is just an expensive clock, and each one
#: spends a solve on an 8GB box shared with the gauntlet and the brain seats.
RATE_WINDOW_S = 600
MAX_PER_WINDOW = 3
MIN_SPACING_S = 60

#: A request older than this is ignored by the supervisor. Short: the entire premise is that the
#: information decays inside a minute, so a request that has been sitting for two is answering a
#: question that no longer exists.
REQUEST_TTL_S = 120

#: Floor on the unpriced fraction. Below this there is not enough information left in front of
#: the market to be worth a special solve, whatever the importance score says.
MIN_UNPRICED = 0.25

__all__ = [
    "FAST_CLOCK_S",
    "MAX_PER_WINDOW",
    "MIN_UNPRICED",
    "RATE_WINDOW_S",
    "REQUEST_TTL_S",
    "SUPERVISOR_HOOK",
    "TURNOVER_COST_R",
    "Decision",
    "pending",
    "request",
    "should_fire",
]


@dataclass(frozen=True)
class Decision:
    fire: bool
    reason: str
    detail: dict[str, Any]


def should_fire(*, importance: float, importance_status: str, unpriced_fraction: float | None,
                decay_half_life_s: float | None, capital_authority: bool,
                expected_gain_per_day: float | None, expected_turnover: float,
                history: Sequence[float] = (), now: float | None = None,
                wait_s: float = FAST_CLOCK_S,
                turnover_cost_r: float = TURNOVER_COST_R) -> Decision:
    """Every gate, in the order that makes the cheapest refusal first.

    `expected_gain_per_day` is the allocator's own units -- log-wealth per day the desk expects
    from acting on this now rather than on the stale book. `expected_turnover` is the fraction of
    heat that would move. Both come from the caller because both belong to the allocator's world,
    not this one; passing None for the gain means the desk cannot price the move and the answer
    is HOLD.
    """
    t = time.time() if now is None else now
    d: dict[str, Any] = {"wait_s": wait_s, "importance": importance,
                         "unpriced_fraction": unpriced_fraction,
                         "decay_half_life_s": decay_half_life_s}

    if not capital_authority:
        return Decision(False, "no capital authority: the event class has not earned the right "
                               "to size anything", d)
    if importance_status != Status.MEASURED:
        return Decision(False, f"importance is {importance_status}; only a MEASURED importance "
                               "may preempt the clock", d)
    if unpriced_fraction is None or unpriced_fraction < MIN_UNPRICED:
        return Decision(False, f"unpriced fraction {unpriced_fraction} < MIN_UNPRICED="
                               f"{MIN_UNPRICED}: too little information left in front of the "
                               "market to justify a special solve", d)
    if decay_half_life_s is None:
        return Decision(False, "decay half-life UNMEASURED. The justification for preempting a "
                               f"{wait_s:.0f}s clock IS the decay rate; without a measured one "
                               "there is no case, and the fast clock handles it", d)
    if decay_half_life_s >= wait_s:
        return Decision(False, f"decay half-life {decay_half_life_s:.0f}s >= wait {wait_s:.0f}s: "
                               "waiting for the fast clock costs less than half the "
                               "information. HOLD", d)
    if expected_gain_per_day is None:
        return Decision(False, "expected gain not priced by the allocator; cannot show the move "
                               "beats its own cost", d)

    # The economic gate. Value lost by waiting, against the cost of moving now. Exponential
    # decay over the wait: the desk loses the fraction that decays before the clock fires.
    decayed = 1.0 - 0.5 ** (wait_s / max(decay_half_life_s, 1e-9))
    gain_at_risk = float(expected_gain_per_day) * (wait_s / 86400.0) * decayed
    cost = float(expected_turnover) * turnover_cost_r
    d.update({"decayed_fraction_over_wait": round(decayed, 6),
              "gain_at_risk": round(gain_at_risk, 10), "turnover_cost": round(cost, 10)})
    if gain_at_risk <= cost:
        return Decision(False, f"gain at risk over the wait ({gain_at_risk:.3e}) does not exceed "
                               f"the turnover it would cause ({cost:.3e}). Rebalancing for less "
                               "than the execution cost is a loss with extra steps", d)

    recent = [h for h in history if t - h <= RATE_WINDOW_S]
    if recent and t - max(recent) < MIN_SPACING_S:
        return Decision(False, f"last interrupt {t - max(recent):.0f}s ago < MIN_SPACING_S="
                               f"{MIN_SPACING_S}", d)
    if len(recent) >= MAX_PER_WINDOW:
        return Decision(False, f"{len(recent)} interrupts in the last {RATE_WINDOW_S}s "
                               f"(max {MAX_PER_WINDOW}): rate limited", d)

    return Decision(True, "measured decay inside the clock, unpriced information remains, and "
                          "the value at risk exceeds the turnover cost", d)


def request(*, event_ids: Sequence[str], decision: Decision, importance: float,
            unpriced_fraction: float | None, path: Path | str | None = None,
            log_path: Path | str | None = None, now: float | None = None) -> dict[str, Any]:
    """Write the request artifact atomically and append to the audit log.

    Atomically because a separate process polls this file every thirty seconds; a partial read
    would either crash the supervisor or, worse, act on half a request.
    """
    t = time.time() if now is None else now
    payload = {
        "schema": 1,
        "requested_at": now_iso(),
        "requested_at_epoch": t,
        "expires_at_epoch": t + REQUEST_TTL_S,
        "ttl_s": REQUEST_TTL_S,
        "mode": "fast",
        "authority": "REQUEST_ONLY",
        "event_ids": list(event_ids),
        "importance": importance,
        "unpriced_fraction": unpriced_fraction,
        "reason": decision.reason,
        "evidence": decision.detail,
        "note": ("A request to SOLVE SOONER. It carries no weights, no direction and no "
                 "instrument targets. The allocator's no-trade filter still decides whether the "
                 "solved book is worth trading toward."),
    }
    p = Path(path) if path is not None else INTERRUPT_PATH
    write_json_atomic(p, payload)
    lp = Path(log_path) if log_path is not None else INTERRUPT_LOG
    lp.parent.mkdir(parents=True, exist_ok=True)
    with open(lp, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, separators=(",", ":"), sort_keys=True, default=str) + "\n")
    return payload


def pending(path: Path | str | None = None, *, now: float | None = None,
            consumed_at: float = 0.0) -> dict[str, Any] | None:
    """The supervisor's side. Returns a live, unconsumed request, or None.

    Pure and side-effect-free so the supervisor stays the only thing that records consumption --
    two writers to one piece of state is how a request gets served twice.
    """
    p = Path(path) if path is not None else INTERRUPT_PATH
    if not p.exists():
        return None
    try:
        raw = json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(raw, dict):
        return None
    t = time.time() if now is None else now
    req_at = float(raw.get("requested_at_epoch") or 0.0)
    exp_at = float(raw.get("expires_at_epoch") or 0.0)
    if req_at <= consumed_at:
        return None
    if exp_at and t > exp_at:
        return None
    return raw


def history_from_log(log_path: Path | str | None = None,
                     limit: int = 50) -> list[float]:
    """Recent interrupt timestamps, for the rate limiter."""
    lp = Path(log_path) if log_path is not None else INTERRUPT_LOG
    if not lp.exists():
        return []
    out: list[float] = []
    try:
        lines = lp.read_text("utf-8").splitlines()[-limit:]
    except OSError:
        return []
    for line in lines:
        try:
            row = json.loads(line)
        except ValueError:
            continue
        ts = row.get("requested_at_epoch")
        if isinstance(ts, int | float):
            out.append(float(ts))
        else:
            dt = parse_ts(row.get("requested_at"))
            if dt is not None:
                out.append(dt.timestamp())
    return out


#: THE EXACT HOOK `desks/mt5/research/research_supervisor.py` NEEDS. Ten lines, purely additive.
#: It cannot make the allocator run LESS often than it does today: every existing path through
#: `tick_periodic` is untouched, and the new branch is reached only where the function currently
#: does nothing (`mode is None` -- no cadence is due).
SUPERVISOR_HOOK = '''
# --- in desks/mt5/research/research_supervisor.py -------------------------------------------
#
# 1. beside the other imports:
#
#     sys.path.insert(0, str(BASE))            # already effectively true; BASE is desks/mt5
#     from macro import interrupt as _macro_interrupt
#
#    (guard it: `try: ... except Exception: _macro_interrupt = None` -- the supervisor is the
#     desk's watchdog and must survive this package being absent or broken.)
#
# 2. inside `tick_periodic`, replace
#
#        mode = _allocator_mode(state, now, p["cadence_s"])
#        if mode is None:
#            continue
#
#    with
#
#        mode = _allocator_mode(state, now, p["cadence_s"])
#        req = None
#        if mode is None and p["name"] == "pf_allocator" and _macro_interrupt is not None:
#            try:
#                req = _macro_interrupt.pending(
#                    now=now,
#                    consumed_at=float(state.get("macro_interrupt_consumed_at", 0) or 0))
#            except Exception:
#                req = None
#            if req is not None:
#                mode = "fast"
#        if mode is None:
#            continue
#
# 3. immediately after the successful `spawn`, record consumption so one request serves once:
#
#        if req is not None:
#            state["macro_interrupt_consumed_at"] = float(req.get("requested_at_epoch", now))
#            log(f"supervisor: macro interrupt honoured -- {req.get('reason','')[:120]}")
#
# PROPERTIES THIS HOOK HAS, ON PURPOSE:
#   * additive -- no existing branch changes, so the allocator can only run at least as often
#   * fast-only -- an interrupt never triggers the expensive normal or heavy legs
#   * one-shot -- `macro_interrupt_consumed_at` makes a request serve exactly once
#   * still guarded by `is_running(p["match"])` above it, so an interrupt cannot stack solves
#   * still filtered by the allocator's own no-trade region, which decides whether the freshly
#     solved book is worth trading toward. The interrupt makes the book FRESHER. It has no
#     opinion about whether the book should move.
'''

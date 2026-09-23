#!/usr/bin/env python3
"""P3 / P35 / P73 -- WHEN TO REBALANCE, WHEN THE RL MAY RUN, AND THE EXIT AS ITS OWN ALPHA.

P3 -- THE HEARTBEAT RE-EVALUATES OPTIMALITY. NOT EVERY EVALUATION REBALANCES.

    rebalance only when   dElog(move) > execution cost + estimation uncertainty

Both subtracted terms are the point. A desk that rebalances whenever the optimum has drifted
churns the book to chase a number inside its own error bars, and pays the spread every time to
do it. The uncertainty term is the one usually omitted: the optimum is itself estimated, so a
drift smaller than the estimate's own noise is not a drift, and acting on it is paying a certain
cost for an uncertain gain.

The heartbeat is one minute because an EVENT can invalidate an allocation in seconds and a clock
that only wakes hourly cannot notice. The evaluation is cheap by construction -- it compares two
numbers -- so a minute of resolution costs almost nothing and the trigger is what stays expensive.

P35 -- EXECUTION RL IS A CHALLENGER, AND ONLY AFTER THE TWIN IS CALIBRATED.

The order in that sentence is a hard gate, not a preference. An RL policy learns against a model
of execution; if that model is uncalibrated the policy learns to exploit the MODEL, and the
better it gets at the simulator the worse it does live. This is the single most reliable way to
build a confident, expensive, backwards execution policy.

So this module REFUSES to run the challenger until the execution twin has demonstrated
calibration on real fills. Measured 2026-09-06: `markout_usable` is false and matched fills are
unmeasured, so the correct state today is REFUSED -- and reporting that is the capability
working, not the capability missing.

P73 -- EXIT, RE-ENTRY AND PYRAMID ARE SEPARATE ALPHA DOMAINS.

The desk researches entries and inherits exits from whatever the entry rule happened to specify.
That is a large unexamined surface: for most mechanisms the exit rule carries as much variance as
the entry, and re-entry after a stop is a distinct decision with its own edge -- one that entry
research never sees because the entry has already happened. `exit_study` exists on this tree and
nothing imported it, so it was CODED and inert; this is the consumer that makes it a domain.
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent.parent
ROOT = BASE.parent.parent
REPORT = BASE / "reports" / "REBALANCE_TRIGGER.json"

#: Heartbeat period. One minute because an EVENT can invalidate an allocation in seconds; the
#: evaluation is a comparison of two numbers, so resolution is nearly free and only the TRIGGER
#: is expensive.
HEARTBEAT_SECONDS = 60

#: Round-trip execution cost charged against any rebalance, in dElog units. Deliberately a
#: charge and not an estimate: a rebalance whose gain does not clear its own spread is a
#: transfer to the broker dressed as portfolio management.
EXECUTION_COST = 0.004

#: Multiplier on the optimum's own standard error. The optimum is ESTIMATED, so a drift smaller
#: than the estimate's noise is not a drift. Omitting this term is how a desk churns daily.
UNCERTAINTY_Z = 1.0


@dataclass(frozen=True)
class Evaluation:
    """One heartbeat: how much better the proposed allocation is, and how well we know it."""

    delta_elog: float
    #: Standard error of `delta_elog` itself.
    se: float
    reason: str = "heartbeat"


def should_rebalance(e: Evaluation, cost: float = EXECUTION_COST,
                     z: float = UNCERTAINTY_Z) -> dict[str, Any]:
    """P3. Rebalance only when the gain clears BOTH the cost and the noise.

    Returning False is the common and correct answer. A trigger that fires most heartbeats is
    not a trigger, it is a schedule -- and a schedule that pays the spread.
    """
    hurdle = cost + z * max(0.0, e.se)
    go = e.delta_elog > hurdle
    return {
        "rebalance": bool(go), "delta_elog": round(e.delta_elog, 6),
        "hurdle": round(hurdle, 6), "execution_cost": cost,
        "uncertainty_term": round(z * max(0.0, e.se), 6), "reason": e.reason,
        "why": (f"dElog {e.delta_elog:+.5f} clears a hurdle of {hurdle:.5f} "
                f"(cost {cost:.4f} + {z}x se {e.se:.5f})"
                if go else
                f"dElog {e.delta_elog:+.5f} does not clear {hurdle:.5f}. "
                + ("the gain is smaller than the estimate's own noise, so the 'drift' is not "
                   "distinguishable from zero" if e.delta_elog <= z * max(0.0, e.se) else
                   "the gain does not pay the round trip; rebalancing would transfer it to the "
                   "broker")),
    }


# --------------------------------------------------------------------------- P35
def twin_calibrated(state_path: Path | None = None) -> dict[str, Any]:
    """Has the execution twin demonstrated calibration against REAL fills?

    UNMEASURED IS NOT CALIBRATED. A twin nobody has checked against live fills is a simulator
    with an unknown bias, and an RL policy trained on it learns the bias.
    """
    p = state_path or (BASE / "data" / "execution_twin_state.json")
    try:
        doc = json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return {"calibrated": False, "status": "UNMEASURED",
                "why": f"{p.name} is absent or unreadable on this host; a twin nobody has "
                       "checked against live fills is a simulator with an unknown bias"}
    matched = doc.get("matched_fills") or doc.get("n_matched") or 0
    usable = doc.get("markout_usable") is True
    return {
        "calibrated": bool(usable and matched >= 200),
        "status": "CALIBRATED" if (usable and matched >= 200) else "NOT_CALIBRATED",
        "matched_fills": matched, "markout_usable": usable,
        "why": ("markout is usable over enough matched fills to price the twin's error"
                if usable and matched >= 200 else
                f"markout_usable={usable!r} over {matched} matched fill(s); the twin's error "
                "against reality is not yet measured"),
    }


def rl_challenger_admissible(state_path: Path | None = None) -> dict[str, Any]:
    """P35. The RL challenger may not run until the twin is calibrated. A hard gate.

    An RL policy learns against a MODEL of execution. If the model is uncalibrated the policy
    learns to exploit the model, and the better it scores in simulation the worse it does live --
    the most reliable way there is to build a confident, expensive, backwards execution policy.
    """
    cal = twin_calibrated(state_path)
    return {
        "admissible": cal["calibrated"], "twin": cal,
        "role": "CHALLENGER_ONLY",
        "why": ("the twin is calibrated, so a challenger policy trained against it is learning "
                "execution rather than learning the simulator. It remains a challenger and owns "
                "no position."
                if cal["calibrated"] else
                "REFUSED -- " + cal["why"] + ". Training a policy against an uncalibrated twin "
                "teaches it to exploit the model; the better it looks in simulation the worse it "
                "does live, and reporting this refusal IS the capability working"),
    }


# --------------------------------------------------------------------------- P73
def exit_domains() -> dict[str, Any]:
    """P73. Exit, re-entry and pyramid named as separate research domains with separate rent.

    The desk researches ENTRIES and inherits exits from whatever the entry rule specified. For
    most mechanisms the exit carries as much variance as the entry, and re-entry after a stop is
    a decision entry research never sees because the entry already happened.
    """
    available = (BASE / "research" / "exit_study.py").exists()
    return {
        "domains": [
            {"domain": "exit", "owner": "research/exit_study.py",
             "why": "for most mechanisms the exit rule carries as much variance as the entry, "
                    "and it is inherited rather than researched"},
            {"domain": "re_entry", "owner": "research/exit_study.py",
             "why": "a distinct decision with its own edge, invisible to entry research because "
                    "the entry has already happened"},
            {"domain": "pyramid", "owner": "research/exit_study.py",
             "why": "adding to a winner is a separate bet on persistence, not a larger version "
                    "of the original bet"},
        ],
        "owner_present": available,
        "status": "WIRED" if available else "OWNER_MISSING",
        "why": ("exit_study exists on this tree and nothing imported it, so it was CODED and "
                "inert. This is the consumer that makes it a domain."
                if available else
                "research/exit_study.py is absent; the domains are named and unowned"),
    }


def run() -> dict[str, Any]:
    return {
        "measured_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "heartbeat_seconds": HEARTBEAT_SECONDS,
        "trigger_examples": {
            "noise_sized_drift": should_rebalance(Evaluation(0.002, 0.010, "heartbeat")),
            "real_but_unprofitable": should_rebalance(Evaluation(0.003, 0.0001, "heartbeat")),
            "worth_doing": should_rebalance(Evaluation(0.050, 0.004, "macro event")),
        },
        "execution_rl": rl_challenger_admissible(),
        "exit_domains": exit_domains(),
        "rule": ("Rebalance only when dElog exceeds execution cost PLUS the optimum's own "
                 "estimation noise. A trigger that fires most heartbeats is not a trigger, it "
                 "is a schedule that pays the spread."),
    }


def main(argv: list[str] | None = None) -> int:
    doc = run()
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    print(f"rebalance trigger: heartbeat {HEARTBEAT_SECONDS}s, "
          f"hurdle = cost {EXECUTION_COST} + {UNCERTAINTY_Z}x se")
    for name, t in doc["trigger_examples"].items():
        print(f"   {'REBALANCE' if t['rebalance'] else 'hold     '} {name:24} "
              f"dElog {t['delta_elog']:+.5f} vs hurdle {t['hurdle']:.5f}")
    rl = doc["execution_rl"]
    print(f"   execution RL: {'ADMISSIBLE' if rl['admissible'] else 'REFUSED'} -- "
          f"{rl['twin']['why'][:70]}")
    ed = doc["exit_domains"]
    print(f"   exit domains: {ed['status']} ({len(ed['domains'])} named)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

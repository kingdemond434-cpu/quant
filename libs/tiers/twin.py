"""THE DIGITAL TWIN OF THE DESK (Tier S layer 28): challengers run beside production on the same
inputs, and win only on information that arrived after they were registered.

A CHALLENGER is any alternative policy for a component (the allocator's book, a validator config,
an execution rule, a research scheduler). It is REGISTERED with a timestamp and a content hash.
From then on, every decision the incumbent makes is paired with the one the challenger would have
made on the same recorded inputs, and both are scored on the outcome when it arrives. Evidence
from before registration is never counted -- a challenger fitted to the past cannot claim the past
as its proof.

`evaluate()` returns a paired verdict:

    PROMOTE     paired mean improvement > 0 with a one-sided t > t_crit over >= min_pairs pairs
    REJECT      >= min_pairs pairs and the improvement is <= 0 with t < -t_crit
    CONTINUE    anything else (still UNMEASURED / not decided)

Promotion of a RESEARCH component is automatic (its adoption file is research state). Promotion of
a MONEY-PATH component (allocator, sizing, admission, certificates, order flow) is a PROPOSAL the
principal must accept in words. Rollback is one operation: `rollback_plan()` names the previous
sealed release and the single command that returns the branch to it.
"""
from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from libs.tiers.replay import parse_t

MONEY_PATH_COMPONENTS = frozenset({"allocator", "sizing", "admission", "certificates",
                                   "order_flow", "promoter", "gateway"})


@dataclass(frozen=True)
class Challenger:
    component: str
    name: str
    registered_at: str
    genome_hash: str


def evaluate(ch: Challenger, pairs: Iterable[tuple[str, float, float]], *,
             min_pairs: int = 30, t_crit: float = 2.0) -> dict[str, Any]:
    """pairs: (time, incumbent_outcome, challenger_outcome). Only times after registration."""
    reg = parse_t(ch.registered_at)
    diffs: list[float] = []
    dropped = 0
    for when, inc, cha in pairs:
        tt = parse_t(when)
        if reg is None or tt is None or tt <= reg:
            dropped += 1
            continue
        diffs.append(float(cha) - float(inc))
    n = len(diffs)
    if n == 0:
        return {"verdict": "CONTINUE", "n": 0, "dropped_before_registration": dropped,
                "money_path": ch.component in MONEY_PATH_COMPONENTS}
    m = sum(diffs) / n
    sd = math.sqrt(sum((d - m) ** 2 for d in diffs) / max(1, n - 1)) if n > 1 else 0.0
    t = m / (sd / math.sqrt(n)) if sd > 0 else (math.inf if m > 0 else -math.inf if m < 0
                                                else 0.0)
    if n >= min_pairs and m > 0 and t > t_crit:
        verdict = "PROMOTE" if ch.component not in MONEY_PATH_COMPONENTS else "PROPOSE"
    elif n >= min_pairs and m <= 0 and t < -t_crit:
        verdict = "REJECT"
    else:
        verdict = "CONTINUE"
    return {"verdict": verdict, "n": n, "mean_improvement": m,
            "t": t if math.isfinite(t) else None, "dropped_before_registration": dropped,
            "money_path": ch.component in MONEY_PATH_COMPONENTS}


def rollback_plan(releases: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """releases: newest last, each {sha, at, sealed?}. The one operation back to the previous
    sealed release."""
    sealed = [r for r in releases if r.get("sha") and r.get("sealed", True)]
    if len(sealed) < 2:
        return {"available": False, "why": f"{len(sealed)} sealed release(s) known"}
    cur, prev = sealed[-1], sealed[-2]
    return {"available": True, "current": cur.get("sha"), "target": prev.get("sha"),
            "command": (f"python desks/mt5/research/tier_s.py --rollback-to {prev.get('sha')} "
                               "--apply-rollback"),
            "effect": "one revert commit on the box branch; MT5-AdoptRelease adopts it within "
                      "the hour"}

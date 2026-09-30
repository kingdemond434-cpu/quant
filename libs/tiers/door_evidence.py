"""THE REVIEW PANEL AND THE THEORY GRAPH AT THE PROMOTION DOOR (Tier S layers 18 and 20).

Until 2026-09-30 the panel's verdicts and the theory graph's statuses were published and gated
nothing. This turns the two into per-certificate door verdicts, written hourly by the `tier_s`
organ `door` to `data/tier_s/door_verdicts.json` and read by `promotion_authority.block`.

WHAT MAY WITHHOLD, AND WHY SO LITTLE OF IT DOES.

  REVIEW_PANEL_FAILED  a HIGH challenge the panel resolved AGAINST the candidate on the
                       candidate's OWN evidence: its forward clock reached 40 trades with a
                       non-positive mean (`forward_n_40`), or its x5-cost stress world is
                       negative (`stress_x5_positive`). Challenges resolved by program-level
                       facts are excluded: a Red Queen leak is a hole in the certifier, true of
                       every certificate at once, so it withholds none of them (it is the
                       immune FREEZE's business); replication and online FDR already have their
                       own door verdicts, so they are not counted twice.
                       The closure/agent-world reviewer's two HIGH challenges count too:
                       `closure_gap_survives` (the candidate's own positive edge turns
                       negative when the venue shuts and reopens gapped) and
                       `agent_worlds_survive` (it loses in all three agent ecologies). Both
                       are the candidate's own replays, never a program-level fact.
  THEORY_REFUTED       the certificate's mechanism is REFUTED on OUT-OF-SAMPLE evidence alone
                       (forward, live and replication, weighted as the theory graph weights
                       them), with at least MIN_OOS pieces of it. Backtest failures are left out
                       on purpose: 97% of judged cells fail, so on backtest evidence nearly every
                       family reads REFUTED, and that measures the search, not the mechanism.

Both are withhold-only, like every door verdict: nothing is sized down, no open position or
funded row is touched, and every withheld row is billed by the `tier_s_evidence_block` rail.
"""
from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from typing import Any

from libs.tiers.theory import EVIDENCE_WEIGHT

#: the panel resolvers whose verdict is a fact about the candidate itself
CANDIDATE_SPECIFIC = frozenset({"forward_n_40", "stress_x5_positive",
                                "closure_gap_survives", "agent_worlds_survive"})
OOS_SOURCES = frozenset({"forward", "live", "replication"})
MIN_OOS = 10


def review_failed(row: Mapping[str, Any]) -> list[str]:
    """The candidate-specific HIGH challenges the panel resolved FAILED on this row."""
    return [f"{c.get('reviewer')}:{c.get('kind')}" for c in row.get("challenges") or []
            if isinstance(c, Mapping) and c.get("state") == "FAILED"
            and c.get("severity") == "HIGH" and c.get("resolves_when") in CANDIDATE_SPECIFIC]


def oos_posterior(evidence: Iterable[tuple[bool, str]]) -> dict[str, Any]:
    """Beta posterior over (supports, source) pairs from out-of-sample sources only."""
    sup = con = 0.0
    n = 0
    for supports, source in evidence:
        if source not in OOS_SOURCES:
            continue
        w = EVIDENCE_WEIGHT.get(source, 1.0)
        n += 1
        if supports:
            sup += w
        else:
            con += w
    a, b = 1.0 + sup, 1.0 + con
    mean = a / (a + b)
    sd = math.sqrt(a * b / ((a + b) ** 2 * (a + b + 1)))
    if n < MIN_OOS:
        status = "UNMEASURED"
    elif mean + 2 * sd < 0.35:
        status = "REFUTED"
    elif mean - 2 * sd > 0.5:
        status = "SUPPORTED"
    else:
        status = "CONTESTED"
    return {"n_oos": n, "confidence": round(mean, 4), "sd": round(sd, 4), "status": status}


def build(panel_rows: Iterable[Mapping[str, Any]], family_of: Mapping[str, str],
          oos_by_family: Mapping[str, list[tuple[bool, str]]]) -> dict[str, dict[str, Any]]:
    """{certificate key: {review_failed, family, theory}} for every reviewed certificate."""
    fam_post = {f: oos_posterior(ev) for f, ev in oos_by_family.items()}
    out: dict[str, dict[str, Any]] = {}
    for row in panel_rows:
        key = str(row.get("candidate") or "")
        if not key:
            continue
        fam = family_of.get(key, "")
        out[key] = {"verdict": row.get("verdict"), "review_failed": review_failed(row),
                    "family": fam,
                    "theory": fam_post.get(fam) or {"status": "UNMEASURED", "n_oos": 0}}
    return out


def door_reason(row: Mapping[str, Any]) -> str | None:
    """The door's reason from one verdict row, or None."""
    failed = row.get("review_failed") or []
    if failed:
        return ("REVIEW_PANEL_FAILED: the panel resolved a HIGH challenge against this "
                f"candidate on its own evidence ({', '.join(map(str, failed))})")
    th = row.get("theory") or {}
    if th.get("status") == "REFUTED":
        return (f"THEORY_REFUTED: the {row.get('family')} mechanism is refuted out of sample "
                f"(confidence {th.get('confidence')} on {th.get('n_oos')} forward/live/"
                "replication results)")
    return None

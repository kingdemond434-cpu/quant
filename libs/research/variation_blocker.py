"""TRIVIAL-VARIATION BLOCKER + REJECTION TELEMETRY -- HYPOTHESIS_MAX #2 and #3.

#3, THE BLOCKER. Two hypotheses sharing a mechanism fingerprint are the SAME IDEA wearing different
parameters. Re-testing one is not new evidence -- it is a fresh multiplicity charge for a question
already asked, which is the garden of forking paths with a lookback knob on it. The desk's own
record is the case in point: 420 candidates, 0 survivors, and nothing in the pipeline could say how
many of the 420 were genuinely distinct questions.

The charge is the point. Every look costs multiplicity budget, so a re-parameterisation is worse
than useless: it consumes the budget that a genuinely new idea would have needed, and it inflates
the trial count that DSR and the stepdown correct against. Blocking it BEFORE compute is both a
cost saving and a statistical one, and the second matters more.

#2, THE TELEMETRY. `do_not_repeat` already routes rejections, but as free text -- so "why do ideas
die?" could only be answered by reading. Rejections are now STRUCTURED (stage + reason +
fingerprint), which lets the generator LEARN from them rather than merely be stopped by them.

=================================================================================================
WHAT THIS DELIBERATELY DOES NOT DO
=================================================================================================
It does not block on SIMILARITY, only on an EXACT fingerprint match plus a near-duplicate check
that must clear a high bar. A blocker tuned to catch "close enough" ideas silently narrows the
search space, and the desk already has a measured, expensive instance of an over-tight funnel
(the $100k capacity floor; the campaign-constant gates behind 420/0). Under L1.21a the timid
error here is the more expensive one, so the bar is set where a false block is unlikely and a
missed duplicate is merely a wasted trial.

A blocked idea is ALWAYS recorded with what it duplicated, so "blocked" never means "lost": the
ledger is a map of the space already searched, which is the input the breeder (#4) will need the
day it unblocks.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from libs.research.mechanism_fingerprint import describe, fingerprint, jaccard, tokens

_ROOT = Path(__file__).resolve().parents[2]
LEDGER = _ROOT / "data/variation_ledger.jsonl"

#: Jaccard at or above this counts as a near-duplicate even when fingerprints differ. Set HIGH on
#: purpose: at 0.90 two ideas share almost all their mechanism vocabulary. Lowering it trades a
#: cheap wasted trial for the risk of silently deleting a genuinely new question.
NEAR_DUP_JACCARD = 0.90


@dataclass(frozen=True)
class Verdict:
    allowed: bool
    reason: str
    fingerprint: str
    duplicate_of: str | None = None
    similarity: float | None = None

    def as_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)


def _seen(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    out = []
    for line in path.read_text("utf-8").splitlines():
        if line.strip():
            try:
                out.append(json.loads(line))
            except ValueError:
                continue
    return out


def screen(hyp: Any, *, path: Path = LEDGER, prior: list[dict[str, Any]] | None = None) -> Verdict:
    """ALLOW or BLOCK, before any compute is spent. Pure apart from reading the ledger."""
    fp = fingerprint(hyp)
    seen = prior if prior is not None else _seen(path)
    accepted = [r for r in seen if r.get("allowed")]

    for r in accepted:
        if r.get("fingerprint") == fp:
            return Verdict(False, "exact mechanism fingerprint already tested -- this is the same "
                                  "idea with different parameters, and re-testing it charges "
                                  "multiplicity for a question already asked",
                           fp, duplicate_of=str(r.get("id", "?")), similarity=1.0)

    my = tokens(describe(hyp))
    for r in accepted:
        sim = jaccard(my, frozenset(r.get("tokens", [])))
        if sim >= NEAR_DUP_JACCARD:
            return Verdict(False, f"near-duplicate of a tested idea (Jaccard {sim:.2f} >= "
                                  f"{NEAR_DUP_JACCARD}) -- distinct fingerprint but the same "
                                  "mechanism vocabulary",
                           fp, duplicate_of=str(r.get("id", "?")), similarity=round(sim, 3))

    return Verdict(True, "novel mechanism fingerprint", fp)


def record(hyp: Any, verdict: Verdict, *, hyp_id: str = "", stage: str = "pre-compute",
           generator: str = "", path: Path = LEDGER) -> dict[str, Any]:
    """Append the decision. A BLOCK is recorded as fully as an ALLOW.

    Blocked ideas are the map of the space already searched -- exactly the input the breeder (#4)
    needs the day it unblocks -- so dropping them would be discarding the record of the work.
    """
    row = {
        "at": datetime.now(tz=UTC).isoformat(),
        "id": hyp_id or f"{fingerprint(hyp)}@{datetime.now(tz=UTC).timestamp():.0f}",
        "stage": stage, "generator": generator,
        "allowed": verdict.allowed, "reason": verdict.reason,
        "fingerprint": verdict.fingerprint, "duplicate_of": verdict.duplicate_of,
        "similarity": verdict.similarity,
        "tokens": sorted(tokens(describe(hyp))),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")
    return row


def telemetry(*, path: Path = LEDGER) -> dict[str, Any]:
    """#2: WHERE ideas die and WHY, structured -- the generator's feedback signal.

    A rejection reason nobody aggregates teaches nothing. This is what turns a stream of blocks
    into a statement about the search: which stages kill, which fingerprints are saturated, and
    what share of generated volume was genuinely new.
    """
    rows = _seen(path)
    if not rows:
        return {"n": 0, "note": "no generation screened yet"}
    blocked = [r for r in rows if not r.get("allowed")]
    by_stage: dict[str, int] = {}
    by_reason: dict[str, int] = {}
    by_fp: dict[str, int] = {}
    for r in blocked:
        by_stage[str(r.get("stage"))] = by_stage.get(str(r.get("stage")), 0) + 1
        key = str(r.get("reason", ""))[:60]
        by_reason[key] = by_reason.get(key, 0) + 1
    for r in rows:
        fp = str(r.get("fingerprint"))
        by_fp[fp] = by_fp.get(fp, 0) + 1
    novel = len(rows) - len(blocked)
    return {
        "n": len(rows), "n_blocked": len(blocked), "n_novel": novel,
        "novel_rate": round(novel / len(rows), 4),
        "distinct_fingerprints": len(by_fp),
        "blocked_by_stage": by_stage, "blocked_by_reason": by_reason,
        "most_attempted_fingerprints": sorted(by_fp.items(), key=lambda kv: -kv[1])[:5],
        "note": "novel_rate is the honest generation yield: the share of produced ideas that "
                "were genuinely new questions rather than reparameterisations. Volume without "
                "it is throughput, not information.",
    }

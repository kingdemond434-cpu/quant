"""RESEARCH-CAPITAL AUCTION -- gate items 14/26/27: the comparison is a RECORD, not a mood.

THE GAP THIS CLOSES. Mandate XVII orders that existing-data exploitation be ECONOMICALLY COMPARED
against new-data acquisition before either wins resources, and the gate demands proof in both
directions: an existing-data candidate defeating a new source when its marginal value is greater
(item 26) and a genuinely superior new free source defeating existing-data work (item 27). The
desk has actually MADE both decisions -- screen_conversion over any new acquisition on 2026-08-05
(114 already-scored cells were unreadable by the finalizer, and unlocking them beat every
alternative use of the same build day), and collect_circulating_supply STARTED the same day even
though existing-data work was abundant, because a point-in-time series is the one asset that can
never be backfilled. But both decisions lived in commit messages and docstrings: right, and
unfindable. A decision that cannot be found cannot be audited, repeated, or overturned by better
evidence -- so from here the auction is an append-only ledger row, made when the decision is made.

WHAT A ROW IS AND IS NOT. A row records WHICH candidate won a unit of scarce research capacity,
WHY in marginal-value terms, and WHAT EVIDENCE each side carried. It allocates nothing by itself:
the desk's schedulers and the principal remain the actuators. And a comparison with a missing side
is REFUSED loudly -- "existing data won" is only a decision if a real alternative was actually
priced, otherwise it is a preference wearing a ledger row.

RETROACTIVE ROWS are permitted and say so: `decided_utc` is when the decision truly happened,
`recorded_utc` when the row was written, and a row where those differ must cite repo artifacts
that already prove the decision. History is assembled, never invented.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

__all__ = ["LEDGER", "AuctionError", "compare", "decisions", "record_decision"]

_ROOT = Path(__file__).resolve().parents[2]
#: Committed under docs/, not data/ -- an auction decision is institutional memory, and the data/
#: tree is gitignored runtime state that a container rebuild erases. (Learned the hard way on
#: 2026-08-11, when a container restart destroyed an unpushed commit.)
LEDGER = "docs/research/research_auction.jsonl"

_SIDES = ("EXISTING_DATA", "NEW_SOURCE", "NEW_HYPOTHESIS", "INFRASTRUCTURE", "EXECUTION")


class AuctionError(ValueError):
    """A comparison the auction refuses to score. Loud, because a silently-scored one-sided
    auction is how a preference gets laundered into a decision."""


def _now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def compare(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    """Score two candidates for the same unit of research capacity. Returns the winner + margin.

    Each candidate declares: `side` (one of the named classes), `marginal_value` (expected
    uncertainty-adjusted contribution, any consistent unit), `cost` (same unit -- engineering +
    compute + opportunity, TOTAL economic cost per XX-A, never just price), and `evidence` (what
    grounds the estimate). The score is value minus cost; the auction takes the larger. No side
    gets a class bonus: item 26 and item 27 are the SAME arithmetic pointing different ways on
    different days, which is the whole point -- the class of the winner is an outcome, never an
    input.
    """
    for c in (a, b):
        missing = [k for k in ("side", "marginal_value", "cost", "evidence") if k not in c]
        if missing:
            raise AuctionError(f"candidate {c.get('side', '?')!r} missing {missing} -- a "
                               "comparison with an unpriced side is a preference, not a decision")
        if c["side"] not in _SIDES:
            raise AuctionError(f"unknown side {c['side']!r}; valid: {_SIDES}")
        if not str(c["evidence"]).strip():
            raise AuctionError(f"{c['side']}: evidence is empty -- an ungrounded marginal-value "
                               "estimate cannot enter the auction")
    sa = float(a["marginal_value"]) - float(a["cost"])
    sb = float(b["marginal_value"]) - float(b["cost"])
    winner, loser = (a, b) if sa >= sb else (b, a)
    return {"winner": winner["side"], "loser": loser["side"],
            "winner_score": max(sa, sb), "loser_score": min(sa, sb),
            "margin": abs(sa - sb),
            "note": "scores are value-minus-TOTAL-cost in the candidates' shared unit; the "
                    "winning CLASS is an outcome of the arithmetic, never an input to it"}


def record_decision(*, question: str, chosen: dict[str, Any], rejected: dict[str, Any],
                    decided_utc: str, artifacts: list[str],
                    retroactive_basis: str = "", root: Path | None = None) -> dict[str, Any]:
    """Append one auction decision. compare() runs first so the ledger cannot hold a row whose
    arithmetic disagrees with its verdict."""
    verdict = compare(chosen, rejected)
    if verdict["winner"] != chosen["side"]:
        raise AuctionError(
            f"the declared choice ({chosen['side']}) LOSES its own comparison to "
            f"{rejected['side']} by {verdict['margin']:.3g} -- either the estimates are wrong or "
            "the decision is; the ledger will not paper over the disagreement")
    row = {
        "decided_utc": decided_utc, "recorded_utc": _now(),
        "question": question,
        "chosen": chosen, "rejected": rejected, "verdict": verdict,
        "artifacts": artifacts,
        "retroactive_basis": retroactive_basis or None,
        "authority": "RECORD ONLY -- allocates nothing; schedulers and the principal actuate.",
    }
    base = root or _ROOT
    path = base / LEDGER
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row


def decisions(root: Path | None = None) -> list[dict[str, Any]]:
    base = root or _ROOT
    out: list[dict[str, Any]] = []
    try:
        text = (base / LEDGER).read_text("utf-8", errors="ignore")
    except OSError:
        return out
    for line in text.splitlines():
        if line.strip():
            try:
                out.append(json.loads(line))
            except ValueError:
                continue
    return out

"""Source-verification backlog picker -- clears the EXISTING catalogue queue, never generates more.

The desk's data-hunting organs (prospector/litminer/dataaxis) already catalogue candidate sources
faster than they get verified (docs/research/data_axis_watchlist.md carries a real backlog). The
bottleneck was never generation -- it is VERIFICATION (read the actual docs/ToS, test the actual
endpoint; the Baidu-vs-NAVER distinction this session took real reading, not a prompt).
So this module does NOT propose new sources; it parses the EXISTING catalogue's source cards and
picks the next ones still genuinely pending -- "if not already in system" -- so a cycle spends its
verification effort on the real backlog instead of re-litigating settled cards or, worse, growing
the pile faster than it shrinks.

Grade taxonomy (as written in the source cards, natural-language, not a rigid enum):
  RESOLVED     -- verified-clean or destroyed-at-source, with no other component pending. Excluded
                  from every queue: it is "already in system," settled, work is over.
  VERIFICATION -- needs-monitoring / UNVERIFIED (bare, or as any component of a compound grade like
                  "needs-monitoring (forward) / destroyed-at-source (backfill)" -- a partial
                  resolution still leaves real work, so the whole card stays pending, conservative).
                  This is a TECHNICAL check: read the docs, hit the endpoint, diff vs ground truth.
  LEGITIMACY   -- needs-legitimacy-review. A POLICY/legal decision (account-gating, ToS, licensing),
                  not a technical test -- kept in its own queue so it is never silently treated as
                  "verified" by a mechanical script, and never mixed with technical-check items.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from pathlib import Path

from pydantic import BaseModel, ConfigDict

_CARD_RE = re.compile(r"^### (\d+)\.\s+(.+?)\s+—\s+grade:\s*(.+?)\s*$", re.MULTILINE)


class SourceCard(BaseModel):
    """One catalogued source card, as written in the watchlist."""

    model_config = ConfigDict(frozen=True)

    card_id: int
    name: str
    grade_raw: str
    category: str  # "resolved" | "verification" | "legitimacy"


def _classify(grade_raw: str) -> str:
    g = grade_raw.lower()
    # Check non-terminal substrings FIRST -- a compound grade with ANY pending component (e.g.
    # "needs-monitoring (forward) / destroyed-at-source (backfill)") stays pending as a whole; a
    # partially-resolved card still has real work left, so it is never silently closed out.
    if "needs-legitimacy-review" in g:
        return "legitimacy"
    if "needs-monitoring" in g or "unverified" in g:
        return "verification"
    if "verified-clean" in g or "destroyed-at-source" in g:
        return "resolved"
    return "verification"  # unrecognized grade text -- fail open to pending, never silently drop


def parse_watchlist(text: str) -> list[SourceCard]:
    """Extract every ``### N. Name — grade: ...`` source card from a watchlist markdown body."""
    cards = []
    for m in _CARD_RE.finditer(text):
        card_id, name, grade_raw = int(m.group(1)), m.group(2).strip(), m.group(3).strip()
        cards.append(SourceCard(
            card_id=card_id, name=name, grade_raw=grade_raw, category=_classify(grade_raw),
        ))
    return cards


class BacklogReport(BaseModel):
    """The parsed backlog, split by queue -- resolved cards are reported but never re-worked."""

    model_config = ConfigDict(frozen=True)

    n_total: int
    n_resolved: int
    n_verification_pending: int
    n_legitimacy_pending: int
    next_verification: tuple[str, ...]  # names, priority order, capped
    next_legitimacy: tuple[str, ...]
    verdict: str


def next_pending(cards: Sequence[SourceCard], *, limit: int = 0) -> BacklogReport:
    """Pick the next items to work THIS cycle -- excluding anything already resolved.

    Priority within the verification queue: ``needs-monitoring`` cards (already partially
    corroborated -- cheaper to finish) before bare ``UNVERIFIED`` ones (found, nothing confirmed --
    more work), then by card id (oldest backlog first, so a shiny new catalogue entry never jumps a
    card that has been waiting -- the same anti-hype-bias reasoning as near-miss-first reject
    scoring). ``limit`` <= 0 (the default) surfaces ALL pending cards --
    conversion is never throttled; a positive value caps the batch for display only.
    """
    resolved = [c for c in cards if c.category == "resolved"]
    verif = [c for c in cards if c.category == "verification"]
    legit = [c for c in cards if c.category == "legitimacy"]

    def _verif_rank(c: SourceCard) -> tuple[int, int]:
        cheaper = 0 if "needs-monitoring" in c.grade_raw.lower() else 1
        return (cheaper, c.card_id)

    verif_sorted = sorted(verif, key=_verif_rank)
    legit_sorted = sorted(legit, key=lambda c: c.card_id)
    # limit <= 0 means UNBOUNDED (principal 2026-07-25: conversion must always maximise and
    # exhaust; a cap on how many findings are even SURFACED throttles conversion before work
    # starts). Note `[:0]` is EMPTY, not unbounded -- the slice must be skipped, not zeroed.
    next_v = tuple(c.name for c in (verif_sorted if limit <= 0 else verif_sorted[:limit]))
    next_l = tuple(c.name for c in (legit_sorted if limit <= 0 else legit_sorted[:limit]))

    if not verif and not legit:
        verdict = f"backlog clear: all {len(resolved)} catalogued source(s) resolved"
    else:
        verdict = (
            f"{len(verif)} pending technical verification, {len(legit)} pending a legitimacy/"
            f"policy decision, {len(resolved)} already resolved (excluded) -- this cycle: "
            f"verify {list(next_v) or 'none'}"
        )
    return BacklogReport(
        n_total=len(cards), n_resolved=len(resolved),
        n_verification_pending=len(verif), n_legitimacy_pending=len(legit),
        next_verification=next_v, next_legitimacy=next_l, verdict=verdict,
    )


def backlog_from_file(path: Path, *, limit: int = 0) -> BacklogReport:
    """Convenience: parse a watchlist file straight to its next-pending report."""
    return next_pending(parse_watchlist(path.read_text("utf-8")), limit=limit)

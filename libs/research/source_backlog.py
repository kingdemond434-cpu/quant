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
  DEFERRED     -- carries a §33 `deferred(YYYY-MM-DD)` marker whose date has NOT arrived. Real work,
                  correctly queued, simply not workable TODAY -- see below.

WHAT THE QUEUE MUST NOT DO, and did for 15 days (F0002, raised 2026-07-28 by the CN frontier
miner, accepted, measured cost: three separate sessions -- 07-26 CN, 07-26 EN-C, 07-28 CN -- each
re-derived by hand that the same cards were not workable).

A card is surfaced as "VERIFY this cycle" only if a miner could actually do it this cycle. Two
classes were being surfaced that no miner can act on, and both came from the SAME line: the
classifier's fail-open `return "verification"` for unrecognised grade text.

  1. TERMINAL KILLS. `KILLED as a purchase ... [§33: killed -> docs/graveyard.md eodhd_paid_vendor]`
     matches none of the recognised substrings, so it fell through to "pending verification" and
     was offered as this cycle's work FOREVER. Three of the fifteen items in the 2026-08-12 queue
     were killed cards with graveyard entries. Fail-open is right for text nobody has seen before;
     it is wrong for a disposition the desk writes deliberately in a documented format.
  2. DATED DEFERRALS. `[§33: deferred(2026-08-24) tier:2]` states, in machine-readable form, that
     the card is blocked until a date. Offering it today wastes the read; hiding it forever would
     be worse. It is excluded ONLY while the date is in the future and returns to the queue on its
     own the day it passes -- the exclusion carries its re-entry condition by construction, and
     the report always names the next return date so a deferral can never become a quiet drop.

THE DISPOSITION IS READ FROM THE §33 MARKER, NEVER FROM PROSE. One card reads "hourly rung of the
family is graveyard-KILLED" inside a needs-monitoring grade: substring-matching "killed" would
resolve a card with live work owed. Only `[§33: ...]` counts.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from datetime import UTC, date, datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict

_CARD_RE = re.compile(r"^### (\d+)\.\s+(.+?)\s+—\s+grade:\s*(.+?)\s*$", re.MULTILINE)
#: The §33 disposition marker the miners write, e.g. `[§33: deferred(2026-08-24) tier:2]`,
#: `[§33: killed -> docs/graveyard.md eodhd_paid_vendor]`, `[§33: wired -> data/x.jsonl]`.
_S33_RE = re.compile(r"\[§33:\s*(?P<verb>[a-z]+)\s*(?:\((?P<date>\d{4}-\d{2}-\d{2})\))?")


class SourceCard(BaseModel):
    """One catalogued source card, as written in the watchlist."""

    model_config = ConfigDict(frozen=True)

    card_id: int
    name: str
    grade_raw: str
    category: str  # "resolved" | "verification" | "legitimacy" | "deferred"
    deferred_until: date | None = None


def _s33(grade_raw: str) -> tuple[str, date | None]:
    """(verb, date) from the card's §33 marker, or ("", None) when it carries none."""
    m = _S33_RE.search(grade_raw)
    if m is None:
        return "", None
    d: date | None = None
    if m.group("date"):
        try:
            d = date.fromisoformat(m.group("date"))
        except ValueError:
            d = None            # a malformed date is NOT a deferral; the card stays workable
    return m.group("verb"), d


def _classify(grade_raw: str, *, today: date) -> tuple[str, date | None]:
    g = grade_raw.lower()
    verb, until = _s33(grade_raw)
    # A §33 KILL is a deliberate terminal disposition with a graveyard entry behind it (audited
    # separately by max_audit's mine-conversion check). Read from the MARKER, never from prose.
    if verb == "killed":
        return "resolved", None
    # A DATED DEFERRAL is workable-later, not workable-now. Strictly `>` today, so a card whose
    # date is TODAY is workable today -- and every past date returns to the queue automatically.
    if verb == "deferred" and until is not None and until > today:
        return "deferred", until
    # Non-terminal substrings FIRST -- a compound grade with ANY pending component (e.g.
    # "needs-monitoring (forward) / destroyed-at-source (backfill)") stays pending as a whole; a
    # partially-resolved card still has real work left, so it is never silently closed out.
    if "needs-legitimacy-review" in g:
        return "legitimacy", None
    if "needs-monitoring" in g or "unverified" in g:
        return "verification", None
    if "verified-clean" in g or "destroyed-at-source" in g:
        return "resolved", None
    return "verification", None  # unrecognized grade text -- fail open, never silently drop


def parse_watchlist(text: str, *, today: date | None = None) -> list[SourceCard]:
    """Extract every ``### N. Name — grade: ...`` source card from a watchlist markdown body.

    ``today`` is injectable so the deferral boundary is testable; it defaults to the UTC date,
    matching the dates the miners write into the §33 markers.
    """
    day = today or datetime.now(tz=UTC).date()
    cards = []
    for m in _CARD_RE.finditer(text):
        card_id, name, grade_raw = int(m.group(1)), m.group(2).strip(), m.group(3).strip()
        category, until = _classify(grade_raw, today=day)
        cards.append(SourceCard(
            card_id=card_id, name=name, grade_raw=grade_raw,
            category=category, deferred_until=until,
        ))
    return cards


class BacklogReport(BaseModel):
    """The parsed backlog, split by queue -- resolved cards are reported but never re-worked."""

    model_config = ConfigDict(frozen=True)

    n_total: int
    n_resolved: int
    n_verification_pending: int
    n_legitimacy_pending: int
    n_deferred: int = 0
    next_verification: tuple[str, ...]  # names, priority order, capped
    next_legitimacy: tuple[str, ...]
    #: (name, date) for every card blocked by a future §33 deferral, soonest first. Published so
    #: a deferral is VISIBLE as pending work with a return date, never a silent drop.
    deferred: tuple[tuple[str, str], ...] = ()
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
    defer = sorted((c for c in cards if c.category == "deferred"),
                   key=lambda c: (c.deferred_until or date.max, c.card_id))

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

    # A deferral is pending work with a date, so it is always COUNTED and its return date named.
    # "blocked until the 24th" and "gone" must never render the same (F0002's whole complaint).
    defer_note = (f", {len(defer)} deferred (next returns "
                  f"{defer[0].deferred_until.isoformat() if defer[0].deferred_until else '?'})"
                  if defer else "")
    if not verif and not legit:
        verdict = (f"backlog clear: all {len(resolved)} catalogued source(s) resolved"
                   f"{defer_note}" if defer else
                   f"backlog clear: all {len(resolved)} catalogued source(s) resolved")
    else:
        verdict = (
            f"{len(verif)} pending technical verification, {len(legit)} pending a legitimacy/"
            f"policy decision, {len(resolved)} already resolved (excluded){defer_note} -- "
            f"this cycle: verify {list(next_v) or 'none'}"
        )
    return BacklogReport(
        n_total=len(cards), n_resolved=len(resolved),
        n_verification_pending=len(verif), n_legitimacy_pending=len(legit),
        n_deferred=len(defer),
        next_verification=next_v, next_legitimacy=next_l,
        deferred=tuple((c.name, c.deferred_until.isoformat() if c.deferred_until else "?")
                       for c in defer),
        verdict=verdict,
    )


def backlog_from_file(path: Path, *, limit: int = 0, today: date | None = None) -> BacklogReport:
    """Convenience: parse a watchlist file straight to its next-pending report."""
    return next_pending(parse_watchlist(path.read_text("utf-8"), today=today), limit=limit)

"""§33 MINED-TO-WIRED law -- zero research inventory.

Mined intelligence is INVENTORY, and un-converted inventory is WASTE that depreciates. A finding
that is catalogued and never wired has produced NEGATIVE value: it consumed a cycle, it inflates
the desk's capability inventory, and it makes every downstream audit read the desk as richer than
it is (the map-vs-territory failure this whole audit family exists to catch). Mining is not the
product -- CONVERSION is. A perfect dig with zero conversions is a FAILED cycle.

This module is the machine-checkable half of §33. It does NOT do conversions (nothing automates
that -- it is irreducibly research work); it makes the backlog IMPOSSIBLE TO NOT SEE, which is the
difference between a law and a wish. §31 only started working when a daily check with a 48h
escalation stood behind it; this is the same shape for mined findings.

DISPOSITION CONTRACT -- every carded find carries exactly one, written inline in the dig-output
doc as ``[§33: <disposition>]``. Four legal values, no fifth; SILENCE IS A DEFECT, not a neutral
state:

  wired            -- code exists AND executed AND wrote a real artifact
  screened         -- a Stage-A screen RAN; result in research_memory, --axis tagged
  killed           -- graveyard entry carrying the MECHANISM of death (never "low priority")
  deferred(DATE)   -- a NAMED blocker and an ISO date. UNDATED DEFERRAL IS ILLEGAL -- it is the
                      hiding place every rotting backlog uses, so it is parsed, rejected, and
                      reported rather than silently accepted.

Two anti-gaming rules are structural, not advisory:

  EXPIRY  -- ``deferred(2026-08-01)`` stops counting as disposed the moment that date passes. A
             deferral is a promise with a clock, not a filing cabinet.
  NO SELF-GRADING -- ``wired``/``screened`` are CLAIMS about artifacts. The caller passes the set
             of names it could actually corroborate on disk; anything claiming conversion without
             a backing artifact is reported as UNBACKED. An organ does not grade its own homework
             (the same artifact-only credit rule as ``max_audit._converted_axes``).
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from datetime import date

from pydantic import BaseModel, ConfigDict

#: A carded find: ``### N. Name`` only. Deliberately NOT bold bullets -- source cards carry
#: ``- **Provenance**:`` / ``- **Queries used**:`` metadata fields, and treating those as finds
#: made the check fire 92/92 on its first real run. A check that flags everything is ignored, so
#: the id-numbered card is the one unambiguous unit of "a thing that was found".
#: The id is captured separately so it never lands in ``name`` -- a name of "1. Upbit" would fail
#: to match the artifact "upbit_krw_btc_1m" in either direction and report a real conversion as
#: unbacked. Matches ``source_backlog``'s card_id/name split.
_ITEM_RE = re.compile(r"^### (?P<cid>\d+)\.\s+(?P<card>.+?)\s*$", re.MULTILINE)
#: The inline disposition tag. Tolerant of "S33"/"section 33" so an ASCII-only writer still counts.
_DISP_RE = re.compile(
    r"\[(?:§|S|section\s*)33:\s*(?P<verb>[a-z-]+)\s*(?:\(\s*(?P<until>[0-9]{4}-[0-9]{2}-[0-9]{2})"
    r"\s*\))?\s*\]",
    re.IGNORECASE,
)

LEGAL = ("wired", "screened", "killed", "deferred")
#: Dispositions that are terminal -- the item is finished and never re-enters the backlog.
_TERMINAL = ("wired", "screened", "killed")
#: Dispositions asserting an artifact exists, and therefore subject to corroboration.
_CLAIMS_ARTIFACT = ("wired", "screened")


class MinedItem(BaseModel):
    """One carded find plus whatever disposition was written against it."""

    model_config = ConfigDict(frozen=True)

    source: str
    name: str
    disposition: str = ""  # "" = none written == UNDISPOSED (silence is a defect)
    deferred_until: str = ""
    illegal_reason: str = ""


def parse_dispositions(text: str, *, source: str) -> list[MinedItem]:
    """Extract every carded find in ``text`` and the disposition written on its own line.

    The tag must appear on the SAME line as the item so a single blanket ``[§33: wired]`` at the
    top of a document cannot launder an entire backlog.
    """
    items: list[MinedItem] = []
    for line in text.splitlines():
        m = _ITEM_RE.match(line)
        if not m:
            continue
        name = m.group("card").strip()
        # strip the tag out of the display name so the same find matches across cycles
        name = _DISP_RE.sub("", name).strip(" -—:")
        d = _DISP_RE.search(line)
        if not d:
            items.append(MinedItem(source=source, name=name))
            continue
        verb = d.group("verb").lower()
        until = d.group("until") or ""
        if verb not in LEGAL:
            items.append(MinedItem(source=source, name=name,
                                   illegal_reason=f"unknown disposition '{verb}'"))
        elif verb == "deferred" and not until:
            # the hiding place: an undated deferral is indistinguishable from abandonment
            items.append(MinedItem(source=source, name=name,
                                   illegal_reason="deferred with NO date"))
        else:
            items.append(MinedItem(source=source, name=name, disposition=verb,
                                   deferred_until=until))
    return items


def is_disposed(item: MinedItem, *, as_of: date) -> bool:
    """True when the item is genuinely finished, or deferred to a date that has NOT yet passed."""
    if item.illegal_reason or not item.disposition:
        return False
    if item.disposition in _TERMINAL:
        return True
    try:
        return date.fromisoformat(item.deferred_until) > as_of
    except ValueError:  # pragma: no cover -- regex already constrains the shape
        return False


def backlog(items: Iterable[MinedItem], *, as_of: date) -> tuple[MinedItem, ...]:
    """Every item still owing a disposition -- untagged, illegally tagged, or expired-deferred."""
    return tuple(i for i in items if not is_disposed(i, as_of=as_of))


def unbacked(
    items: Iterable[MinedItem], *, artifact_backed: Sequence[str]
) -> tuple[MinedItem, ...]:
    """Items CLAIMING wired/screened that the caller could not corroborate against a real artifact.

    Substring match in both directions: a card name and its artifact rarely agree character for
    character ("Tardis" vs "tardis_l2_backfill"), and a false ACCEPT here is far cheaper than a
    false alarm that trains the reader to ignore the check.
    """
    backed = [b.lower() for b in artifact_backed]
    out = []
    for i in items:
        if i.disposition not in _CLAIMS_ARTIFACT:
            continue
        n = i.name.lower()
        if not any(b in n or n in b for b in backed):
            out.append(i)
    return tuple(out)


class ConversionReport(BaseModel):
    """The §33 cycle block -- filled from artifacts, never from a narrative."""

    model_config = ConfigDict(frozen=True)

    n_items: int
    n_wired: int
    n_screened: int
    n_killed: int
    n_deferred: int
    n_backlog: int
    n_illegal: int
    n_unbacked: int
    backlog_names: tuple[str, ...]
    illegal_names: tuple[str, ...]
    unbacked_names: tuple[str, ...]
    suspend_mining: bool
    verdict: str


def conversion_report(
    items: Sequence[MinedItem],
    *,
    as_of: date,
    artifact_backed: Sequence[str] = (),
    max_shown: int = 8,
) -> ConversionReport:
    """Build the §33 report and decide whether mining is SUSPENDED this cycle.

    Suspension is flow control, not punishment: an organ producing faster than the desk converts
    is not producing value, it is producing debt. Mining resumes the instant the backlog clears.
    An UNBACKED conversion claim suspends too -- otherwise the cheapest way to clear a backlog is
    to type the word "wired", which would make the whole law self-defeating.
    """
    bl = backlog(items, as_of=as_of)
    illegal = tuple(i for i in items if i.illegal_reason)
    ub = unbacked(items, artifact_backed=artifact_backed)
    # An EXPIRED deferral is backlog, not a deferral -- counting it in both places would let a
    # rotting item read as handled at a glance, which is the exact failure this law exists to stop.
    counts = {v: sum(1 for i in items if i.disposition == v and is_disposed(i, as_of=as_of))
              for v in LEGAL}
    suspend = bool(bl) or bool(ub)

    if not items:
        verdict = "no carded finds parsed -- nothing owed"
    elif suspend:
        verdict = (
            f"MINING SUSPENDED -- {len(bl)} item(s) owe a disposition, "
            f"{len(ub)} claim conversion with NO backing artifact. Reassign the ENTIRE dig slot "
            "to conversion; catalogue nothing new until the backlog clears."
        )
    else:
        verdict = f"backlog clear -- all {len(items)} carded find(s) disposed; mining authorised"

    return ConversionReport(
        n_items=len(items),
        n_wired=counts["wired"], n_screened=counts["screened"],
        n_killed=counts["killed"], n_deferred=counts["deferred"],
        n_backlog=len(bl), n_illegal=len(illegal), n_unbacked=len(ub),
        backlog_names=tuple(i.name for i in bl[:max_shown]),
        illegal_names=tuple(f"{i.name} ({i.illegal_reason})" for i in illegal[:max_shown]),
        unbacked_names=tuple(i.name for i in ub[:max_shown]),
        suspend_mining=suspend, verdict=verdict,
    )

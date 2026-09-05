"""§33 MINED-TO-WIRED law -- zero research inventory, and a closed loop back into generation.

Mined intelligence is INVENTORY, and un-converted inventory is WASTE that depreciates. A finding
that is catalogued and never wired has produced NEGATIVE value: it consumed a cycle, it inflates
the desk's capability inventory, and it makes every downstream audit read the desk as richer than
it is (the map-vs-territory failure this audit family exists to catch). Mining is not the product
-- CONVERSION is. A perfect dig with zero conversions is a FAILED cycle.

This module is the machine-checkable half of §33. It does NOT do conversions (nothing automates
that -- it is irreducibly research work); it makes the backlog impossible to not see, prices it,
and feeds the outcome back into what gets mined next. §31 only started working when a daily check
with a 48h escalation stood behind it; this is the same shape, in four layers:

  1. DISPOSITION (stock)   -- every carded find owes exactly one disposition; silence is a defect.
  2. QUALITY               -- a disposition is not automatically a conversion. `killed` must be
                              backed by a real graveyard entry, so "kill everything" stops being
                              the cheapest legal way to unblock mining.
  3. VALUE (weighted)      -- a Tier-1 defect-closer outranks a Tier-4 operator, so the gate
                              cannot be cleared by converting only the easy tail.
  4. FLOW + FEEDBACK       -- conversion LATENCY and per-class conversion RATES are tracked over
                              time, and the rates become priors that steer future generation.
                              A gate that only blocks is a fence; a gate that reweights is a
                              control system, and the second one is what "maximum utilisation"
                              actually means.

DISPOSITION CONTRACT -- written inline in the dig-output doc as ``[§33: <disposition>]`` on the
item's OWN line (a blanket tag atop a document launders nothing). Four legal values, no fifth:

  wired            -- code exists AND executed AND wrote a real artifact
  screened         -- a Stage-A screen RAN; result in research_memory, --axis tagged
  killed           -- a graveyard entry carrying the MECHANISM of death (never "low priority")
  deferred(DATE)   -- a NAMED blocker and an ISO date. UNDATED DEFERRAL IS ILLEGAL -- it is the
                      hiding place every rotting backlog uses, so it is parsed and rejected.

An optional ``tier:N`` component overrides the inferred tier:
``[§33: deferred(2026-09-01) tier:1]``.

Three anti-gaming rules are structural, not advisory:

  EXPIRY   -- a deferral stops counting the moment its date passes. A promise with a clock, not a
              filing cabinet.
  NO SELF-GRADING -- wired/screened/killed are CLAIMS about artifacts. The caller passes what it
              could corroborate on disk; anything else is UNBACKED. An organ does not grade its
              own homework (same artifact-only credit rule as ``max_audit._converted_axes``).
  NO CHEAP EXIT -- because `killed` is artifact-checked against the graveyard, mass-killing the
              backlog costs strictly more than converting it. The escape hatch is closed by
              construction rather than by asking nicely.
"""

from __future__ import annotations

import json
import re
import statistics
from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

#: The id is captured separately so it never lands in ``name`` -- a name of "1. Upbit" would fail
#: to match the artifact "upbit_krw_btc_1m" in either direction and report a real conversion as
#: unbacked. Matches ``source_backlog``'s card_id/name split.
#: Deliberately NOT bold bullets: source cards carry ``- **Provenance**:`` / ``- **Queries used**:``
#: metadata fields, and treating those as finds made the check fire 92/92 on its first real run.
#: A check that flags everything is ignored, so the id-numbered card is the one unambiguous unit.
#: A card heading, INCLUDING a merged one. `### 13-14.` (with any dash a writer may type) is one
#: card covering a range, and requiring a bare `(\d+)\.` matched it against nothing: the heading
#: produced no row, so the card was never IN the population any fence iterates, and its absence was
#: byte-identical to its non-existence for every reader (L1.60). That is the silent-attrition shape
#: arriving through a regex rather than through an `except: continue`.
#:
#: THE ID IS THE FIRST NUMBER IN THE RANGE. A merged card is one entry with one identity, and the
#: range is part of its heading rather than part of its name -- so the trailing `-14` is consumed
#: here and the card's name starts where the writer thought it did.
_ITEM_RE = re.compile(r"^### (?P<cid>\d+)(?:[-\u2013\u2014]\d+)?\.\s+(?P<card>.+?)\s*$", re.MULTILINE)
#: The inline disposition tag. Tolerant of "S33"/"section 33" so an ASCII-only writer still counts.
_DISP_RE = re.compile(
    r"\[(?:§|S|section\s*)33:\s*(?P<verb>[a-z-]+)\s*"
    r"(?:\(\s*(?P<until>[0-9]{4}-[0-9]{2}-[0-9]{2})\s*\))?"
    r"(?:[\s,]*tier\s*:\s*(?P<tier>[1-4]))?"
    r"(?:\s*(?:->|@)\s*(?P<art>[^\]]+?))?\s*\]",
    re.IGNORECASE,
)

#: One appended snapshot row: heterogeneous by nature (float ts + list of item dicts).
LedgerRow = Mapping[str, Any]

LEGAL = ("wired", "screened", "killed", "deferred")
#: Terminal dispositions -- the item is finished and never re-enters the backlog.
_TERMINAL = ("wired", "screened", "killed")
#: Every terminal disposition asserts an artifact exists, and is therefore corroborated. `killed`
#: is included ON PURPOSE: it is what closes the mass-graveyard escape hatch.
_CLAIMS_ARTIFACT = _TERMINAL

#: Value weights. A Tier-1 defect-closer stops ongoing bleed and is worth many operators.
TIER_WEIGHT: Mapping[int, int] = {1: 8, 2: 4, 3: 2, 4: 1}

_T1 = ("ground truth", "ground-truth", "diff-verify", "diff verify", "fence", "unblock",
       "blocker", "vendor-replacement", "defect", "backfill")
_T4 = ("operator", "lexicon", "diaspora", "search key", "query", "printpage", "tree-walk")
_T2 = ("prior", "mechanism", "premium", "carry", "funding", "basis", "regime")


def infer_tier(name: str, *, ingested_axes: Sequence[str] = ()) -> int:
    """Best-effort conversion tier (1 = highest ROI). An explicit ``tier:N`` tag always wins.

    Heuristic and deliberately coarse -- its job is to stop a Tier-1 defect-closer being buried
    under cheap Tier-4 wins, not to be a taxonomy. TIER 1 defect-closers (make a permanently-firing
    gate satisfiable) outrank everything because they stop ongoing bleed rather than adding
    capability; TIER 2 is a mechanism prior on an axis ALREADY ingested (pure §31 work on data
    already paid for); TIER 3 a new surface; TIER 4 operators/lexicons/diaspora.
    """
    n = name.lower()
    if any(k in n for k in _T1):
        return 1
    if any(a.lower() in n for a in ingested_axes if a) or any(k in n for k in _T2):
        return 2
    if any(k in n for k in _T4):
        return 4
    return 3


class MinedItem(BaseModel):
    """One carded find plus whatever disposition was written against it."""

    model_config = ConfigDict(frozen=True)

    source: str
    name: str
    disposition: str = ""  # "" = none written == UNDISPOSED (silence is a defect)
    deferred_until: str = ""
    illegal_reason: str = ""
    tier: int = 3
    artifact: str = ""   # explicit repo-relative path from ``-> path`` -- exact, not fuzzy

    @property
    def weight(self) -> int:
        return TIER_WEIGHT.get(self.tier, 1)


def parse_dispositions(
    text: str, *, source: str, ingested_axes: Sequence[str] = ()
) -> list[MinedItem]:
    """Extract every carded find in ``text`` and the disposition written on its own line."""
    items: list[MinedItem] = []
    for line in text.splitlines():
        m = _ITEM_RE.match(line)
        if not m:
            continue
        name = _DISP_RE.sub("", m.group("card")).strip(" -—:")
        d = _DISP_RE.search(line)
        tier = int(d.group("tier")) if (d and d.group("tier")) else infer_tier(
            name, ingested_axes=ingested_axes)
        if not d:
            items.append(MinedItem(source=source, name=name, tier=tier))
            continue
        verb, until = d.group("verb").lower(), (d.group("until") or "")
        art = (d.group("art") or "").strip()
        if verb not in LEGAL:
            items.append(MinedItem(source=source, name=name, tier=tier, artifact=art,
                                   illegal_reason=f"unknown disposition '{verb}'"))
        elif verb == "deferred" and not until:
            # the hiding place: an undated deferral is indistinguishable from abandonment
            items.append(MinedItem(source=source, name=name, tier=tier, artifact=art,
                                   illegal_reason="deferred with NO date"))
        else:
            items.append(MinedItem(source=source, name=name, tier=tier, artifact=art,
                                   disposition=verb, deferred_until=until))
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


#: ``path`` optionally followed by a backtick-quoted anchor naming WHICH entry inside it.
_ARTIFACT_RE = re.compile(r"^(?P<path>\S+)(?:\s+`(?P<anchor>[^`]+)`)?\s*$")


def _split_anchor(artifact: str) -> tuple[str, str]:
    """Split ``path `anchor``` into the file assertion and the entry assertion.

    THE PARSER USED TO SWALLOW THE ANCHOR INTO THE FILENAME, so a card citing its evidence MORE
    precisely scored WORSE than one naming a bare path. Measured 2026-08-01: the bitFlyer kill
    wrote ``-> docs/graveyard.md `jp_bitflyer_direct_recording```, which parsed as a single
    47-character "path" that can never exist, so the claim read as unbacked permanently and no
    amount of doing the actual work could ever clear it. A convention that punishes precision
    trains everyone back to the vaguest form the checker still accepts.

    Returns (path, anchor); anchor is "" when none was given, which preserves the old behaviour
    for every bare-path card.
    """
    s = artifact.strip()
    m = _ARTIFACT_RE.match(s)
    if not m:
        return s, ""
    return m.group("path"), (m.group("anchor") or "").strip()


def _anchor_tokens(anchor: str) -> tuple[str, ...]:
    """THE THIRD COSTUME (2026-08-12), and `_readings` below predicted it in its own docstring:
    "a per-instance fix buys one cycle; the rule has to generalise or it returns in a third
    costume." It did. The parser was taught backticked anchors, then bare anchors -- and the
    CONTAINS assertion downstream stayed a single verbatim substring test, so a card naming TWO
    entries was checked for a string that never existed anywhere.

    MEASURED, and it was the dangerous direction. The J-Quants kill card cites
    `data/data_universe_map.json` `100-jquants-api` + `101-jpx-investor-type-free`. Both keys are
    in that file; the compound literal "`100-jquants-api` + `101-jpx-investor-type-free`" is not,
    so a card whose work was genuinely DONE read as a fabricated claim. A false "unbacked" is worse
    than a false pass here, because the defect's own prescribed remedy is "produce the artifact or
    DOWNGRADE THE CLAIM" -- pointed at a true claim, that instructs a reader to either redo
    finished work or retract something correct.

    A CONJUNCTION, WHICH IS STRICTLY STRONGER, NEVER A DISCOUNT. Naming two entries asserts BOTH
    exist and every one must appear; a single anchor keeps the exact behaviour it had. There is no
    input on which this credits a card the old test rejected for a real absence -- it only stops
    reading "A and B" as one nonexistent string. The laundering guard `_readings` names is intact:
    an anchor is still an EXTRA assertion on top of exists / non-empty / postdates-the-find.

    MISSING TOKENS ARE NAMED INDIVIDUALLY, per this module's own "a count is not a diagnosis"
    rule: a half-done conversion now says WHICH half is absent instead of quoting the whole
    citation back at the reader.
    """
    toks = tuple(t.strip() for t in re.findall(r"`([^`]+)`", anchor) if t.strip())
    return toks or (anchor,)


def _readings(artifact: str) -> tuple[tuple[str, str], ...]:
    """Every defensible (path, anchor) reading of a citation, STRONGEST FIRST.

    THE SAME BUG, ONE COSTUME LATER (2026-08-05). The backtick fix taught the parser exactly ONE
    precise form and left every other attempt at precision scoring WORSE than vagueness. Three
    JP/BR cards wrote the anchor BARE -- `docs/research/prospector_coverage.md JP-s1` -- which
    matches neither branch, so the whole 47-character string became a "path" that can never exist
    and the claims read as unbacked permanently, exactly as the backtick cards had. Per the
    section-37 rule, a per-instance fix buys one cycle; the rule has to generalise or it returns
    in a third costume.

    PURE ON PURPOSE. An earlier draft resolved the filesystem in here and got it wrong in a way
    worth recording: this function has no `root`, so it tested paths against the process CWD while
    every caller resolves them against `base`. A parser that silently disagrees with its caller
    about which file it is talking about is a worse defect than the one being fixed. Resolution
    belongs where `base` is known; this returns candidates and judges nothing.

    SAFE BY CONSTRUCTION, and the ORDER is the whole argument: the literal reading is offered
    first, so a real path that happens to contain a space can never be reinterpreted. The bare
    reading is only ever reached when the literal one does not resolve, and every assertion still
    applies to whatever it produces -- exists, non-empty, POSTDATES the find, and CONTAINS the
    anchor. It can only convert "unbacked, reason unknown" into a fully-checked claim; it cannot
    credit anything the stricter reading rejected. The three cards that motivated it still fail,
    because `JP-s1` appears nowhere in the file they name.
    """
    path, anchor = _split_anchor(artifact)
    if anchor:                                   # explicit backtick form -- nothing to guess
        return ((path, anchor),)
    head, _, tail = artifact.strip().partition(" ")
    if tail.strip():
        return ((path, ""), (head, tail.strip()))
    return ((path, ""),)


def unbacked(
    items: Iterable[MinedItem],
    *,
    backing: Mapping[str, Sequence[str]],
    root: Path | None = None,
    first_seen: Mapping[str, float] | None = None,
) -> tuple[MinedItem, ...]:
    """Terminal claims that could not be corroborated by a real artifact.

    TWO MODES, and the strong one is preferred:

    EXACT (``[§33: wired -> data/upbit_1m.jsonl]``) -- the named path must EXIST and be NON-EMPTY.
    Authoritative: a rename, a deletion, or an empty stub file all fail loudly. This is the mode
    the desk should converge on, because it names the evidence instead of hinting at it.

    FUZZY (no path given) -- substring match in both directions against ``backing`` (wired/screened
    from collector output and research memory; killed from the graveyard). Kept only for backward
    compatibility with cards written before the arrow syntax: a card name and its artifact rarely
    agree character for character ("Tardis" vs "tardis_l2_backfill"). It is genuinely weaker -- a
    rename silently breaks credit and a coincidental substring silently grants it -- so the report
    counts how many claims still rely on it, making the drift toward EXACT visible and pressurable.
    """
    return tuple(i for i, _ in unbacked_reasons(items, backing=backing, root=root,
                                                first_seen=first_seen))


def backing_reason(
    item: MinedItem,
    *,
    backing: Mapping[str, Sequence[str]],
    root: Path | None = None,
    first_seen: Mapping[str, float] | None = None,
) -> str:
    """WHY this claim could not be corroborated -- "" when it can.

    A COUNT IS NOT A DIAGNOSIS, AND THESE TWO NEED OPPOSITE ACTIONS. `unbacked` reported a bare
    tally, so a card whose citation was mis-typed and a card whose claim was simply untrue arrived
    at the reader as one number. The first is fixed by correcting a string; the second must NEVER be
    fixed by correcting a string -- that is laundering, and section 33 credits artifacts on disk
    precisely to stop it. Measured 2026-08-05: 3 cards read as "no backing artifact", which looked
    like three fabricated claims; two were malformed citations AND mis-dispositioned, and one was a
    card whose own grade said "catalogued, NOT screened". Reporting the reason makes the difference
    visible instead of leaving it to whoever picks the item up.
    """
    base = root or Path()
    if item.disposition not in _CLAIMS_ARTIFACT:
        return ""
    if item.artifact:
        # Readings are ordered strongest-first; the FIRST one that resolves to a real file is the
        # one judged. Its verdict is final -- a later reading may not rescue a claim whose named
        # file exists but fails a check, or "anchor absent" would silently downgrade to a bare path.
        why = ""
        for path_s, anchor in _readings(item.artifact):
            p = base / path_s
            try:
                if not p.exists():
                    why = why or (f"path-not-found: {path_s!r} does not exist. If you meant to "
                                  "name an entry INSIDE a file, the checked form is: path `anchor`")
                    continue
                if not p.is_file():
                    return f"path-not-a-file: {path_s!r} is a directory"
                if p.stat().st_size == 0:
                    return f"path-empty: {path_s!r} exists but is 0 bytes"
                # AN ANCHOR IS AN EXTRA ASSERTION, NEVER A DISCOUNT. Naming WHICH entry is strictly
                # better evidence than naming the file -- a 388-line graveyard is non-empty no
                # matter what you failed to write in it -- so the anchor must APPEAR in the file.
                if anchor:
                    blob = p.read_text("utf-8", errors="ignore").lower()
                    missing = [t for t in _anchor_tokens(anchor) if t.lower() not in blob]
                    if missing:
                        return (f"anchor-absent: {path_s!r} does not contain "
                                + " + ".join(repr(t) for t in missing))
                # ...and it must POSTDATE the find. Exact was not enough on its own:
                # `-> pyproject.toml` named a real non-empty file and was credited, so any
                # pre-existing file in the repo was a valid receipt for any claim. Doing the actual
                # work satisfies this for free -- including a graveyard entry, which touches
                # graveyard.md.
                if (first_seen and stable_key(item.name) in first_seen
                        and p.stat().st_mtime <= first_seen[stable_key(item.name)]):
                    return (f"stale-evidence: {path_s!r} has not been modified since before this "
                            "find was first carded, so it cannot be evidence OF it")
            except OSError as exc:
                return f"unreadable: {path_s!r} ({type(exc).__name__})"
            return ""
        return why
    n = item.name.lower()
    cands = [b.lower() for b in backing.get(item.disposition, ()) if b]
    if not any(b in n or n in b for b in cands):
        return ("no-artifact-named: no path was cited and no fuzzy name match was found. Name the "
                "evidence explicitly: -> path `anchor`")
    return ""


def unbacked_reasons(
    items: Iterable[MinedItem],
    *,
    backing: Mapping[str, Sequence[str]],
    root: Path | None = None,
    first_seen: Mapping[str, float] | None = None,
) -> tuple[tuple[MinedItem, str], ...]:
    """Every uncorroborated terminal claim paired with the reason it failed."""
    out = []
    for i in items:
        why = backing_reason(i, backing=backing, root=root, first_seen=first_seen)
        if why:
            out.append((i, why))
    return tuple(out)


def fuzzy_credited(items: Iterable[MinedItem]) -> tuple[MinedItem, ...]:
    """Terminal claims relying on NAME MATCHING rather than a named artifact path.

    Not a defect on its own -- it is the weaker evidence standard, and measuring it is how the
    desk ratchets from "roughly corroborated" to "this exact file, non-empty, or it did not
    happen" without a flag day.
    """
    return tuple(i for i in items if i.disposition in _CLAIMS_ARTIFACT and not i.artifact)


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
    n_fuzzy_credited: int
    weighted_backlog: int
    top_tier_owing: int          # 1..4; 0 when nothing is owed
    kill_share: float            # killed / terminal -- a spike means the escape hatch is in use
    priority_inversion: bool     # a Tier-1/2 item owes while cheaper tiers were converted
    backlog_names: tuple[str, ...]
    illegal_names: tuple[str, ...]
    unbacked_names: tuple[str, ...]
    suspend_mining: bool
    verdict: str


#: Above this share of terminal dispositions being `killed`, the backlog is being cleared by
#: graveyard rather than by conversion. Not proof of gaming -- a genuinely bad batch happens --
#: but it is the signature, and it must be looked at rather than pass silently.
KILL_SHARE_BAR = 0.60


def conversion_report(
    items: Sequence[MinedItem],
    *,
    as_of: date,
    backing: Mapping[str, Sequence[str]] | None = None,
    root: Path | None = None,
    first_seen: Mapping[str, float] | None = None,
    max_shown: int = 8,
) -> ConversionReport:
    """Build the §33 report and decide whether mining is SUSPENDED this cycle.

    Suspension is flow control, not punishment: an organ producing faster than the desk converts
    is not producing value, it is producing debt. Mining resumes the instant the backlog clears.
    An UNBACKED claim suspends too -- otherwise the cheapest way to clear a backlog is to type the
    word "wired", which would make the whole law self-defeating.
    """
    backing = backing or {}
    bl = backlog(items, as_of=as_of)
    illegal = tuple(i for i in items if i.illegal_reason)
    ub_why = unbacked_reasons(items, backing=backing, root=root, first_seen=first_seen)
    ub = tuple(i for i, _ in ub_why)
    fuzzy = fuzzy_credited(items)
    counts = {v: sum(1 for i in items if i.disposition == v and is_disposed(i, as_of=as_of))
              for v in LEGAL}
    # An EXPIRED deferral is backlog, not a deferral -- counting it in both places would let a
    # rotting item read as handled at a glance, the exact failure this law exists to stop.
    n_terminal = sum(counts[v] for v in _TERMINAL)
    kill_share = (counts["killed"] / n_terminal) if n_terminal else 0.0
    weighted = sum(i.weight for i in bl)
    top_tier = min((i.tier for i in bl), default=0)
    # Priority inversion: something expensive still owes while cheaper work was finished. This is
    # the enforceable form of "work the backlog highest-ROI first" -- the doctrine states the
    # order, and without this the order is unenforced prose.
    converted_tiers = [i.tier for i in items if is_disposed(i, as_of=as_of)
                       and i.disposition in _TERMINAL]
    inversion = bool(bl) and top_tier <= 2 and any(t > top_tier for t in converted_tiers)
    suspend = bool(bl) or bool(ub)

    if not items:
        verdict = "no carded finds parsed -- nothing owed"
    elif suspend:
        verdict = (
            f"CONVERSION FIRST -- {len(bl)} item(s) owe a disposition (weighted {weighted}, "
            f"highest tier owing T{top_tier or '-'}), {len(ub)} claim conversion with NO backing "
            "artifact. Spend this run's FIRST effort disposing of them, highest tier first "
            "(wired/screened/killed-with-mechanism/deferred-with-a-date), THEN CONTINUE MINING "
            "AND EXHAUSTING NEW GROUND IN THIS SAME RUN. Mining is never throttled, paused, or "
            "reduced -- acquisition keeps growing while extraction scales up to meet it."
        )
    else:
        verdict = f"backlog clear -- all {len(items)} carded find(s) disposed; mining authorised"

    return ConversionReport(
        n_items=len(items),
        n_wired=counts["wired"], n_screened=counts["screened"],
        n_killed=counts["killed"], n_deferred=counts["deferred"],
        n_backlog=len(bl), n_illegal=len(illegal), n_unbacked=len(ub),
        n_fuzzy_credited=len(fuzzy),
        weighted_backlog=weighted, top_tier_owing=top_tier,
        kill_share=round(kill_share, 3), priority_inversion=inversion,
        backlog_names=tuple(f"T{i.tier} {i.name}" for i in bl[:max_shown]),
        illegal_names=tuple(f"{i.name} ({i.illegal_reason})" for i in illegal[:max_shown]),
        # THE REASON TRAVELS WITH THE NAME. A bare tally cannot distinguish a mis-typed citation
        # (fix the string) from an untrue claim (never fix the string -- that is laundering), and
        # the reader is the one who has to choose. Measured 2026-08-05: 3 names looked like 3
        # fabrications; two were malformed AND mis-dispositioned, one was a card whose own grade
        # said "catalogued, NOT screened".
        unbacked_names=tuple(f"{i.name} [{i.disposition}] -- {w}" for i, w in ub_why[:max_shown]),
        suspend_mining=suspend, verdict=verdict,
    )


# --------------------------------------------------------------------------------------------
# FLOW + FEEDBACK -- a stock check says whether inventory exists; only a flow check says whether
# the desk is getting FASTER. And conversion outcomes are worthless if they dead-end in an audit
# report: fed back as per-class priors, they steer what gets mined next.
# --------------------------------------------------------------------------------------------

def append_snapshot(path: Path, items: Sequence[MinedItem], *, now: datetime | None = None,
                    carded: int | None = None) -> None:
    """Append one line recording every item's disposition as of now (jsonl, one line per run).

    First-seen and converted-at are DERIVED from consecutive snapshots rather than demanded from
    the miners: a timestamp a human has to remember to write is a timestamp that goes missing.

    ``carded`` is the TOTAL number of cards standing in the dig docs, which is a different number
    from ``len(items)``: items are the cards still OWING a disposition, so a card that gets
    resolved leaves items and stays in carded. The mining-volume ratchet must read this one --
    see the note in max_audit.check_mining_nonregression for what went wrong when it did not.
    """
    ts = (now or datetime.now(UTC)).timestamp()
    # "u" (deferred_until) is retained because flow_stats needs it: dropping it at snapshot time
    # made every DATED deferral age as "owing" -- mine-flow-rotting fired on the Upbit card at
    # 17d while the card carried a legal deferred(2026-08-15) the parser had understood and this
    # writer then threw away (the flag-computed-and-dropped class, L1.47).
    row = {"ts": ts, "items": [
        {"n": i.name, "s": i.source, "d": i.disposition, "t": i.tier,
         **({"u": i.deferred_until} if i.deferred_until else {})}
        for i in items]}
    if carded is not None:
        row["carded"] = int(carded)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def load_ledger(path: Path) -> list[dict[str, Any]]:
    """Read the snapshot ledger, skipping any corrupt line rather than losing the whole history."""
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text("utf-8", errors="ignore").splitlines():
        if not line.strip():
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(r, dict) and "ts" in r and isinstance(r.get("items"), list):
            rows.append(r)
    return sorted(rows, key=lambda r: float(r["ts"]))


class FlowStats(BaseModel):
    """Conversion THROUGHPUT -- the stock check cannot tell 30-day conversion from 2-day."""

    model_config = ConfigDict(frozen=True)

    n_snapshots: int
    median_latency_days: float   # find -> terminal disposition; -1 when nothing has converted yet
    p90_latency_days: float
    oldest_owing_days: float
    oldest_owing_name: str
    n_converted: int
    latency_worsening: bool      # recent half slower than the earlier half


def flow_stats(
    ledger: Sequence[LedgerRow], *, now: datetime | None = None
) -> FlowStats:
    """Derive find->conversion latency and the age of the oldest still-owing item."""
    ts_now = (now or datetime.now(UTC)).timestamp()
    # KEYED ON stable_key, NOT THE RAW NAME (2026-08-12). A re-grade renames the card, and on
    # raw names the old name became an immortal owing ghost: first_seen kept it, no snapshot
    # could ever convert or defer it, and mine-flow-rotting fired forever on a find whose
    # CURRENT card was already killed with an artifact (bitFlyer, killed 08-04, "owing 17d").
    # The identity fix landed for vanished/stale-evidence on 08-11 and this function was the
    # one reader still on raw names.
    first_seen: dict[str, float] = {}
    converted_at: dict[str, float] = {}
    deferred_until: dict[str, str] = {}
    display: dict[str, str] = {}
    for row in ledger:
        ts = float(row["ts"])
        for it in row["items"]:
            name = str(it.get("n", ""))
            if not name:
                continue
            key = stable_key(name)
            display[key] = name          # latest sighting carries the find's current card text
            first_seen.setdefault(key, ts)
            if it.get("d") in _TERMINAL and key not in converted_at:
                converted_at[key] = ts
            # LATEST snapshot wins: a re-dated deferral supersedes, and a card that stops being
            # deferred (tag edited away) drops back into owing.
            if it.get("d") == "deferred":
                deferred_until[key] = str(it.get("u", ""))
            elif key in deferred_until:
                del deferred_until[key]
    lat = sorted((converted_at[n] - first_seen[n]) / 86400.0 for n in converted_at)

    def _deferral_active(name: str) -> bool:
        """A DATED, UNEXPIRED deferral is a disposition (§33): it silences the owing clock but
        never resets it -- on expiry the item re-enters owing at its ORIGINAL first_seen age, so
        deferral buys silence, not youth. Undated (old-format rows dropped "u") or expired
        deferrals keep aging: the conservative direction for both."""
        until = deferred_until.get(name, "")
        if not until:
            return False
        try:
            return date.fromisoformat(until) > datetime.fromtimestamp(ts_now, UTC).date()
        except ValueError:
            return False

    owing = {n: t for n, t in first_seen.items()
             if n not in converted_at and not _deferral_active(n)}
    oldest_name, oldest_days = "", 0.0
    if owing:
        oldest_key = min(owing, key=lambda n: owing[n])
        oldest_name = display.get(oldest_key, oldest_key)
        oldest_days = (ts_now - owing[oldest_key]) / 86400.0
    worsening = False
    if len(lat) >= 6:
        # ordered by latency, not time -- compare the halves of the CHRONOLOGICAL series instead
        chrono = [(converted_at[n], (converted_at[n] - first_seen[n]) / 86400.0)
                  for n in converted_at]
        chrono.sort()
        half = len(chrono) // 2
        early = statistics.median(v for _, v in chrono[:half])
        late = statistics.median(v for _, v in chrono[half:])
        worsening = late > early * 1.5
    return FlowStats(
        n_snapshots=len(ledger),
        median_latency_days=round(statistics.median(lat), 2) if lat else -1.0,
        p90_latency_days=round(lat[int(len(lat) * 0.9)], 2) if lat else -1.0,
        oldest_owing_days=round(oldest_days, 2), oldest_owing_name=oldest_name,
        n_converted=len(lat), latency_worsening=worsening,
    )


class ClassPrior(BaseModel):
    """What a SOURCE CLASS has historically been worth -- the signal that steers generation."""

    model_config = ConfigDict(frozen=True)

    source: str
    n_seen: int
    n_converted: int
    conversion_rate: float
    median_latency_days: float


def class_priors(
    ledger: Sequence[LedgerRow], *, min_seen: int = 3
) -> tuple[ClassPrior, ...]:
    """Per-source conversion rate and latency -- the closed loop back into what to mine next.

    Conversion data that dead-ends in an audit report is a fence. Fed back as priors, it becomes a
    control system: a source class converting at 60% earns more of the next cycle than one
    converting at 5%, WITHOUT anyone deciding that by hand. Classes below ``min_seen`` are omitted
    rather than shown at a noisy 0/1 rate -- a thin prior that reweights generation is worse than
    no prior at all.
    """
    seen: dict[str, dict[str, float]] = {}
    first: dict[str, float] = {}
    conv: dict[str, float] = {}
    src_of: dict[str, str] = {}
    for row in ledger:
        ts = float(row["ts"])
        for it in row["items"]:
            name, src = str(it.get("n", "")), str(it.get("s", "?"))
            if not name:
                continue
            src_of.setdefault(name, src)
            first.setdefault(name, ts)
            if it.get("d") in _TERMINAL and name not in conv:
                conv[name] = ts
    for name, src in src_of.items():
        b = seen.setdefault(src, {"n": 0.0, "c": 0.0})
        b["n"] += 1
        if name in conv:
            b["c"] += 1
    out = []
    for src, b in sorted(seen.items()):
        if b["n"] < min_seen:
            continue
        lat = sorted((conv[n] - first[n]) / 86400.0 for n, s in src_of.items()
                     if s == src and n in conv)
        out.append(ClassPrior(
            source=src, n_seen=int(b["n"]), n_converted=int(b["c"]),
            conversion_rate=round(b["c"] / b["n"], 3),
            median_latency_days=round(statistics.median(lat), 2) if lat else -1.0,
        ))
    return tuple(sorted(out, key=lambda p: -p.conversion_rate))


def priors_payload(
    priors: Sequence[ClassPrior], *, now: datetime | None = None
) -> dict[str, Any]:
    """The artifact the diggers read: where the next cycle's effort is worth most, and least."""
    ts = (now or datetime.now(UTC))
    ranked = list(priors)
    return {
        "generated_at": ts.isoformat(),
        "law": "§33.4 -- generation is reweighted BY measured conversion, not by enthusiasm",
        "favour": [p.source for p in ranked[:3]],
        "starve": [p.source for p in ranked[-3:] if p.conversion_rate < 0.25],
        "classes": [p.model_dump() for p in ranked],
    }


# --------------------------------------------------------------------------------------------
# SELF-IMPROVEMENT -- the ratchet. Layers 1-4 make conversion visible, priced, and fed back; none
# of them makes it get BETTER. A standard that never moves is a standard the desk grows into and
# then stops at, which is the no-ceiling axiom's exact failure mode. So the bar is the desk's OWN
# BEST-EVER performance: every record tightens it permanently, and it never loosens. There is no
# "good enough" state -- only "better than the best we have ever done", or a regression defect.
# --------------------------------------------------------------------------------------------

class Ratchet(BaseModel):
    """Best-ever conversion performance. Monotone by construction -- records only ever improve."""

    model_config = ConfigDict(frozen=True)

    best_median_latency_days: float = -1.0   # -1 = no record yet
    best_conversion_rate: float = 0.0
    best_at: str = ""
    n_records: int = 0
    #: Ledger high-water marks. Snapshot count only grows and the earliest ts only moves back;
    #: either going the wrong way proves the evidence base was truncated or rewritten.
    n_snapshots: int = 0
    earliest_ts: float = 0.0


class RatchetVerdict(BaseModel):
    """Whether this cycle set a record, held, or REGRESSED against the desk's own best."""

    model_config = ConfigDict(frozen=True)

    improved: bool
    regressed: bool
    latency_vs_best: float   # multiple of best-ever median latency; -1 when no record yet
    rate_vs_best: float      # current conversion rate minus best-ever
    next_bar_days: float     # the tightened bar the NEXT cycle must beat
    verdict: str


def load_ratchet(path: Path) -> Ratchet:
    """Read the ratchet, degrading to a fresh one rather than losing the check on a corrupt file."""
    try:
        return Ratchet.model_validate_json(path.read_text("utf-8"))
    except Exception:
        return Ratchet()


def update_ratchet(
    ratchet: Ratchet,
    flow: FlowStats,
    *,
    conversion_rate: float,
    regress_mult: float = 1.5,
    ledger: Sequence[LedgerRow] = (),
    now: datetime | None = None,
) -> tuple[Ratchet, RatchetVerdict]:
    """Compare this cycle to the best ever, tighten on a record, and flag regression.

    ONE-WAY: a worse cycle never relaxes the bar -- it produces a defect instead. That asymmetry is
    the whole point. Latency improvements and rate improvements both count, so the desk can advance
    by converting FASTER or by converting MORE, and it is never allowed to trade one away for the
    other silently (both are held against their own records).
    """
    ts = (now or datetime.now(UTC)).isoformat()
    cur_lat, best_lat = flow.median_latency_days, ratchet.best_median_latency_days
    have_lat = cur_lat >= 0.0
    lat_record = have_lat and (best_lat < 0.0 or cur_lat < best_lat)
    rate_record = conversion_rate > ratchet.best_conversion_rate
    improved = bool(lat_record or rate_record)

    lat_vs = (cur_lat / best_lat) if (have_lat and best_lat > 0.0) else -1.0
    # A regression is measured against the RECORD, never against last cycle -- otherwise a slow
    # drift downhill reads as "fine" at every single step.
    regressed = bool(have_lat and best_lat > 0.0 and cur_lat > best_lat * regress_mult)

    new = Ratchet(
        best_median_latency_days=(cur_lat if lat_record else best_lat),
        best_conversion_rate=(conversion_rate if rate_record else ratchet.best_conversion_rate),
        best_at=(ts if improved else ratchet.best_at),
        n_records=ratchet.n_records + (1 if improved else 0),
        # high-water marks only ever ratchet the safe way, so a shrunken ledger stays detectable
        n_snapshots=max(ratchet.n_snapshots, len(ledger)),
        earliest_ts=(min(float(r["ts"]) for r in ledger)
                     if ledger and not ratchet.earliest_ts
                     else ratchet.earliest_ts),
    )
    # the bar the next cycle must beat: the (possibly new) record, tightened by the tolerance
    next_bar = (new.best_median_latency_days * regress_mult
                if new.best_median_latency_days > 0.0 else -1.0)

    if improved:
        bits = []
        if lat_record:
            bits.append(f"latency {cur_lat:.1f}d (prev best {best_lat:.1f}d)")
        if rate_record:
            prev = ratchet.best_conversion_rate
            bits.append(f"rate {conversion_rate:.0%} (prev best {prev:.0%})")
        verdict = "RECORD -- " + "; ".join(bits) + ". Bar tightened; it never loosens."
    elif regressed:
        verdict = (f"REGRESSION -- median latency {cur_lat:.1f}d vs best-ever {best_lat:.1f}d "
                   f"({lat_vs:.1f}x). The desk has been faster than this and must be again.")
    else:
        verdict = (f"held -- {cur_lat:.1f}d vs best {best_lat:.1f}d. Holding is not improving: "
                   "the standing bar is the desk's own record, and it only moves down.")
    return new, RatchetVerdict(
        improved=improved, regressed=regressed,
        latency_vs_best=round(lat_vs, 2),
        rate_vs_best=round(conversion_rate - ratchet.best_conversion_rate, 3),
        next_bar_days=round(next_bar, 2), verdict=verdict,
    )


def feedback_applied(
    ledger: Sequence[LedgerRow], priors: Sequence[ClassPrior], *, lookback: int = 2
) -> tuple[bool, str]:
    """Did generation ACTUALLY reweight toward the high-converting classes, or just get told to?

    The loop is only closed if the advice changes behaviour. Compares which source classes NEW
    items arrived in over the last ``lookback`` snapshots against the priors' favour/starve lists.
    A recommendation nothing acts on is the same failure as a law with no monitor -- so the
    feedback step is itself verified rather than assumed.
    """
    if len(ledger) < lookback + 1 or not priors:
        return True, "insufficient history to judge feedback -- not a defect yet"
    starve = {p.source for p in priors if p.conversion_rate < 0.25}
    if not starve:
        return True, "no starved class -- nothing to reweight away from"
    older = {str(i.get("n", "")) for row in ledger[:-lookback] for i in row["items"]}
    fresh: dict[str, int] = {}
    for row in ledger[-lookback:]:
        for i in row["items"]:
            n = str(i.get("n", ""))
            if n and n not in older:
                fresh[str(i.get("s", "?"))] = fresh.get(str(i.get("s", "?")), 0) + 1
    if not fresh:
        return True, "no new finds in the window -- nothing to judge"
    bad = sum(v for k, v in fresh.items() if k in starve)
    share = bad / sum(fresh.values())
    if share > 0.5:
        return False, (f"{share:.0%} of new finds came from classes measured below a 25% "
                       f"conversion rate ({', '.join(sorted(starve))}) -- the priors were "
                       "published and IGNORED. Generation must follow measured conversion.")
    return True, f"new finds skew away from starved classes ({share:.0%} from them)"


# --------------------------------------------------------------------------------------------
# TAMPER-RESISTANCE -- the lesson of the gate file, generalised. Every remaining bypass in §33 was
# the same shape: state that could be DELETED or FORGED. A card can be deleted from the doc; an
# artifact path can point at a file that has been there for months; the ratchet's "never loosens"
# guarantee lived in a gitignored file one `rm` deep. Enforcement is only as strong as its weakest
# erasable surface, so each of these is closed the same way -- derive it, or put it where deleting
# it is VISIBLE.
# --------------------------------------------------------------------------------------------

#: A card's name is "<find> — grade: <mutable assessment>". The split tolerates em/en dashes and
#: plain hyphens because the docs carry all three.
_GRADE_SPLIT = re.compile(r"\s+[—–-]{1,2}\s*grade\s*:", re.IGNORECASE)  # noqa: RUF001 -- the en dash is a deliberate member of the class: live cards carry em/en/hyphen variants


def stable_key(name: str) -> str:
    """The find's durable identity: the card text BEFORE its grade.

    Grades are DESIGNED to change ("re-graded 2026-07-25" appears in live cards), so an identity
    that includes the grade makes every re-grade a RENAME: the old name fires mine-item-vanished
    while the new name's first_seen resets to the re-grade instant, which turns every artifact
    written before that instant into "stale-evidence". Measured 2026-08-11: one re-graded T3 card
    reported vanished and six same-run conversions reported unbacked, all from this one identity
    choice -- the work was real, the fence's name for it was not stable.
    """
    return _GRADE_SPLIT.split(name, 1)[0].strip()


def first_seen_map(ledger: Sequence[LedgerRow]) -> dict[str, float]:
    """LOWER BOUND on each stable find identity's birth, from the snapshot ledger.

    A find first appearing in snapshot N was born somewhere in the (N-1, N] window -- snapshot
    N's own timestamp is an UPPER bound, and judging evidence against an upper bound fails the
    exact flow section 33 mandates (screen-on-discovery: work and card land in the SAME run, and
    the artifact write naturally precedes the doc write by minutes). So the value recorded is the
    PREVIOUS snapshot's timestamp: an artifact older than that provably predates the find and
    stays stale-evidence; one written inside the discovery window is credited. Items already
    present in the very first snapshot keep that snapshot's timestamp -- with no earlier row
    there is no window to reason about, and loosening the oldest cohort is not this fix's job.
    """
    out: dict[str, float] = {}
    prev_ts = None
    for row in ledger:
        ts = float(row["ts"])
        lower = prev_ts if prev_ts is not None else ts
        for it in row["items"]:
            n = str(it.get("n", ""))
            if n:
                out.setdefault(stable_key(n), lower)
        prev_ts = ts
    return out


def vanished(
    current: Sequence[MinedItem], ledger: Sequence[LedgerRow], *, as_of: date
) -> tuple[str, ...]:
    """Finds that were owed a disposition in the last snapshot and have since DISAPPEARED.

    Deleting the card must not delete the obligation. Without this, the cheapest way to clear the
    backlog is an editor: remove the line, and the item stops being counted entirely. The ledger
    remembers, so a name that was undisposed yesterday and is absent today is an erasure, reported
    immediately and by name rather than surfacing weeks later as a confusing rot warning about an
    item nobody can find.
    """
    if not ledger:
        return ()
    prev = ledger[-1]
    # Keyed on the STABLE identity: a re-graded card is the same find under a new assessment,
    # not an erasure. The display name reported back is the one the last snapshot carried.
    was_owing = {stable_key(n): n for i in prev["items"]
                 if i.get("d") not in _TERMINAL and (n := str(i.get("n", "")))}
    now_present = {stable_key(i.name) for i in current}
    # a terminal disposition in THIS pass is a legitimate exit, not an erasure
    now_done = {stable_key(i.name) for i in current if is_disposed(i, as_of=as_of)}
    return tuple(sorted(was_owing[k] for k in was_owing.keys() - now_present - now_done))


def ledger_regressed(ratchet: Ratchet, ledger: Sequence[LedgerRow], *,
                     local_n_prior: int | None = None) -> tuple[bool, str]:
    """Has the snapshot history been truncated or rewritten since the last recorded state?

    The ledger is the evidence base for latency, priors and the ratchet itself; erasing it resets
    every one of them. Snapshot count only ever grows and the earliest timestamp only ever moves
    BACKWARD (never forward), so either statistic going the wrong way is proof of tampering or of
    data loss -- both of which invalidate the record and must be seen, not silently absorbed.

    THE TWO SIGNALS BELONG TO DIFFERENT SCOPES, which is why `local_n_prior` exists. The snapshot
    COUNT is a property of one machine's ledger -- data/ is gitignored, so a clone's count starts
    at zero and has nothing to do with the count the VPS reached. Comparing a clone against a
    committed count reports "the ledger was truncated" on a machine that has deleted nothing.
    `earliest_ts` is the cross-machine signal and stays on the committed ratchet.

    So the caller passes THIS MACHINE's previously observed count as `local_n_prior`. Absent, the
    count test falls back to the committed figure, preserving the original behaviour for callers
    that have no machine-local state to offer.
    """
    if not ratchet.n_snapshots:
        return False, "no prior record -- nothing to compare"
    n = len(ledger)
    earliest = min((float(r["ts"]) for r in ledger), default=0.0)

    prior_n = ratchet.n_snapshots if local_n_prior is None else local_n_prior
    if n < prior_n:
        return True, (f"snapshot count fell {prior_n} -> {n}: the conversion ledger "
                      "has been truncated or deleted")
    if ratchet.earliest_ts and earliest > ratchet.earliest_ts + 1.0:
        # AMBIGUOUS BY CONSTRUCTION, AND SAID SO RATHER THAN GUESSED.
        #
        # This fires in two situations that the ledger CANNOT distinguish: history genuinely
        # rewritten, and a fresh checkout. data/ is gitignored, so a clone starts an empty ledger
        # and fills it one row per audit invocation -- every row then postdates the recorded
        # earliest, at an unchanged or higher count. Structurally identical to a rewrite that
        # replaced old rows with new ones.
        #
        # A carve-out for "disjoint history" was written, and reverted, because the existing
        # tamper test proved it silenced the real case: `n >= n_snapshots` is true of BOTH, so
        # exempting it would have converted a false positive into a false negative on the only
        # detector of the desk's evidence base being erased. Between the two errors this one is
        # the cheap one -- an accusation that can be checked, rather than a deletion that cannot
        # be noticed.
        #
        # So the verdict stands and the MESSAGE carries the ambiguity, which is what stops a
        # reader (this one included, on 2026-08-02) filing an environment artifact as a desk
        # defect without comparing the timestamps first.
        return True, (
            "the ledger's earliest snapshot moved forward in time: history was rewritten, not "
            f"appended (local earliest {earliest:.0f} vs recorded {ratchet.earliest_ts:.0f}, "
            f"{n} rows vs {ratchet.n_snapshots} recorded). CHECK THE ENVIRONMENT BEFORE THE "
            "CONCLUSION: data/ is gitignored, so a fresh checkout builds its own ledger from "
            "scratch and produces this signature having deleted nothing. On the machine that owns "
            "the recorded history this is tampering; on a clone it is expected. The ledger alone "
            "cannot tell them apart, and pretending otherwise in either direction is worse than "
            "saying so.")
    return False, "ledger intact"


# --------------------------------------------------------------------------------------------
# THE LAW HELD TO ITS OWN STANDARD. Everything above pressures the DESK. Nothing above asks
# whether §33's own machinery is any good -- and a law exempt from the evidence standard it
# enforces is exactly the hypocrisy the NO-CEILING AXIOM forbids ("we are at max" is a claim
# requiring evidence, never a default). Two self-audits close that: the tier weights must be
# shown to track reality, and the law must be shown to have improved conversion at all.
# --------------------------------------------------------------------------------------------

class TierCalibration(BaseModel):
    """Measured behaviour per tier -- are the weights tracking reality or just asserted?"""

    model_config = ConfigDict(frozen=True)

    per_tier: Mapping[int, tuple[int, float, float]]  # tier -> (n, conversion_rate, median_days)
    inverted: bool
    verdict: str


def tier_calibration(
    ledger: Sequence[LedgerRow], *, min_per_tier: int = 4
) -> TierCalibration:
    """Check the TIER WEIGHTS against measured outcomes instead of trusting the heuristic.

    The weighting (T1=8 .. T4=1) is an ASSERTION: it claims Tier-1 finds are the high-ROI ones.
    If in practice Tier-1 items convert less often and slower than Tier-4 items, the weights are
    not merely useless -- they are actively misdirecting effort toward the wrong work while
    reporting that priority is being enforced. This does not silently re-learn the mapping (a
    keyword heuristic quietly rewritten by its own outcomes is unauditable); it DETECTS that the
    mapping is wrong and demands the tiering be corrected, which is the honest version of learning
    when the sample is this thin.
    """
    first: dict[str, float] = {}
    conv: dict[str, float] = {}
    tier_of: dict[str, int] = {}
    for row in ledger:
        ts = float(row["ts"])
        for it in row["items"]:
            n = str(it.get("n", ""))
            if not n:
                continue
            first.setdefault(n, ts)
            tier_of.setdefault(n, int(it.get("t", 3) or 3))
            if it.get("d") in _TERMINAL and n not in conv:
                conv[n] = ts
    per: dict[int, tuple[int, float, float]] = {}
    for tier in (1, 2, 3, 4):
        names = [n for n, t in tier_of.items() if t == tier]
        if not names:
            continue
        done = [n for n in names if n in conv]
        lat = sorted((conv[n] - first[n]) / 86400.0 for n in done)
        per[tier] = (len(names), round(len(done) / len(names), 3),
                     round(statistics.median(lat), 2) if lat else -1.0)

    hi, lo = per.get(1), per.get(4)
    enough = bool(hi and lo and hi[0] >= min_per_tier and lo[0] >= min_per_tier)
    inverted = bool(enough and hi and lo and hi[1] < lo[1])
    if not enough:
        verdict = "insufficient per-tier history to judge the weights -- not a defect yet"
    elif inverted and hi and lo:
        verdict = (f"tier weights INVERTED: T1 converts at {hi[1]:.0%} vs T4 at {lo[1]:.0%}. The "
                   "weighting is steering effort toward work that does not finish.")
    else:
        verdict = "tier weights track measured outcomes"
    return TierCalibration(per_tier=per, inverted=inverted, verdict=verdict)


class LawEffectiveness(BaseModel):
    """Has §33 actually improved conversion, or is it ceremony with good telemetry?"""

    model_config = ConfigDict(frozen=True)

    n_snapshots: int
    early_rate: float
    late_rate: float
    early_latency_days: float
    late_latency_days: float
    improving: bool
    conclusive: bool
    verdict: str
    #: Distinct ITEMS behind each window's rate. The snapshot count says how often the ledger was
    #: written; only this says how much evidence the rate rests on, and they can differ by orders
    #: of magnitude.
    n_early_items: int = 0
    n_late_items: int = 0


#: Distinct items each window needs before the two rates may be COMPARED. Matches
#: libs.doctrine.estimate.MIN_N_FOR_ACTION, and for the same reason: below it a single item
#: flipping moves the rate tens of percentage points, so "flat" and "improving" are the same
#: measurement wearing different labels.
MIN_ITEMS_PER_WINDOW = 5

#: z for calling the change real. One-sided 80%, matching ADMIT_Z -- the cost of investigating a
#: law that turns out fine is one cycle, the cost of never noticing a dead law is unbounded.
_EFFECT_Z = 1.28


def _rate_se(rate: float, n: int) -> float:
    """Binomial standard error, floored so n=1 cannot report perfect precision."""
    if n <= 0:
        return 1.0
    return float(max((rate * (1.0 - rate) / n) ** 0.5, 1.0 / n))


def law_effectiveness(
    ledger: Sequence[LedgerRow], *, min_snapshots: int = 12
) -> LawEffectiveness:
    """Compare the FIRST third of the ledger against the LAST third: is conversion getting better?

    HONEST LIMIT, stated rather than buried: there is no control group and no pre-§33 baseline
    (the ledger begins with the law), so this is a TREND, not a counterfactual -- it cannot prove
    §33 caused an improvement, only that one did or did not happen while §33 was in force. That is
    still the strongest evidence available, and it is strictly better than the alternative the desk
    would otherwise use, which is assuming the law works because it was written carefully. If
    conversion is flat or worse after enough cycles, §33 is ceremony with good telemetry and must
    say so about itself in those words.
    """
    n = len(ledger)
    if n < min_snapshots:
        return LawEffectiveness(
            n_snapshots=n, early_rate=0.0, late_rate=0.0, early_latency_days=-1.0,
            late_latency_days=-1.0, improving=False, conclusive=False,
            verdict=f"{n}/{min_snapshots} snapshots -- too early to judge the law itself")
    third = max(1, n // 3)

    def _window(rows: Sequence[LedgerRow]) -> tuple[float, float, int]:
        first: dict[str, float] = {}
        conv: dict[str, float] = {}
        for row in rows:
            ts = float(row["ts"])
            for it in row["items"]:
                nm = str(it.get("n", ""))
                if not nm:
                    continue
                first.setdefault(nm, ts)
                if it.get("d") in _TERMINAL and nm not in conv:
                    conv[nm] = ts
        rate = (len(conv) / len(first)) if first else 0.0
        lat = sorted((conv[k] - first[k]) / 86400.0 for k in conv)
        return round(rate, 3), (round(statistics.median(lat), 2) if lat else -1.0), len(first)

    e_rate, e_lat, e_n = _window(ledger[:third])
    l_rate, l_lat, l_n = _window(ledger[-third:])

    # THE SNAPSHOT COUNT IS NOT THE SAMPLE SIZE, and conflating them let this function call §33
    # "ceremony with good telemetry" from two items. min_snapshots gates how often the ledger was
    # WRITTEN; the rates rest on how many distinct ITEMS were seen, and the live ledger had 62 of
    # the former and 2 of the latter. Below MIN_ITEMS_PER_WINDOW a single item flipping swings the
    # rate by tens of points, so "flat" and "improving" are the same measurement with different
    # labels -- and this is the organ that enforces the evidence standard on everything else. A
    # law is not exempt from the bar it sets, which cuts both ways: it may not be convicted on
    # evidence too thin to convict anything else.
    if min(e_n, l_n) < MIN_ITEMS_PER_WINDOW:
        return LawEffectiveness(
            n_snapshots=n, early_rate=e_rate, late_rate=l_rate,
            early_latency_days=e_lat, late_latency_days=l_lat,
            n_early_items=e_n, n_late_items=l_n,
            improving=False, conclusive=False,
            verdict=(f"{n} snapshots but only {e_n}/{l_n} distinct items per window (bar "
                     f"{MIN_ITEMS_PER_WINDOW}) -- the rate {e_rate:.0%} -> {l_rate:.0%} rests on "
                     "too few conversions to distinguish a flat law from a working one. Snapshots "
                     "measure how often the ledger was written, never how much evidence it holds."))

    # THE LEVEL CONVICTS WITHOUT A TREND. A law under which NOTHING converts is failing whether or
    # not the rate moved -- 0% to 0% is flat, and flatness is the least interesting thing about it.
    # Requiring a significant DECLINE here would exonerate the worst possible state for being
    # consistently the worst, which is the trap in judging a law only by its derivative.
    if l_rate <= 0.0:
        return LawEffectiveness(
            n_snapshots=n, early_rate=e_rate, late_rate=l_rate,
            early_latency_days=e_lat, late_latency_days=l_lat,
            n_early_items=e_n, n_late_items=l_n,
            improving=False, conclusive=True,
            verdict=(f"conversion rate {e_rate:.0%} -> {l_rate:.0%} over {l_n} items -- NOTHING "
                     "converts under §33. It is ceremony with good telemetry, and no trend "
                     "argument can rescue a rate of zero: either the enforcement is not biting or "
                     "the bottleneck is elsewhere. Find out which."))

    # COMPARED WITH ITS UNCERTAINTY, not with `>`. Two proportions differing by a point are not a
    # trend, and ranking on raw point estimates is precisely what libs/doctrine/estimate.py exists
    # to stop the rest of the desk doing.
    se = (_rate_se(e_rate, e_n) ** 2 + _rate_se(l_rate, l_n) ** 2) ** 0.5
    rate_better = (l_rate - e_rate) > _EFFECT_Z * se
    rate_worse = (e_rate - l_rate) > _EFFECT_Z * se
    faster = l_lat >= 0 and e_lat >= 0 and l_lat < e_lat
    improving = bool(rate_better or (faster and not rate_worse))
    indistinguishable = not rate_better and not rate_worse and not faster
    verdict = (
        f"conversion rate {e_rate:.0%} -> {l_rate:.0%} (n={e_n}/{l_n}, se {se:.0%}), "
        f"median latency {e_lat:.1f}d -> {l_lat:.1f}d"
        + (" -- the law is working" if improving else
           " -- the change is NOT distinguishable from flat at this sample size. That is a finding "
           "about the evidence, not yet a verdict on the law: gather more before concluding either "
           "way." if indistinguishable else
           " -- NO improvement while §33 has been in force. It is ceremony with good telemetry: "
           "either the enforcement is not biting or the bottleneck is elsewhere. Find out which.")
    )
    return LawEffectiveness(
        n_snapshots=n, early_rate=e_rate, late_rate=l_rate,
        early_latency_days=e_lat, late_latency_days=l_lat,
        n_early_items=e_n, n_late_items=l_n,
        improving=improving, conclusive=not indistinguishable, verdict=verdict)

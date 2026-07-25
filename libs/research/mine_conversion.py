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
_ITEM_RE = re.compile(r"^### (?P<cid>\d+)\.\s+(?P<card>.+?)\s*$", re.MULTILINE)
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
    base = root or Path()
    out = []
    for i in items:
        if i.disposition not in _CLAIMS_ARTIFACT:
            continue
        if i.artifact:
            p = base / i.artifact
            try:
                ok = p.is_file() and p.stat().st_size > 0
                # ...and it must POSTDATE the find. Exact was not enough: `-> pyproject.toml`
                # named a real non-empty file and was credited, so any pre-existing file in the
                # repo was a valid receipt for any claim. A file that has not been touched since
                # before the discovery cannot be evidence OF that discovery. Doing the actual
                # work satisfies this for free -- including a graveyard entry, which touches
                # graveyard.md. Skipped when the find has no ledger history yet.
                if ok and first_seen and i.name in first_seen:
                    ok = p.stat().st_mtime > first_seen[i.name]
                if ok:
                    continue
            except OSError:
                pass
            out.append(i)
            continue
        n = i.name.lower()
        cands = [b.lower() for b in backing.get(i.disposition, ()) if b]
        if not any(b in n or n in b for b in cands):
            out.append(i)
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
    ub = unbacked(items, backing=backing, root=root, first_seen=first_seen)
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
            f"MINING SUSPENDED -- {len(bl)} item(s) owe a disposition (weighted {weighted}, "
            f"highest tier owing T{top_tier or '-'}), {len(ub)} claim conversion with NO backing "
            "artifact. Reassign the ENTIRE dig slot to conversion, highest tier first; catalogue "
            "nothing new until the backlog clears."
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
        unbacked_names=tuple(f"{i.name} [{i.disposition}]" for i in ub[:max_shown]),
        suspend_mining=suspend, verdict=verdict,
    )


# --------------------------------------------------------------------------------------------
# FLOW + FEEDBACK -- a stock check says whether inventory exists; only a flow check says whether
# the desk is getting FASTER. And conversion outcomes are worthless if they dead-end in an audit
# report: fed back as per-class priors, they steer what gets mined next.
# --------------------------------------------------------------------------------------------

def append_snapshot(path: Path, items: Sequence[MinedItem], *, now: datetime | None = None) -> None:
    """Append one line recording every item's disposition as of now (jsonl, one line per run).

    First-seen and converted-at are DERIVED from consecutive snapshots rather than demanded from
    the miners: a timestamp a human has to remember to write is a timestamp that goes missing.
    """
    ts = (now or datetime.now(UTC)).timestamp()
    row = {"ts": ts, "items": [{"n": i.name, "s": i.source, "d": i.disposition, "t": i.tier}
                               for i in items]}
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
    first_seen: dict[str, float] = {}
    converted_at: dict[str, float] = {}
    for row in ledger:
        ts = float(row["ts"])
        for it in row["items"]:
            name = str(it.get("n", ""))
            if not name:
                continue
            first_seen.setdefault(name, ts)
            if it.get("d") in _TERMINAL and name not in converted_at:
                converted_at[name] = ts
    lat = sorted((converted_at[n] - first_seen[n]) / 86400.0 for n in converted_at)
    owing = {n: t for n, t in first_seen.items() if n not in converted_at}
    oldest_name, oldest_days = "", 0.0
    if owing:
        oldest_name = min(owing, key=lambda n: owing[n])
        oldest_days = (ts_now - owing[oldest_name]) / 86400.0
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

def first_seen_map(ledger: Sequence[LedgerRow]) -> dict[str, float]:
    """Earliest snapshot timestamp per item name -- when the desk first knew about the find."""
    out: dict[str, float] = {}
    for row in ledger:
        ts = float(row["ts"])
        for it in row["items"]:
            n = str(it.get("n", ""))
            if n:
                out.setdefault(n, ts)
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
    was_owing = {str(i.get("n", "")) for i in prev["items"]
                 if i.get("d") not in _TERMINAL and str(i.get("n", ""))}
    now_present = {i.name for i in current}
    # a terminal disposition in THIS pass is a legitimate exit, not an erasure
    now_done = {i.name for i in current if is_disposed(i, as_of=as_of)}
    return tuple(sorted(was_owing - now_present - now_done))


def ledger_regressed(ratchet: Ratchet, ledger: Sequence[LedgerRow]) -> tuple[bool, str]:
    """Has the snapshot history been truncated or rewritten since the last recorded state?

    The ledger is the evidence base for latency, priors and the ratchet itself; erasing it resets
    every one of them. Snapshot count only ever grows and the earliest timestamp only ever moves
    BACKWARD (never forward), so either statistic going the wrong way is proof of tampering or of
    data loss -- both of which invalidate the record and must be seen, not silently absorbed.
    """
    if not ratchet.n_snapshots:
        return False, "no prior record -- nothing to compare"
    n = len(ledger)
    earliest = min((float(r["ts"]) for r in ledger), default=0.0)
    if n < ratchet.n_snapshots:
        return True, (f"snapshot count fell {ratchet.n_snapshots} -> {n}: the conversion ledger "
                      "has been truncated or deleted")
    if ratchet.earliest_ts and earliest > ratchet.earliest_ts + 1.0:
        return True, ("the ledger's earliest snapshot moved forward in time: history was "
                      "rewritten, not appended")
    return False, "ledger intact"

"""CONVERSION, ACROSS EVERY FAMILY AT ONCE -- and the fences that stop the pressure corrupting it.

PRINCIPAL ORDER (2026-08-01): maximise every part of conversion, aggressively and exhaustively,
across defects, data and recommendations alike -- *"its one big family to always maximise"* --
*"without letting the factor its trying to utilise or convert get reduced or affected cuz of it"*.

That second clause is the hard half and it is what most of this file is about.

============================== WHY ONE FAMILY, MEASURED TOGETHER ==============================

This desk already has a conversion law -- §33 in `mine_conversion`, with dispositions, quality
backing, value weighting, latency and a ratchet. It is good, and it governs ONE family: mined
research cards. Meanwhile the recommendation ledger sits at 123 open and 67 scheduled out of 283
(67% never reaching implementation), the research-conversion ledger tracks video and paper items
separately, the mined queue holds hundreds of unread candidates, and the GAP register holds
defects. Four backlogs, four separate measurements, and NOTHING that reads them together or shows
any of them to the organ whose job is to prioritise.

So the desk could truthfully report each family as tended while the aggregate rotted. Unconverted
inventory is not neutral: it consumed a cycle to acquire, it inflates every downstream audit's
picture of the desk's capability, and it makes the map read richer than the territory. Mining is
not the product; CONVERSION is. A perfect dig with zero conversions is a failed cycle.

========================= THE HARD PART: PRESSURE MUST NOT DILUTE =========================

Turning conversion pressure up has exactly two failure modes, and both LOOK like success:

  PADDING          -- propose more, weaker items so the throughput number rises. The reject rate
                      rises with volume; the desk reads "lots of recommendations" and converts a
                      smaller fraction of a worse pool.
  CHEAP DISPOSITION -- clear the backlog by marking things done. `mine_conversion` names this
                      exactly: without a quality layer, "kill everything" is the cheapest legal
                      way to unblock mining. The same applies to "implemented" as a status.

The naive fix -- push harder and hope -- makes both worse. So the fences here get STRONGER as the
pressure rises rather than staying fixed:

  1. RE-PROPOSING AN OPEN ITEM IS NOT CONVERSION, it is noise, and under pressure it is the
     single most likely thing to happen: the model is asked for twelve recommendations, has ten
     good ones, and fills the last two by restating what is already in the ledger. `duplicate_of`
     catches that on a normalised title and the contract rejects it.
  2. THE EVIDENCE BAR DOES NOT MOVE. Conversion pressure must never buy a weaker claim, so the
     `evidence` class still requires a cited number. Volume is negotiable; the bar is not.
  3. PADDING IS MEASURED AND REPORTED. `dilution_report` compares the reject rate of the recent
     window against the prior one. If pushing harder raised the reject rate, that is padding and
     it says so -- rather than the desk reading a higher raw count as more output.
  4. A CONVERSION IS A SHIPPED THING. The definition is inherited from `conversion_ledger` and is
     deliberately strict: shipped, tested code, or a measurement that changed a constant. Not
     "was interesting". Not "confirmed something".

NOTHING HERE DISPOSES OF ANYTHING. This measures and it pressures; a human or an implementation
agent still does the work. An organ that could both demand conversions and record them would
record them.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[2]

#: Statuses that count as CONVERTED, per family. Deliberately narrow -- `scheduled` is NOT a
#: conversion, it is a promise, and counting promises is how a backlog reads as worked while
#: nothing ships.
_CONVERTED = {"implemented", "done", "wired", "converted", "screened"}
_DEAD = {"rejected", "killed", "read_no_value", "retired"}


@dataclass(frozen=True)
class Family:
    """One conversion family: what was acquired, what became something, what is rotting."""
    name: str
    total: int
    converted: int
    dead: int
    open: int
    oldest_open_days: float | None = None
    note: str = ""

    @property
    def settled_rate(self) -> float | None:
        """Of the items that reached a VERDICT, what fraction converted. Answers "when this desk
        decides, does it decide to build?" -- and NOTHING about the backlog."""
        decided = self.converted + self.dead
        return round(self.converted / decided, 3) if decided else None

    @property
    def throughput_rate(self) -> float | None:
        """Of everything ACQUIRED, what fraction converted. The honest backlog number.

        BOTH RATES ARE REPORTED AND THIS ONE LEADS, because reporting only the settled rate is the
        denominator trick this desk forbids everywhere else. The recommendation ledger settles at
        95% -- 88 converted against 5 closed dead -- while 190 of 283 items sit open. A CRO reading
        "conversion rate 95%" concludes conversion is solved; the same family at 31% throughput
        says two-thirds of everything ever raised is still rotting, which is the truth and the
        whole reason this file exists. A metric that flatters the thing it measures is worse than
        no metric, because it ends the investigation.
        """
        return round(self.converted / self.total, 3) if self.total else None

    def line(self) -> str:
        age = f", oldest {self.oldest_open_days:.0f}d" if self.oldest_open_days else ""
        thru = f"{self.throughput_rate:.0%}" if self.throughput_rate is not None else "UNMEASURED"
        settled = f"{self.settled_rate:.0%}" if self.settled_rate is not None else "n/a"
        pct_open = f" ({self.open / self.total:.0%} of everything acquired)" if self.total else ""
        return (f"{self.name}: {self.open} OPEN{pct_open}{age} -- {self.converted} converted and "
                f"{self.dead} closed dead out of {self.total} acquired. THROUGHPUT {thru} "
                f"(settled rate {settled}, which excludes the open and must not be read as health)"
                + (f" [{self.note}]" if self.note else ""))


@dataclass(frozen=True)
class ConversionState:
    families: list[Family] = field(default_factory=list)
    generated_utc: str = ""

    @property
    def total_open(self) -> int:
        return sum(f.open for f in self.families)

    @property
    def total_acquired(self) -> int:
        return sum(f.total for f in self.families)

    def worst(self) -> Family | None:
        """The family with the most rotting inventory. Named explicitly because a board listing
        four backlogs produces none of them; naming the binding one produces work."""
        live = [f for f in self.families if f.open]
        return max(live, key=lambda f: f.open) if live else None

    def summary(self) -> str:
        return (f"{self.total_acquired} items acquired across {len(self.families)} families, "
                f"{self.total_open} still OPEN")


# ------------------------------------------------------------------------------ reading families

def assemble(root: Path | None = None) -> ConversionState:
    """Every conversion family the desk keeps, read together for the first time.

    A family whose ledger is absent or unreadable is reported with a note, never silently omitted
    -- a missing backlog reads as an empty one, and an empty backlog reads as a tended one.
    """
    base = root or _ROOT
    fams = [
        _recommendations(base),
        _research_conversions(base),
        _mined_queue(base),
        _cro(base),
    ]
    return ConversionState(families=[f for f in fams if f is not None],
                           generated_utc=datetime.now(UTC).isoformat(timespec="seconds"))


def _recommendations(base: Path) -> Family | None:
    p = base / "docs" / "research" / "recommendation_ledger.json"
    rows, note = _json_rows(p, "recommendations")
    if rows is None:
        return Family("recommendations", 0, 0, 0, 0, note=note)
    conv = sum(1 for r in rows if str(r.get("status", "")).lower() in _CONVERTED)
    dead = sum(1 for r in rows if str(r.get("status", "")).lower() in _DEAD)
    open_ = len(rows) - conv - dead
    # `scheduled` is counted OPEN, deliberately. A schedule is a promise, and a family that counts
    # promises as conversions reads as worked while nothing ships.
    sched = sum(1 for r in rows if str(r.get("status", "")).lower() == "scheduled")
    return Family("recommendations", len(rows), conv, dead, open_,
                  _oldest_days(rows, "raised"),
                  note=f"{sched} of the open are 'scheduled' -- a promise, not a conversion"
                  if sched else "")


def _research_conversions(base: Path) -> Family | None:
    rows, note = _jsonl_rows(base / "docs" / "research_conversions.jsonl")
    if rows is None:
        return Family("mined_research", 0, 0, 0, 0, note=note)
    conv = sum(1 for r in rows if r.get("outcome") == "converted")
    dead = sum(1 for r in rows if r.get("outcome") == "read_no_value")
    open_ = sum(1 for r in rows if r.get("outcome") == "queued_unread")
    return Family("mined_research", len(rows), conv, dead, open_,
                  _oldest_days(rows, "recorded_utc"))


def _mined_queue(base: Path) -> Family | None:
    """The miner's live queue. EVERY row here is unread by definition -- it is the raw acquisition
    rate, and the gap between it and `mined_research` is how much mining outruns reading."""
    p = base / "reports" / "research_queue.json"
    if not p.exists():
        return Family("mine_queue", 0, 0, 0, 0, note="queue artifact absent -- miner has not run")
    try:
        q = json.loads(p.read_text("utf-8")).get("queue") or []
    except (OSError, json.JSONDecodeError) as exc:
        return Family("mine_queue", 0, 0, 0, 0, note=f"unreadable: {type(exc).__name__}")
    return Family("mine_queue", len(q), 0, 0, len(q),
                  note="every row is unread by construction; this is the ACQUISITION rate, and "
                       "the gap to mined_research is how far mining outruns reading")


def _cro(base: Path) -> Family | None:
    rows, note = _jsonl_rows(base / "docs" / "research" / "cro_recommendations.jsonl")
    if rows is None:
        return Family("cro", 0, 0, 0, 0, note=note)
    conv = sum(1 for r in rows if str(r.get("disposition", "")).lower() in _CONVERTED)
    dead = sum(1 for r in rows if r.get("rejected_reason")
               or str(r.get("disposition", "")).lower() in _DEAD)
    return Family("cro", len(rows), conv, dead, len(rows) - conv - dead,
                  _oldest_days(rows, "utc"))


def _json_rows(p: Path, key: str) -> tuple[list[dict[str, Any]] | None, str]:
    if not p.exists():
        return None, f"{p.name} absent"
    try:
        obj = json.loads(p.read_text("utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return None, f"{p.name} unreadable: {type(exc).__name__}"
    rows = obj.get(key) if isinstance(obj, dict) else obj
    return (rows, "") if isinstance(rows, list) else (None, f"{p.name}: no '{key}' list")


def _jsonl_rows(p: Path) -> tuple[list[dict[str, Any]] | None, str]:
    if not p.exists():
        return None, f"{p.name} absent -- nothing recorded yet"
    out: list[dict[str, Any]] = []
    for line in p.read_text("utf-8").splitlines():
        if line.strip():
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out, ""


def _oldest_days(rows: list[dict[str, Any]], key: str) -> float | None:
    now = datetime.now(UTC)
    best: float | None = None
    for r in rows:
        raw = str(r.get(key) or "")[:19]
        if not raw:
            continue
        for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
            try:
                d = datetime.strptime(raw[:len(datetime.now().strftime(fmt))], fmt).replace(
                    tzinfo=UTC)
            except ValueError:
                continue
            age = (now - d).total_seconds() / 86400.0
            best = age if best is None else max(best, age)
            break
    return best


# ------------------------------------------------------------------------------- the pressure

def pressure_block(state: ConversionState) -> str:
    """The aggressive conversion demand, built from measured backlogs rather than exhortation.

    'Convert more' is exhortation and produces padding. 'The recommendation ledger holds 123 open
    items, the oldest 47 days old, and 67 more are merely scheduled' is a fact that produces work,
    and it is the same distinction the whole contract rests on.
    """
    lines = "\n".join(f"  - {f.line()}" for f in state.families)
    worst = state.worst()
    focus = (f"\nTHE BINDING BACKLOG THIS CYCLE is {worst.name} at {worst.open} open items. "
             "A board that lists four backlogs produces none of them; this is the one to attack."
             if worst else "")
    return f"""
========================= CONVERSION: ONE FAMILY, MAXIMISED =========================
Mining is not the product. CONVERSION is. Un-converted inventory is not neutral -- it consumed a
cycle to acquire, it inflates every downstream audit's picture of this desk's capability, and it
makes the map read richer than the territory. A perfect cycle with zero conversions is a FAILED
cycle.

Measured right now, across every family at once:

{lines}
{focus}

EVERY CYCLE YOU MUST, and these are not optional:
  - Name what is ROTTING: the specific open items whose age or value makes them the most
    expensive things on this list, by name, not by category.
  - Say WHY each is stuck. "Not prioritised" is not a reason; a reason is a missing dependency, a
    blocked credential, an unanswered question, or an item that should be KILLED and is not.
  - Recommend KILLS as readily as builds. An item that will never be converted should be closed
    dead, and refusing to kill it is how a backlog becomes permanent. `retire` is a full
    recommendation with the same required fields as any other.
  - Attack the ACQUISITION/READING gap where one exists. Mining faster than the desk reads
    manufactures inventory and calls it progress.

=========================== AND THE PRESSURE MUST NOT DILUTE ===========================
Turning conversion pressure up has exactly two failure modes and BOTH LOOK LIKE SUCCESS. You are
being asked for maximum aggression on conversion, so you are the one most exposed to them:

  PADDING -- filling your quota with weaker items so the count rises. If you have eight strong
    recommendations, RETURN EIGHT and say why the rest of the quota was not worth spending. A
    short list of falsifiable items beats a full list padded with the unfalsifiable, and the
    reject rate is measured across cycles, so padding is visible.
  RE-PROPOSING WHAT IS ALREADY OPEN -- the single most likely thing to happen under quota
    pressure. It is NOT conversion, it is noise that inflates the very backlog you are attacking,
    and a code check rejects it on a normalised title.

The evidence bar does NOT move because the pressure went up. `evidence` still requires a cited
number. Volume is negotiable; the bar is not.
"""


# -------------------------------------------------------------------- the anti-dilution fences

_NORM = re.compile(r"[^a-z0-9 ]+")


def normalise_title(title: str) -> str:
    """Lowercase, strip punctuation, collapse space, drop filler. Enough to catch a restatement
    without collapsing two genuinely different recommendations onto one key."""
    t = _NORM.sub(" ", str(title).lower())
    drop = {"the", "a", "an", "to", "for", "of", "and", "on", "in", "by", "with", "at"}
    return " ".join(w for w in t.split() if w not in drop)


def open_titles(path: Path | None = None) -> set[str]:
    """Normalised titles of everything currently OPEN, across families. What a new recommendation
    must not merely restate."""
    state_paths = [
        (path or _ROOT / "docs" / "research" / "cro_recommendations.jsonl", "title", "disposition"),
    ]
    out: set[str] = set()
    for p, tkey, dkey in state_paths:
        rows, _ = _jsonl_rows(p)
        for r in rows or []:
            if str(r.get(dkey, "")).lower() in _CONVERTED or r.get("rejected_reason"):
                continue
            if r.get(tkey):
                out.add(normalise_title(str(r[tkey])))
    ledger, _ = _json_rows(_ROOT / "docs" / "research" / "recommendation_ledger.json",
                           "recommendations")
    for r in ledger or []:
        if str(r.get("status", "")).lower() in _CONVERTED | _DEAD:
            continue
        if r.get("summary"):
            out.add(normalise_title(str(r["summary"])))
    return out


def duplicate_of(title: str, known: set[str]) -> bool:
    """Is this a restatement of something already open?

    Exact normalised match, plus a containment check for the common padding shape where a known
    item is restated with extra qualifiers bolted on. Deliberately NOT fuzzy beyond that: a false
    positive here silently discards a real recommendation, which is worse than letting one
    near-duplicate through.
    """
    n = normalise_title(title)
    if not n:
        return False
    if n in known:
        return True
    return any(k and (k in n or n in k) and min(len(k), len(n)) >= 20 for k in known)


def dilution_report(rows: list[dict[str, Any]], *, window: int = 24) -> dict[str, Any]:
    """Did the pressure buy volume at the cost of quality? Measured across cycles.

    THE NUMBER THAT KEEPS THIS HONEST. Aggression is supposed to raise conversions, not raise
    output. If the recent window's reject rate is materially above the prior window's, the extra
    output is padding and the desk should read the raw count as smaller, not larger.
    """
    if len(rows) < 2 * window:
        return {"verdict": f"UNMEASURED: need {2 * window} recorded rows to compare windows, "
                           f"have {len(rows)}", "n": len(rows)}
    recent, prior = rows[-window:], rows[-2 * window:-window]

    def rej(batch: list[dict[str, Any]]) -> float:
        return sum(1 for r in batch if r.get("rejected_reason")) / len(batch)

    r_now, r_before = rej(recent), rej(prior)
    out: dict[str, Any] = {
        "n": len(rows), "window": window, "reject_rate_recent": round(r_now, 3),
        "reject_rate_prior": round(r_before, 3), "delta": round(r_now - r_before, 3)}
    if r_now - r_before > 0.15:
        out["verdict"] = (f"PADDING: the reject rate rose from {r_before:.0%} to {r_now:.0%}. The "
                          "extra output is not extra value -- read the raw count as smaller, not "
                          "larger, and tighten the ask rather than raising the quota.")
    elif r_now > 0.5:
        out["verdict"] = (f"LOW YIELD: {r_now:.0%} of the recent window was rejected by the "
                          "contract, regardless of trend. The seat is mostly producing what the "
                          "fences catch.")
    else:
        out["verdict"] = (f"HOLDING: reject rate {r_now:.0%} against {r_before:.0%} prior -- "
                          "the pressure is not buying volume at the cost of quality.")
    return out

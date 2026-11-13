"""I7 -- THE POINT-IN-TIME LADDER, ACTUALLY CLIMBED. A lake nothing promotes into is a schema.

`libs/data/lake.py` has carried the whole ladder for days -- BRONZE byte-faithful, SILVER
normalised with a resolved `event_time`, GOLD folded -- along with the refusal rules that are the
reason it exists. Nothing on the tree called `promote`. Its Tier-1 row said bronze/silver/gold
"EXISTS as a row property with a refusing promoter", which is built, not done (III.16).

This is the first producer put through it, and what it publishes is the REFUSAL COUNT.

WHY THE REFUSALS ARE THE OUTPUT. A promoter that fills a missing `event_time` with the ingestion
time produces a lake in which every backtest passes and none of them mean anything, because every
row then claims to have been knowable at the moment it was scraped. `promote` refuses those rows
instead, and until something ran it nobody knew what share of the desk's own intelligence could
survive the question. That number is the measurement here: not how much was promoted, but how
much could not be, and why.

WHAT IT READS. The seat and crawler discoveries under `data/intelligence/**` -- the same tree
`miner_candidate_compiler` compiles from, so the two answer about one population. Each file's rows
are wrapped BRONZE (byte-faithful, hashed before anything touches them) and then offered to
SILVER, which is where `event_time` has to come from the producer's own fields or the row is
refused.

IT MOVES NOTHING AND PROMOTES NO HYPOTHESIS. The ladder is about provenance, not merit: a row
reaching SILVER has a defensible point-in-time stamp, and that is all it has. The ten gates decide
whether anything is true.

THE ZERO IT PUBLISHED WAS THE ORGAN'S, NOT THE CORPUS'S (N12, measured 2026-11-10). `to_bronze`
keeps what arrived as serialised text in `raw`, and this module offered silver the bronze WRAPPER
with no normaliser, so the producer's own fields were never opened: no row could resolve an event
time whatever it carried, and `silver_share` read 0.0 for every pass of its life -- the binding
term of the Tier-1 scorecard's `pit_compliance_pct`. On one tree that day 363 of 2,410 rows held a
recognised event key and all 2,410 were refused. `normalise_arrived` now opens the payload.

IT IS STRICTER THAN THE KEY LIST, NOT LOOSER. 354 of those 363 were a catalogue's `date` reading
"Yesterday" or "1 hour ago": a non-empty string under a recognised key, and no point in time at
all. An event time is taken only when it parses as an absolute ISO-8601 instant that is not in the
future; a relative or unparseable value is REFUSED under its own named reason. The desk's own
arrival stamps (`retrieved_at`, `first_seen_at`, `observed_at`, ...) are never an event time.

Artifact: desks/mt5/reports/LAKE_PROMOTION.json
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

OUT = DESK / "reports" / "LAKE_PROMOTION.json"

#: Both intelligence roots, because the compiler reads both and a ladder measured over one of them
#: would answer about a different population than the one the desk actually converts.
INTEL_ROOTS = (ROOT / "data" / "intelligence", DESK / "data" / "intelligence")

#: Files per pass. The ladder is cheap per row but the tree is large; this keeps one hourly leg
#: bounded while still turning over the whole corpus across a day.
MAX_FILES = 400

#: Rows per file. A single crawler dump can carry thousands; the refusal RATE is what is being
#: measured and it is estimated perfectly well from a bounded sample of each file.
MAX_ROWS_PER_FILE = 200


#: Producer fields that name when the thing was PUBLISHED OR CREATED BY ITS AUTHOR, beside
#: `libs.data.pit.EVENT_KEYS`. Declared here, counted apart in the artifact (`resolved_by_key`,
#: `silver_share_canonical_keys`), and never a desk-side arrival stamp.
PRODUCER_EVENT_ALIASES = ("published", "created")

#: The name published as each silver row's `normalisation`.
NORMALISATION = "arrived_fields_v2"

#: A producer clock may run a little ahead of this box; beyond this an event time is in the future
#: and stamps nothing.
FUTURE_TOLERANCE = timedelta(days=1)


class UnresolvableEventTime(ValueError):
    """The row names an event time that is not an absolute past instant."""


def absolute_instant(value: Any, now: datetime) -> str | None:
    """`value` as an ISO-8601 UTC instant, or None when it is not an absolute time not after now.

    "Yesterday", "1 hour ago", "Sep 3" and an empty string all return None: each needs a guess
    (relative to when? which year?) and the ladder refuses rather than guesses. A bare date is
    read as that day's first instant UTC, which is the earliest it can mean.
    """
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    try:
        if len(text) == 10:
            when = datetime.combine(date.fromisoformat(text), datetime.min.time(), tzinfo=UTC)
        else:
            when = datetime.fromisoformat(text.replace("Z", "+00:00"))
            when = when.replace(tzinfo=UTC) if when.tzinfo is None else when.astimezone(UTC)
    except ValueError:
        return None
    if when > now + FUTURE_TOLERANCE:
        return None
    return when.isoformat(timespec="seconds")


def normalise_arrived(bronze: dict[str, Any], *, now: datetime | None = None) -> dict[str, Any]:
    """The silver body of one bronze row: the producer's own fields, opened, and its event time.

    Returns the wrapper's own fields plus `fields` (what arrived, parsed) and, when the producer
    answered, `event_time` and `event_time_key`. A row that names no event time returns without
    one and `promote` refuses it. A row that names one this cannot read as an absolute past
    instant raises `UnresolvableEventTime`, so it is refused under that reason and not under
    "named none".
    """
    from libs.data.pit import EVENT_KEYS

    now = now or datetime.now(UTC)
    out = {k: v for k, v in bronze.items() if k not in ("raw", "raw_encoding", *EVENT_KEYS)}
    try:
        arrived = json.loads(bronze["raw"]) if bronze.get("raw_encoding") == "utf-8" else None
    except (KeyError, TypeError, ValueError):
        arrived = None
    if not isinstance(arrived, dict):
        return out
    out["fields"] = arrived
    named: list[str] = []
    for key in (*EVENT_KEYS, *PRODUCER_EVENT_ALIASES):
        value = arrived.get(key)
        if value in (None, "", [], {}):
            continue
        named.append(key)
        instant = absolute_instant(value, now)
        if instant:
            out["event_time"], out["event_time_key"] = instant, key
            return out
    if named:
        raise UnresolvableEventTime(
            f"`{named[0]}` is relative, unparseable or in the future -- not an absolute instant")
    return out


def _rows_of(doc: Any) -> list[dict[str, Any]]:
    if isinstance(doc, list):
        return [r for r in doc if isinstance(r, dict)]
    if isinstance(doc, dict):
        for key in ("rows", "discoveries", "items", "hypotheses", "claims"):
            v = doc.get(key)
            if isinstance(v, list):
                return [r for r in v if isinstance(r, dict)]
        return [doc]
    return []


def run(max_files: int = MAX_FILES) -> dict[str, Any]:
    now = datetime.now(UTC)
    try:
        from libs.data.lake import Layer, promote, to_bronze
    except Exception as exc:
        return {"at": now.isoformat(timespec="seconds"), "status": "UNMEASURABLE",
                "why": f"libs.data.lake is not importable ({type(exc).__name__}: {str(exc)[:140]})"}

    files: list[Path] = []
    for root in INTEL_ROOTS:
        if root.exists():
            files.extend(sorted(root.rglob("*.json"),
                                key=lambda f: -f.stat().st_mtime)[:max_files])
    files = files[:max_files]
    if not files:
        return {"at": now.isoformat(timespec="seconds"), "status": "UNMEASURED",
                "why": ("no intelligence files under " +
                        ", ".join(str(r) for r in INTEL_ROOTS) +
                        " -- an empty corpus is not a clean ladder")}

    bronze: list[dict[str, Any]] = []
    per_source: Counter[str] = Counter()
    unreadable = 0
    for f in files:
        try:
            doc = json.loads(f.read_text("utf-8"))
        except (OSError, ValueError):
            unreadable += 1
            continue
        source = f.parent.name or "intelligence"
        for row in _rows_of(doc)[:MAX_ROWS_PER_FILE]:
            bronze.append(to_bronze(row, source, now=now))
            per_source[source] += 1

    if not bronze:
        return {"at": now.isoformat(timespec="seconds"), "status": "UNMEASURED",
                "n_files": len(files), "unreadable_files": unreadable,
                "why": "every file read held no row-shaped content"}

    # BRONZE -> SILVER IS WHERE THE QUESTION IS ASKED. `event_time` must come from the producer's
    # own fields; a row that cannot answer is refused rather than stamped with its arrival.
    res = promote(bronze, Layer.BRONZE, Layer.SILVER, now=now, normalisation=NORMALISATION,
                  normalise=lambda r: normalise_arrived(r, now=now))
    by_key: Counter[str] = Counter(str(r.get("event_time_key")) for r in res.rows)
    canonical = sum(k for key, k in by_key.items() if key not in PRODUCER_EVENT_ALIASES)

    why_counts: Counter[str] = Counter()
    by_source_refused: Counter[str] = Counter()
    for r in res.refused:
        why_counts[str(r.get("refused_why") or r.get("why") or "unstated")[:120]] += 1
        by_source_refused[str(r.get("source") or "?")] += 1

    n = len(bronze)
    promoted = len(res.rows)
    return {
        "at": now.isoformat(timespec="seconds"),
        "status": "MEASURED",
        "n_files": len(files), "unreadable_files": unreadable,
        "n_bronze": n,
        "n_silver": promoted,
        "n_refused": len(res.refused),
        # THE HEADLINE. What share of the desk's own intelligence can survive being asked when it
        # was knowable. A low number is not a failure of this module.
        "silver_share": round(promoted / n, 4) if n else None,
        # WHICH PRODUCER FIELD ANSWERED, so the aliases can be discounted by a reader who wants
        # the canonical keys alone.
        "resolved_by_key": dict(by_key.most_common()),
        "silver_share_canonical_keys": round(canonical / n, 4) if n else None,
        "event_keys": {"canonical": "libs.data.pit.EVENT_KEYS",
                       "producer_aliases": list(PRODUCER_EVENT_ALIASES)},
        "normalisation": NORMALISATION,
        "refusal_reasons": dict(why_counts.most_common(12)),
        "rows_by_source": dict(per_source.most_common(20)),
        "refused_by_source": dict(by_source_refused.most_common(20)),
        "rule": ("bronze is byte-faithful and hashed before anything touches it; silver requires "
                 "an event_time resolved from the PRODUCER's own fields as an absolute instant "
                 "not in the future, and a row that cannot answer (or answers 'Yesterday') is "
                 "refused rather than stamped with its arrival time"),
        "why_refusals_are_the_output": (
            "a promoter that fills a missing event_time with the ingestion time produces a lake "
            "in which every backtest passes and none of them mean anything"),
        "authority": ("ZERO -- the ladder is about provenance, not merit; the ten "
                      "gates decide what is true"),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--max-files", type=int, default=MAX_FILES)
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args(argv)
    doc = run(args.max_files)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(doc, indent=1), encoding="utf-8")
    if doc["status"] != "MEASURED":
        print(f"lake_promote: {doc['status']} -- {str(doc.get('why'))[:170]}")
    else:
        print(f"lake_promote: {doc['n_bronze']} bronze -> {doc['n_silver']} silver "
              f"({doc['silver_share']:.1%}), {doc['n_refused']} refused")
        for why, k in list(doc["refusal_reasons"].items())[:4]:
            print(f"   {k:>6}  {why[:100]}")
    print(f"-> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

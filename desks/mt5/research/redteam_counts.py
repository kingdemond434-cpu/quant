#!/usr/bin/env python3
"""RED-TEAM COUNTS: how many ideas each of the desk's red-team organs killed, passed or could not
judge, in a form the public repository may carry (hourly-pass sweep, 2026-11-13).

The committees, the committee ensembles, the falsifier battery and the decay walk all write their
verdicts on the box, and none of those reports may cross the wire as written: each carries free
exception text (a path, a host or a login can sit inside any `{exc}`), and decay_live.json is on
the publish list's NEVER line for that reason. So origin read zero measured output from all four,
and the desk could not measure its own kill rate or catch rate.

This organ reads each report and keeps ONLY what cannot carry text:
  * the report's own stamp (an ISO time, validated as one) and its top-level integer counts;
  * a tally of every `verdict` / `status` / `state` / `decision` / `regime` value that is an
    enum token (upper-case letters, digits and underscores, at most 32 characters), wherever it
    sits in the document. Anything else -- a sentence, a path, an exception -- is not counted and
    not copied; it is tallied only as `n_non_enum` so a reader can see it existed.

    python desks/mt5/research/redteam_counts.py [--json] [--dry-run]

Writes `reports/REDTEAM_COUNTS.json`, carried by the box publish list.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
SOURCES: dict[str, Path] = {
    "committees": DESK / "reports" / "COMMITTEE_IDEA_MINER.json",
    "committee_ensembles": DESK / "reports" / "COMMITTEES.json",
    "falsifier_run": DESK / "reports" / "FALSIFIER_VERDICTS.json",
    "decay_monitor": DESK / "data" / "decay_live.json",
}
OUT = DESK / "reports" / "REDTEAM_COUNTS.json"

#: Keys whose values are verdicts. `regime` carries decay_regime's per-sleeve state through
#: decay_monitor (DECAY_REGIME).
VERDICT_KEYS = ("verdict", "status", "state", "decision", "regime", "roster_state")
ENUM = re.compile(r"^[A-Z][A-Z0-9_]{1,31}$")
STAMP_KEYS = ("generated_utc", "generated_at", "checked_at", "at", "asof", "measured_at")
#: A walk this deep covers every report named above (their verdict rows sit at depth 2-4); the
#: bound stops a pathological document from costing the hour.
MAX_DEPTH = 8


def _stamp(doc: dict[str, Any]) -> str | None:
    for k in STAMP_KEYS:
        v = doc.get(k)
        if isinstance(v, str):
            try:
                d = datetime.fromisoformat(v.replace("Z", "+00:00"))
            except ValueError:
                continue
            d = d if d.tzinfo else d.replace(tzinfo=UTC)
            return d.astimezone(UTC).isoformat(timespec="seconds")
    return None


def tally(doc: Any) -> dict[str, Any]:
    """{key: {ENUM: n}} over every verdict-shaped value, plus how many were not enum tokens."""
    counts: dict[str, Counter[str]] = {k: Counter() for k in VERDICT_KEYS}
    non_enum = 0

    def walk(x: Any, depth: int) -> None:
        nonlocal non_enum
        if depth > MAX_DEPTH:
            return
        if isinstance(x, dict):
            for k, v in x.items():
                if k in counts and isinstance(v, str):
                    if ENUM.match(v):
                        counts[k][v] += 1
                    else:
                        non_enum += 1
                elif isinstance(v, (dict, list)):
                    walk(v, depth + 1)
        elif isinstance(x, list):
            for v in x:
                walk(v, depth + 1)

    walk(doc, 0)
    return {"counts": {k: dict(sorted(c.items())) for k, c in counts.items() if c},
            "n_non_enum": non_enum}


def summarise(path: Path) -> dict[str, Any]:
    try:
        doc = json.loads(path.read_text("utf-8"))
    except FileNotFoundError:
        return {"status": "ABSENT"}
    except (OSError, ValueError) as exc:
        return {"status": "UNREADABLE", "error_class": type(exc).__name__}
    out: dict[str, Any] = {"status": "READ"}
    if isinstance(doc, dict):
        out["stamp"] = _stamp(doc)
        out["top_counts"] = {k: v for k, v in sorted(doc.items())
                             if isinstance(v, int) and not isinstance(v, bool)
                             and re.match(r"^[a-z0-9_]{1,40}$", k)}
    out.update(tally(doc))
    return out


def build(now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(tz=UTC)
    organs = {name: summarise(p) for name, p in SOURCES.items()}
    read = sum(1 for o in organs.values() if o["status"] == "READ")
    return {"generated_utc": now.isoformat(timespec="seconds"),
            "status": "MEASURED" if read else "UNMEASURED",
            "n_read": read, "n_organs": len(organs), "organs": organs,
            "rule": "enum verdict tokens and integer counts only; no text crosses",
            "valid_until": (now + timedelta(hours=26)).isoformat(timespec="seconds")}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    doc = build()
    if not a.dry_run:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        tmp = OUT.with_suffix(".tmp")
        tmp.write_text(json.dumps(doc, indent=1), "utf-8")
        tmp.replace(OUT)
    if a.json:
        print(json.dumps(doc))
    else:
        print(f"redteam_counts: {doc['status']} {doc['n_read']}/{doc['n_organs']} organs read")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

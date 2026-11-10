#!/usr/bin/env python3
"""EVERY BLUEPRINT ROW, RE-SCORED FROM EVIDENCE EVERY HOUR -- NEVER FROM A DOCUMENT'S SAY-SO.

    python scripts/check_blueprint_score.py                  # portable fence: exit 1 on a lie
    python scripts/check_blueprint_score.py --write          # re-score, write the artifact
    python scripts/check_blueprint_score.py --require-state  # box half: artifact fresh, not RED

THE ASK (BACKLOG rows 20 and 82, principal 2026-09-29): "verify all my blueprints are done; if
not, get them fully done", and "finish all 20 audit items and 52 Tier-5 partials with ledger".
The 2026-09-30 strict re-score found 0 of 138 blueprint rows DONE and nothing re-scored them for
five weeks: the matrix (docs/audit/BLUEPRINT_VERIFICATION.md) is prose, so every number in it
began to decay the hour it was written. The cure is the one the Tier-1 programme already uses --
the ledger is DATA and a checker is its gate -- applied to the two ledgers that were not data:

  * docs/research/blueprint_ledger/      the 138 strict rows (A1, A2 = the 20 audit items I1-I20
    plus P1, B1, B2, C), in the Tier-1 ledger's schema, verified by
    `check_tier1_program.check` itself -- one verifier, not a second;
  * docs/research/tier5_audit.json       the 272 Tier-5 sections (52 of them PARTIAL), verified
    by `check_tier5_audit.check` and its clock table.

HOW A ROW'S STATE IS DERIVED. Seven marks, the strict definition of 2026-09-30:

  I  implemented    every code path the row cites exists in this tree          MEASURED
  W  wired          a clock source (hourly/daily cycle, box task manifest, ops timer/unit/
                    script) names one of the row's modules                      MEASURED
  A  authoritative  its output decides something                                RECORDED
  T  tested         a test file names one of the row's modules (or the test the row cites
                    exists); whether it PASSES is C's business (CI)             MEASURED
  R  artifact       an artifact the row names exists on THIS host, under 72 h   MEASURED
  D  deployed       this checkout is LIVE (the box's branch) and I holds        MEASURED
  C  consistent     committed state does not contradict it; CI green            RECORDED

A RECORDED mark is a reviewer's judgement in the ledger. It counts only while it is younger than
the ledger's `mark_ttl_days` (14): an old judgement is UNMEASURED, not a pass, and a recorded ✓ is
honoured only with `mark_evidence[<mark>]` citing a file that exists. A measured mark that cannot
be measured here (no cited module, no named artifact on this host) is UNMEASURED -- never ✓.

The row's state is the MINIMUM of what it claims and what the evidence proves, on the order
OPEN < UNMEASURED < PARTIAL < DONE (EXCLUDED is outside the denominator). The scorer never
raises a row above its claim: evidence that would is reported as `promotable`, for a reviewer to
write into the ledger. A row that CLAIMS DONE without all seven marks proven is a LIE.

THE FENCE IS RED when (a) any ledger lies (a DONE claim unproven, a Tier-1/Tier-5 checker lie, a
recorded ✓ with no evidence), or (b) a ledger's DONE count FELL since the previous artifact on
this host. An absent ledger is UNMEASURED (exit 2), never a clean pass.

Artifact: desks/mt5/reports/BLUEPRINT_SCORE.json -- counts per state per ledger, the 20 audit
items and the 52 Tier-5 partials as their own subsets, and every non-DONE row ranked by its
expected E[log W] weight so the open work can be routed.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

# the evidence half: one checker in two files
from blueprint_marks import (
    BLUEPRINT,
    LIVE_BRANCH,
    ROOT,
    STATE_MAX_AGE_H,
    STATES,
    UNMEASURED,
    Host,
    _read_json,
    _stamp,
    score_blueprint_row,
    score_tier5_row,
    tier1,
    tier5,
    weight,
)

#: The names a caller (the tests, the fence) reaches through this script.
__all__ = ["BLUEPRINT", "LIVE_BRANCH", "load_blueprint", "main", "require_state", "score",
           "weight"]


def load_blueprint(path: Path) -> dict[str, Any] | None:
    """The blueprint ledger as ONE document, whichever form it is stored in.

    It is stored SPLIT (docs/research/blueprint_ledger/: index.json holds every header field and
    names its parts in order; each part holds {"phase", "items"}) because a single 4,000-line
    file is one diff hunk too large for the independent reviewer to read whole. The assembled
    document is the one the single file held, field for field and row for row. A missing or
    unreadable index or part reads None -- UNMEASURED, never a ledger silently short of rows."""
    if not path.is_dir():
        doc = _read_json(path)
        return doc if isinstance(doc, dict) else None
    index = _read_json(path / "index.json")
    if not isinstance(index, dict) or not isinstance(index.get("parts"), list):
        return None
    items: list[Any] = []
    for name in index["parts"]:
        part = _read_json(path / str(name))
        if not isinstance(part, dict) or not isinstance(part.get("items"), list):
            return None
        items += part["items"]
    doc = {k: v for k, v in index.items() if k != "parts"}
    doc["items"] = items
    return doc



def _counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    c = Counter(r["state"] for r in rows)
    return {s: int(c.get(s, 0)) for s in STATES}


def score(root: Path = ROOT, *, now: datetime | None = None, branch: str | None = None,
          blueprint_path: Path | None = None, tier5_path: Path | None = None,
          previous: dict[str, Any] | None = None) -> dict[str, Any]:
    now = now or datetime.now(tz=UTC)
    t0 = time.monotonic()
    host = Host(root, now, branch)
    bp_doc = load_blueprint(blueprint_path or root / "docs" / "research" / "blueprint_ledger")
    t5_doc = _read_json(tier5_path or root / "docs" / "research" / "tier5_audit.json")
    lies: list[str] = []
    ledgers: dict[str, Any] = {}
    rows: list[dict[str, Any]] = []
    if isinstance(bp_doc, dict) and isinstance(bp_doc.get("items"), list):
        problems, _census = tier1.check(bp_doc, root)
        lies += [f"blueprint ledger: {p}" for p in problems]
        exp = dict(bp_doc.get("expected_counts") or {})
        for phase, n in exp.items():
            have = sum(1 for it in bp_doc["items"] if str(it.get("phase")) == phase)
            if have != int(n):
                lies.append(f"blueprint ledger: phase {phase} lists {have} rows, {n} expected")
        ttl = float(bp_doc.get("mark_ttl_days") or 14)
        bp_rows = [score_blueprint_row(it, host, ttl, root) for it in bp_doc["items"]]
        for r in bp_rows:
            lies += r["lies"]
        rows += bp_rows
        audit = [r for r in bp_rows if r["phase"] == "A2" and re.fullmatch(r"I\d+", str(r["id"]))]
        ledgers["blueprint"] = {"measured": True, "n": len(bp_rows), "counts": _counts(bp_rows),
                                "by_phase": {p: _counts([r for r in bp_rows if r["phase"] == p])
                                             for p in sorted({str(r["phase"]) for r in bp_rows})}}
        ledgers["audit_items_20"] = {"measured": True, "n": len(audit), "counts": _counts(audit)}
    else:
        ledgers["blueprint"] = {"measured": False, "why": "docs/research/blueprint_ledger/ "
                                "absent or unreadable"}
        ledgers["audit_items_20"] = {"measured": False, "why": "the blueprint ledger is absent"}
    if isinstance(t5_doc, dict) and isinstance(t5_doc.get("sections"), list):
        problems, _census = tier5.check(t5_doc, root)
        lies += [f"tier-5 audit: {p}" for p in problems]
        t5_rows = [score_tier5_row(it, host, root) for it in t5_doc["sections"]]
        rows += t5_rows
        partials = [r for r in t5_rows if r["claim"] == "PARTIAL"]
        ledgers["tier5"] = {"measured": True, "n": len(t5_rows), "counts": _counts(t5_rows),
                            "unproven_live_claims": sum(1 for r in t5_rows
                                                        if r["claim"] == "EXISTS+WIRED+LIVE"
                                                        and r["state"] != "DONE")}
        ledgers["tier5_partials_52"] = {"measured": True, "n": len(partials),
                                        "counts": _counts(partials),
                                        "promotable": [r["id"] for r in partials
                                                       if r["promotable"]]}
    else:
        ledgers["tier5"] = {"measured": False, "why": "docs/research/tier5_audit.json absent"}
        ledgers["tier5_partials_52"] = {"measured": False, "why": "the tier-5 ledger is absent"}
    drops: list[str] = []
    prev_ledgers = (previous or {}).get("ledgers") or {}
    for name, cur in ledgers.items():
        before = (prev_ledgers.get(name) or {}).get("counts") or {}
        if cur.get("measured") and "DONE" in before and cur["counts"]["DONE"] < int(before["DONE"]):
            drops.append(f"{name}: DONE fell {before['DONE']} -> {cur['counts']['DONE']}")
    open_rows = sorted((r for r in rows if r["state"] not in ("DONE", "EXCLUDED")),
                       key=lambda r: (-r["weight"], -r["held"], str(r["ledger"]), str(r["id"])))
    measured = all(v.get("measured") for v in ledgers.values())
    verdict = "RED" if (lies or drops) else ("GREEN" if measured else UNMEASURED)
    return {"generated_at": now.isoformat(timespec="seconds"), "host_root": str(root),
            "branch": host.branch, "verdict": verdict, "lies": lies, "done_drops": drops,
            "ledgers": ledgers,
            "open_ranked": [{k: r[k] for k in ("ledger", "id", "item", "state", "marks",
                                                "weight", "money_path", "gap")}
                            for r in open_rows],
            "rows": [{k: r[k] for k in ("ledger", "id", "claim", "state", "marks", "weight",
                                        "promotable")} for r in rows],
            "previous": {k: (v or {}).get("counts") for k, v in prev_ledgers.items()},
            "rule": ("a row is DONE only on evidence measured on this host (seven marks for the "
                     "blueprint ledger; files + known clock + a current artifact for the Tier-5 "
                     "ledger); the state is the minimum of claim and evidence; absent inputs are "
                     "UNMEASURED; RED on any lie or a fall in a ledger's DONE count"),
            "elapsed_s": round(time.monotonic() - t0, 2)}


def _write(path: Path, doc: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n", "utf-8")
    os.replace(tmp, path)


def require_state(path: Path, now: datetime | None = None) -> tuple[int, str]:
    now = now or datetime.now(tz=UTC)
    doc = _read_json(path)
    if not isinstance(doc, dict):
        return 1, f"BLUEPRINT_SCORE absent at {path}: the hourly leg has not scored here"
    at = _stamp(doc.get("generated_at"))
    if at is None or (now - at).total_seconds() > STATE_MAX_AGE_H * 3600:
        return 1, f"BLUEPRINT_SCORE stale (generated_at {doc.get('generated_at')})"
    if doc.get("verdict") == "RED":
        return 1, "BLUEPRINT_SCORE is RED: " + "; ".join((doc.get("lies") or [])[:3]
                                                          + (doc.get("done_drops") or [])[:3])
    return 0, f"BLUEPRINT_SCORE {doc.get('verdict')} at {doc.get('generated_at')}"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", type=Path, default=ROOT)
    ap.add_argument("--write", action="store_true", help="write the artifact (the hourly leg)")
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--require-state", action="store_true",
                    help="box half: the artifact is present, under 3 h old and not RED")
    args = ap.parse_args(argv)
    out = args.out or args.root / "desks" / "mt5" / "reports" / "BLUEPRINT_SCORE.json"
    if args.require_state:
        code, msg = require_state(out)
        print(msg)
        return code
    prev = _read_json(out) if args.write else None
    doc = score(args.root, previous=prev if isinstance(prev, dict) else None)
    for name, led in doc["ledgers"].items():
        if led.get("measured"):
            print(f"{name}: {led['n']} rows; " + ", ".join(f"{k} {v}" for k, v in
                                                          led["counts"].items()))
        else:
            print(f"{name}: UNMEASURED ({led.get('why')})")
    for lie in doc["lies"][:20]:
        print(f"  LIE: {lie}")
    for d in doc["done_drops"]:
        print(f"  DROP: {d}")
    print(f"verdict {doc['verdict']} ({doc['elapsed_s']} s)")
    if args.write:
        _write(out, doc)
        print(f"wrote {out}")
    if doc["verdict"] == "RED":
        return 1
    return 2 if doc["verdict"] == UNMEASURED else 0


if __name__ == "__main__":
    raise SystemExit(main())

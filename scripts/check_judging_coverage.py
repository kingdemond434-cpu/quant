#!/usr/bin/env python
"""87% OF THE DOCKET SAT UNJUDGED AND NOTHING SAID SO.

WHAT HAPPENED, AND WHY THIS FILE EXISTS (2026-09-24). A funnel census found 476,702 admissible
cells that had never been judged -- 87% of a 546,104-cell docket. They were not lost, broken or
rejected. Nothing had ever looked at them. The desk's own artifacts carried the fact the whole
time: `JUDGE_COVERAGE.json` has published `unjudged_total` and `oldest_unjudged_age_h` per
family for as long as it has existed, and no organ read either.

That is the same shape as every other defect found the same day: 1,196 placement refusals nobody
read, 837 rows retired against an empty canon, 158 certificates voided by a tuple comparison, a
validity gate whose absence read as a FAIL. In each case the evidence existed and no organ was
watching it. The principal's instruction is that this one must not recur: "make all of it judged
n this should never repeat again where none are judged, it should always be 100% judged fast."

SO THIS FENCE READS THE STALL, NOT ITS CAUSE -- the same principle as
`check_placement_interlock.py`, and for the same reason: the next time judging stops it will be
for a reason nobody has thought of yet, and a fence keyed to today's reason would miss it as
thoroughly as no fence at all. It does not ask why cells are unjudged. It asks whether the
unjudged count is MOVING.

A BACKLOG IS NOT A BREACH; A STALLED BACKLOG IS. This distinction is the whole design. The desk
will hold a large backlog for as long as its miners outproduce its judge, and a fence that fired
on size alone would be red from the day it was written -- and `check_placement_interlock.py`
records exactly what that costs: "a gate that is always red is a gate somebody switches off, and
then the next real halt is silent again" (L1.43). A steady 5,000 that turns over daily is
healthy. A steady 5,000 that never moves is a stall wearing a number.

Two breaches, either sufficient:

  (a) COVERAGE WENT BACKWARDS. `judged_total` fell below the ratchet's high-water mark by more
      than `RATCHET_TOLERANCE`. Coverage floors ratchet UP only (L1.50), so a fall is either a
      lost ledger or a docket rewritten under the judge, and both are defects.
  (b) JUDGING STALLED. `unjudged_total` has not fallen across `STALL_READINGS` consecutive
      readings spanning at least `STALL_HOURS`, while the docket still holds unjudged cells.
      That is "cells are not being judged", whatever the reason -- a dead task, a starved leg,
      a judge that cannot reach its epilogue, a docket nothing consumes.

IT CAPS NOTHING, GATES NO CAPITAL AND RATIONS NOTHING. Judging more cells is free in
multiplicity terms -- the charge is pinned at a fixed trial count and measured in effective
independent tests -- so there is no reason to ration what reaches the judge and this fence never
proposes one. If anything it exists to make the desk judge MORE, by making a stall visible in
one pass instead of never.

NOT-APPLICABLE IS NOT UNMEASURED (L1.43). A clean checkout, CI or the VPS has no
JUDGE_COVERAGE.json because it runs no judge; that passes, saying so. A host that HAS the
artifact and cannot read it is UNMEASURED and FAILS (L1.28a, WS-005) -- "no evidence" is exactly
what 87% unjudged looked like from the outside.

Artifact: `desks/mt5/reports/JUDGING_COVERAGE.json`; ratchet state in
`desks/mt5/data/judging_coverage_ratchet.json`. Registered in `scripts/run_law_gate.py`
`_STATE_FENCES`.

    python scripts/check_judging_coverage.py
    python scripts/check_judging_coverage.py --json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DESK = ROOT / "desks" / "mt5"
SOURCE = DESK / "reports" / "JUDGE_COVERAGE.json"
OUT = DESK / "reports" / "JUDGING_COVERAGE.json"
RATCHET = DESK / "data" / "judging_coverage_ratchet.json"

#: How many consecutive readings with no fall in `unjudged_total` count as a stall rather than a
#: slow hour. `judge_coverage` republishes on every core pass, so a handful of readings is hours.
STALL_READINGS = 6
#: ...and the run must also span this long, so a burst of readings in one minute is not a stall.
STALL_HOURS = 3.0
#: How far `judged_total` may fall below its high-water mark before it is a regression rather
#: than the docket being recounted. Cells legitimately leave the docket (untradeable symbols,
#: banned families, the event lane), so this is not zero.
RATCHET_TOLERANCE = 5_000


def _read(path: Path) -> Any:
    return json.loads(path.read_text("utf-8"))


def _atomic(path: Path, doc: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    os.replace(tmp, path)


def _parse(ts: object) -> datetime | None:
    try:
        out = datetime.fromisoformat(str(ts))
    except (TypeError, ValueError):
        return None
    return out if out.tzinfo else out.replace(tzinfo=UTC)


def measure(source: Path | None = None, ratchet: Path | None = None) -> dict:
    """The coverage reading, the ratchet it advances, and the verdict. Pure of argv."""
    src = source or SOURCE
    rat = ratchet or RATCHET
    now = datetime.now(UTC)

    if not src.exists():
        return {"status": "NOT_APPLICABLE", "ok": True, "at": now.isoformat(timespec="seconds"),
                "why": (f"{src.relpath if hasattr(src, 'relpath') else src} is absent: this host "
                        f"runs no judge, so there is no coverage to fence (L1.43)")}
    try:
        doc = _read(src)
        totals = doc.get("totals") or {}
        if not isinstance(totals, dict) or "unjudged_total" not in totals:
            raise ValueError("no totals.unjudged_total")
    except (OSError, ValueError) as exc:
        return {"status": "UNMEASURED", "ok": False, "at": now.isoformat(timespec="seconds"),
                "why": (f"{src.name} exists and cannot be read ({type(exc).__name__}: {exc}). "
                        f"A judging host that cannot say what it has judged is exactly the "
                        f"silence this fence exists to break (L1.28a)")}

    unjudged = int(totals.get("unjudged_total") or 0)
    docket = int(totals.get("docket_rows") or 0)
    judged = max(0, docket - unjudged)
    oldest_h = float(totals.get("oldest_unjudged_age_h") or 0.0)
    reading = {"at": (_parse(doc.get("at")) or now).isoformat(timespec="seconds"),
               "unjudged": unjudged, "judged": judged, "docket": docket,
               "oldest_unjudged_age_h": round(oldest_h, 2)}

    try:
        state = _read(rat)
        if not isinstance(state, dict):
            state = {}
    except (OSError, ValueError):
        state = {}
    history: list[dict] = [r for r in (state.get("history") or []) if isinstance(r, dict)]
    if not history or history[-1].get("at") != reading["at"]:
        history.append(reading)
    history = history[-40:]
    high_water = max(int(state.get("judged_high_water") or 0), judged)

    breaches: list[str] = []
    # (a) the ratchet
    if judged + RATCHET_TOLERANCE < int(state.get("judged_high_water") or 0):
        breaches.append(
            f"COVERAGE WENT BACKWARDS: judged {judged:,} is more than {RATCHET_TOLERANCE:,} "
            f"below the high-water mark {int(state['judged_high_water']):,}. Coverage floors "
            f"ratchet up only (L1.50)")
    # (b) the stall
    recent = history[-STALL_READINGS:]
    if unjudged > 0 and len(recent) >= STALL_READINGS:
        first, last = _parse(recent[0]["at"]), _parse(recent[-1]["at"])
        span_h = ((last - first).total_seconds() / 3600.0) if (first and last) else 0.0
        fell = any(int(r.get("unjudged") or 0) > unjudged for r in recent[:-1])
        if span_h >= STALL_HOURS and not fell:
            breaches.append(
                f"JUDGING STALLED: unjudged_total has not fallen below {unjudged:,} across "
                f"{len(recent)} readings spanning {span_h:.1f}h, with {unjudged:,} cells still "
                f"unjudged and the oldest {oldest_h:.0f}h old. Cells are not being judged")

    out = {
        "status": "BREACH" if breaches else "OK",
        "ok": not breaches,
        "at": now.isoformat(timespec="seconds"),
        "source": str(src),
        **reading,
        "judged_share": round(judged / docket, 6) if docket else None,
        "judged_high_water": high_water,
        "readings_held": len(history),
        "breaches": breaches,
        "rule": ("a backlog is not a breach; a STALLED backlog is. This fence reads whether the "
                 "unjudged count is moving, never why it is not -- the next stall will have a "
                 "reason nobody has thought of yet. It caps nothing and rations nothing."),
    }
    _atomic(rat, {"judged_high_water": high_water, "history": history,
                  "updated_at": now.isoformat(timespec="seconds")})
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    out = measure()
    _atomic(OUT, out)
    if a.json:
        print(json.dumps(out, indent=1))
    else:
        print(f"judging coverage: {out['status']}")
        if out.get("docket"):
            print(f"  docket {out['docket']:,}  judged {out['judged']:,} "
                  f"({(out.get('judged_share') or 0) * 100:.1f}%)  "
                  f"unjudged {out['unjudged']:,}  oldest {out['oldest_unjudged_age_h']}h")
        else:
            print(f"  {out.get('why', '')}")
        for b in out.get("breaches") or []:
            print(f"  BREACH: {b}")
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())

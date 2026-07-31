#!/usr/bin/env python3
"""EXPLORATION FAMILY FENCE (L1.32) -- the unknown-unknown organs are ONE family, measured as one.

PRINCIPAL ORDER (2026-07-31): *"same with unknowns, gaps, blindspots -- these are all families."*

THE DEFECT THIS CLOSES. This desk owns SIX organs that all sample the same space -- "what we do
not know we do not know" -- and until now each ran on its own cadence, with its own artifact, and
NOTHING looked at them together:

    capability_hunt   what capability is missing entirely          (L1.31, 3x/day, 8 lenses)
    blindspot_max     the desk's own blind spots                   data/blindspot_max.json
    blindspot_prober  information-class probes                     data/blindspot_probes.json
    blindrediscovery  ideas worth re-opening on new capability     cro_ai_logs (dig seat)
    kimi_hunter       an INDEPENDENT family hunting mechanisms     data/kimi_hunt.json
    deep_sweep meta   the meta-and-blindspots audit seat           docs/research/deep_sweep/

Three failures follow from treating them as unrelated singletons, and all three are live:
 1. UNMEASURED YIELD -- an organ that has produced NOTHING for weeks looks exactly like one
    producing steadily, because nobody compares them. `blindrediscovery` was scheduled with
    `last=never` and only a human noticing caught it.
 2. UNCOORDINATED COVERAGE -- six organs free to hunt the same region on the same day is one
    organ's worth of diversity at six organs' cost. Lens rotation (L1.31) solved this WITHIN the
    capability hunt; this fence extends the accounting ACROSS the family.
 3. NO FAMILY-LEVEL FLOOR -- exploration could decay to zero organ by organ, each decay
    individually unremarkable, with no single number that would have shown it.

STATUSES:
  DARK        >=1 organ has NEVER produced an artifact -- scheduled and silent. Fence FAILS.
  STALE       an organ's artifact is older than its own cadence allows (produced once, then
              quietly stopped -- the failure mode L1.25a forbids as a response to null streaks).
  THIN        the family is running but fewer than half the organs produced this week.
  OK          every organ produced within its window.

NEVER a throttle: this fence can only ever demand MORE exploration. It has no path that
recommends running any organ less (L1.8 / L1.25a) -- if two organs overlap, the answer is to
re-aim one, never to silence it.

    python scripts/check_exploration.py [--report-only] [--json]
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent

#: organ -> (artifact, max_age_hours implied by its own cadence, what it hunts)
_FAMILY: dict[str, tuple[str, float, str]] = {
    "capability_hunt": ("data/capability_hunt.json", 36,
                        "capabilities the desk never conceived (8 rotating lenses, 3x/day)"),
    "blindspot_max": ("data/blindspot_max.json", 36, "the desk's own blind spots (daily)"),
    "blindspot_prober": ("data/blindspot_probes.json", 24 * 8,
                         "information-class probes (weekly)"),
    "kimi_hunter": ("data/kimi_hunt.json", 12,
                    "mechanism hunting by an INDEPENDENT model family (8x/day)"),
    "hunt_coverage": ("data/hunt_coverage.json", 24 * 8,
                      "which regions of the hunt space have been covered"),
    "deep_sweep_meta": ("docs/research/deep_sweep", 24 * 8,
                        "the meta-and-blindspots audit seat (weekly 9-seat sweep)"),
}


def _age_hours(p: Path, now: datetime) -> float | None:
    """Age of the newest file at this path (dir = newest child). None = never produced."""
    if not p.exists():
        return None
    if p.is_dir():
        kids = [c for c in p.rglob("*") if c.is_file()]
        if not kids:
            return None
        newest = max(c.stat().st_mtime for c in kids)
    else:
        newest = p.stat().st_mtime
    return (now.timestamp() - newest) / 3600.0


def build_report(root: Path | None = None, now: datetime | None = None) -> dict[str, Any]:
    root = root or _ROOT
    now = now or datetime.now(tz=UTC)
    organs: dict[str, Any] = {}
    dark, stale, fresh = [], [], []
    for name, (rel, max_h, hunts) in _FAMILY.items():
        age = _age_hours(root / rel, now)
        if age is None:
            state = "NEVER-PRODUCED"
            dark.append(name)
        elif age > max_h:
            state = "STALE"
            stale.append(name)
        else:
            state = "FRESH"
            fresh.append(name)
        organs[name] = {"state": state, "artifact": rel, "hunts": hunts,
                        "age_hours": None if age is None else round(age, 1),
                        "max_age_hours": max_h}

    n = len(_FAMILY)
    if dark:
        status = "DARK"
    elif stale:
        status = "STALE"
    elif len(fresh) < n / 2:
        status = "THIN"
    else:
        status = "OK"
    return {
        "generated": now.isoformat(),
        "law": "L1.32 -- the unknown-unknown organs are ONE family; measured together or not "
               "at all. This fence can only ever demand MORE exploration.",
        "status": status,
        "n_organs": n, "n_fresh": len(fresh), "n_stale": len(stale), "n_dark": len(dark),
        "dark": dark, "stale": stale,
        "organs": organs,
        "detail": (f"{len(fresh)}/{n} organs produced within their own cadence; "
                   f"{len(dark)} never produced, {len(stale)} stale"),
        "next_action": (
            "a DARK organ is scheduled and silent -- check its runner and auth, then fix or "
            "re-aim it. NEVER silence an overlapping organ: if two hunt the same region, "
            "re-aim one (L1.8, L1.25a). Exploration decays organ-by-organ and no single "
            "decay ever looks alarming, which is exactly why this number exists."),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report-only", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    rep = build_report()
    out = _ROOT / "data/exploration_status.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rep, indent=2), "utf-8")
    print(json.dumps(rep, indent=2) if args.json else
          f"exploration family (L1.32): {rep['status']} -- {rep['detail']}\n-> {out}")
    if args.report_only:
        return 0
    return 2 if rep["status"] == "DARK" else 0


if __name__ == "__main__":
    sys.exit(main())

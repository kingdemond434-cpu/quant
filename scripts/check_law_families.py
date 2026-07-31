#!/usr/bin/env python3
"""LAW-FAMILY FENCE (L1.36) -- every family of laws is enforced as a FAMILY, at military strength.

PRINCIPAL ORDER (2026-07-31): *"make timidity, anti-conservative, non-exhaustion, max aggression
— all these families — as maximum aggressive and strongest as possible in every way and enforced
strongly everywhere like strict military maximum"* + *"all these similar families in general too,
not just these mandates."*

WHY FAMILIES AND NOT JUST LAWS. The enforcement matrix already proves each law has A fence. That
is not the same as a family being enforced, and the difference is where decay lives: a family of
six laws can lose one member's fence, keep five green, and report as healthy -- the matrix sees a
per-law fact, nobody sees the FAMILY fact. Exploration proved the failure mode is real (L1.32:
six organs, three DARK, no single number would have shown it). This generalises that accounting
to every law family the desk has.

EACH FAMILY MUST SATISFY FOUR CONDITIONS, and any failure is the family's failure, not a note:
  1. COMPLETE   -- every declared member exists in the constitution.
  2. ENFORCED   -- every member maps to >=1 fence in the enforcement matrix (never prose).
  3. REACHING   -- the family reaches the organs: its ids appear in ops/principal_doctrine.txt,
                   which is injected at every organ's spawn. A law that never reaches an organ
                   cannot change behaviour, however well fenced.
  4. GUARDED    -- the family has a named FAMILY-LEVEL fence: something that fails when the
                   family as a whole degrades, not merely when one member does.

STATUSES: DECORATIVE (a member with no fence -- L2.0's exact failure) / UNREACHED (absent from
the doctrine) / UNGUARDED (no family-level fence) / INCOMPLETE (declared member missing) / OK.
Exit 2 on anything but OK: this fence is a gate, not a report.

    python scripts/check_law_families.py [--report-only] [--json]
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent

#: family -> (member law ids, family-level fence, what the family exists to prevent)
FAMILIES: dict[str, tuple[tuple[str, ...], str, str]] = {
    "aggression": (
        ("L1.21a", "L1.28", "L1.28a", "L1.28b", "L1.28c", "L1.25a", "L1.35", "L1.41"),
        "scripts/check_timidity_language.py",
        "the desk quietly doing less than it could -- every organ defaulting to the timid "
        "reading of a restraint, idling a ceiling, slowing after a null, or shipping a cadence "
        "nobody ever tried to raise"),
    "exploration": (
        ("L1.9", "L1.11a", "L1.31", "L1.32", "L1.33", "L1.34", "L1.35", "L1.40"),
        "scripts/check_exploration.py",
        "the unknown-unknown organs decaying one at a time, each decay individually "
        "unremarkable, with no number that would show it"),
    "conversion": (
        ("L1.10", "L1.28b", "L2.3", "L2.7", "L1.39"),
        "scripts/check_conversion.py",
        "findings piling up unfixed -- a desk that detects at tier-1 rate and repairs at "
        "hobbyist rate, with the spread invisible"),
    "survival": (
        ("L1.23", "L1.20", "L2.8a", "L1.38", "L1.42"),
        "scripts/run_drills.py",
        "a rail that reads healthy while being terminal, or a survival guarantee that was "
        "never actually wired to the money path"),
    "validation_honesty": (
        ("L1.6", "L1.25", "L1.29", "L1.30", "L1.43", "L1.44"),
        "scripts/check_ratchets.py",
        "the desk being confidently wrong -- a welded gate, an over-confident forecast, a "
        "book whose edges die faster than the pipeline replaces them, or a live decision "
        "steered by a frozen input it believes is current"),
    "moat": (
        ("L1.11", "L1.17", "L2.9"),
        "scripts/run_moat_backup.py",
        "irreplaceable information lost, or proprietary state built and never consumed"),
}


def build_report(root: Path | None = None) -> dict[str, Any]:
    root = root or _ROOT
    const = (root / "docs/CONSTITUTION.md").read_text("utf-8", errors="ignore")
    doctrine = (root / "ops/principal_doctrine.txt").read_text("utf-8", errors="ignore")
    try:
        matrix = json.loads((root / "data/enforcement_matrix.json").read_text("utf-8"))
        enforced = {r.get("principle"): r for r in matrix.get("rows", matrix.get("matrix", []))}
    except (OSError, ValueError):
        enforced = {}

    fams: dict[str, Any] = {}
    bad: list[str] = []
    for name, (members, fence, prevents) in FAMILIES.items():
        missing = [m for m in members if m not in const]
        unfenced = [m for m in members
                    if m in const and not (enforced.get(m, {}).get("fences")
                                           or enforced.get(m, {}).get("status") in
                                           ("ENFORCED", "STANDING", "HUMAN-ONLY"))]
        unreached = [m for m in members if m not in doctrine]
        guarded = (root / fence).exists()
        if missing:
            state = "INCOMPLETE"
        elif unfenced:
            state = "DECORATIVE"
        elif not guarded:
            state = "UNGUARDED"
        elif unreached:
            state = "UNREACHED"
        else:
            state = "OK"
        if state != "OK":
            bad.append(name)
        fams[name] = {"state": state, "members": list(members), "n_members": len(members),
                      "family_fence": fence, "family_fence_exists": guarded,
                      "missing_from_constitution": missing, "unfenced": unfenced,
                      "not_in_doctrine": unreached, "prevents": prevents}

    return {
        "generated": datetime.now(tz=UTC).isoformat(),
        "law": "L1.36 -- a family of laws is enforced as a family: complete, fenced per member, "
               "reaching every organ, and guarded by a family-level check. Per-law greenness "
               "hides family decay.",
        "status": "OK" if not bad else "FAILING",
        "n_families": len(FAMILIES),
        "n_laws_governed": sum(len(m) for m, _f, _p in FAMILIES.values()),
        "failing": bad,
        "families": fams,
        "detail": (f"{len(FAMILIES) - len(bad)}/{len(FAMILIES)} families fully enforced"
                   + (f"; failing: {', '.join(bad)}" if bad else "")),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report-only", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    rep = build_report()
    out = _ROOT / "data/law_families.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rep, indent=2), "utf-8")
    if args.json:
        print(json.dumps(rep, indent=2))
    else:
        print(f"law families (L1.36): {rep['status']} -- {rep['detail']}")
        for name, f in rep["families"].items():
            if f["state"] != "OK":
                print(f"  {f['state']:<11} {name}: missing={f['missing_from_constitution']} "
                      f"unfenced={f['unfenced']} not_in_doctrine={f['not_in_doctrine']} "
                      f"fence_exists={f['family_fence_exists']}")
        print(f"-> {out}")
    if args.report_only:
        return 0
    return 2 if rep["status"] != "OK" else 0


if __name__ == "__main__":
    sys.exit(main())

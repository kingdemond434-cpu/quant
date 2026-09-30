#!/usr/bin/env python
"""SOURCE PROVENANCE IS A RATCHET: the share of NEW candidates that name their source only rises.

Exits 1 when the compiler's last pass measured a provenance share of NEW candidates below the
floor it had recorded (`desks/mt5/data/hypotheses/provenance_floor.json`, raised by
`miner_candidate_compiler` through `libs.research.source_provenance.ratchet`, never lowered).

WHY (six-event trace, 2026-09-30): 0 of 53,174 compiled candidates carried a `source_url`, and
nothing failed. A candidate that cannot name the row it was minted from cannot be traced back to
the mechanism that justified it; a producer that stops stamping provenance breaks nothing that
anyone would see, so this fence fails on its behalf.

WHAT IS FENCED AND WHAT IS NOT. The fenced share is `provenanced` -- content hash, retrieval time,
and an external URL OR a source id (the artifact coordinate for an internal generator). The
external-URL share is published beside it and deliberately NOT fenced: the desk's own
generators read no web page, and a fence on URLs could only be satisfied by producing less.

An absent artifact is UNMEASURED and does not fail (L1.28a: a verdict, not a pass by silence).

THE CERTIFICATE HALF (2026-09-30). The #104 re-score found `certificate_provenance.json` covering
20 of the 52 current certificates. `check_certificates` fails when a birth record computed
against TODAY's certificate store leaves any current certificate without a row carrying its
source lineage (certificate -> docket row -> donation -> source row, or UNMEASURED where it ends).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.research.source_provenance import TOLERANCE  # noqa: E402

ARTIFACT = ROOT / "desks" / "mt5" / "data" / "hypotheses" / "miner_candidates.json"
FLOOR = ROOT / "desks" / "mt5" / "data" / "hypotheses" / "provenance_floor.json"
URL_FLOOR = ROOT / "desks" / "mt5" / "data" / "hypotheses" / "provenance_url_floor.json"


def _provenance_block(path: Path) -> dict | None:
    """The artifact's `provenance` block, {} when the artifact predates it, None if unreadable."""
    try:
        doc = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None
    blk = doc.get("provenance") if isinstance(doc, dict) else None
    return blk if isinstance(blk, dict) else {}


def check(artifact: Path = ARTIFACT, floor_path: Path = FLOOR) -> tuple[int, str]:
    if not artifact.exists():
        return 0, (f"UNMEASURED: {artifact.name} has not been written on this host; the hourly "
                   "compiler leg publishes it.")
    blk = _provenance_block(artifact)
    if blk is None:
        return 1, f"FAIL: {artifact} is unreadable"
    if not blk:
        return 0, ("UNMEASURED: the last compiled artifact predates the provenance block; the "
                   "next compiler pass writes it.")
    new = blk.get("new") or {}
    allc = blk.get("all") or {}
    share = new.get("share")
    try:
        floor = float(json.loads(floor_path.read_text("utf-8")).get("floor") or 0.0)
    except (OSError, ValueError, AttributeError):
        floor = float((blk.get("floor") or {}).get("prior_floor") or 0.0)
    lines = [f"new candidates: {new.get('n')} provenanced {new.get('provenanced')} "
             f"(share {share}); with an external source_url {new.get('with_source_url')}",
             f"all candidates: {allc.get('n')} provenanced {allc.get('provenanced')} "
             f"(share {allc.get('share')}); share_source_url {allc.get('share_source_url')}",
             f"floor {floor}"]
    if share is None:
        return 0, "UNMEASURED: no new candidate this pass.\n" + "\n".join(lines)
    if float(share) < floor - TOLERANCE:
        return 1, ("FAIL: the provenance share of NEW candidates fell below its floor -- a "
                   "producer stopped stamping its source, or the compiler dropped it.\n"
                   + "\n".join(lines))
    return 0, "OK\n" + "\n".join(lines)


def check_url(artifact: Path = ARTIFACT, floor_path: Path = URL_FLOOR) -> tuple[int, str]:
    """THE SECOND FLOOR: the EXTERNAL-URL (http/https) share of new candidates.

    The provenanced share above is met by construction -- an artifact coordinate counts as a
    source id -- so it cannot see a producer that stops recording the page it read. This one
    can. The floor rises to the worst of the last `window` passes and never falls
    (`source_provenance.ratchet_window`); absent anything to read, it is UNMEASURED.
    """
    if not artifact.exists():
        return 0, f"UNMEASURED: {artifact.name} has not been written on this host"
    blk = _provenance_block(artifact)
    if blk is None:
        return 1, f"FAIL: {artifact} is unreadable"
    share = (blk.get("new") or {}).get("share_source_url") if blk else None
    try:
        floor = float(json.loads(floor_path.read_text("utf-8")).get("floor") or 0.0)
    except (OSError, ValueError, AttributeError):
        floor = float(((blk or {}).get("url_floor") or {}).get("prior_floor") or 0.0)
    line = f"external-URL share of new candidates {share}; floor {floor}"
    if share is None:
        return 0, f"UNMEASURED: no external-URL share measured this pass; {line}"
    if float(share) < floor - TOLERANCE:
        return 1, ("FAIL: the external-URL share of NEW candidates fell below its floor -- a "
                   f"producer stopped recording the page it read. {line}")
    return 0, f"OK: {line}"


def check_certificates() -> tuple[int, str]:
    """The certificate half: every CURRENT certificate has a birth-record row with a source
    lineage (`certificate_provenance.coverage_gate`). Coverage below the number of current
    certificates on a record that saw today's store fails."""
    desk = ROOT / "desks" / "mt5"
    for p in (str(desk), str(desk / "research")):
        if p not in sys.path:
            sys.path.insert(0, p)
    import certificate_provenance as cp  # type: ignore[import-not-found]
    return cp.coverage_gate(cp._json(cp.RECORD), cp.certificates())


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--artifact", type=Path, default=ARTIFACT)
    ap.add_argument("--floor", type=Path, default=FLOOR)
    args = ap.parse_args()
    code, msg = check(args.artifact, args.floor)
    print("candidates: " + msg, flush=True)
    c1, m1 = check_url(args.artifact)
    print("external urls: " + m1, flush=True)
    c2, m2 = check_certificates()
    print("certificates: " + m2, flush=True)
    return max(code, c1, c2)


if __name__ == "__main__":
    raise SystemExit(main())

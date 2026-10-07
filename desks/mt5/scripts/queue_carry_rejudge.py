"""Queue every carry certificate minted on the look-ahead `family_carry` for re-judgement.

WHY (2026-10-07, EliteQuant review). `family_carry` applied TODAY's swap to every past bar, so a
certificate it produced was judged on years of bars carrying a swap nobody could have known
(CHFNOK carry: `days: 1120` on a swap tape that starts 2026-08-27). The family is now
point-in-time. Its certificates must be re-judged under the fixed family, not demoted by hand.

HOW: THE JUDGE'S OWN RE-MINT PATH, NOTHING NEW. `external_gauntlet` reads
`data/hypotheses/priority_remint.json` when its `attestation` equals the one in force:
  * the listed `cells` are judged FIRST, ahead of the never-judged tier;
  * every key in `stale_certificate_keys` leaves the survivor set and is either RETIRED with
    its new failing gates (re-judged FAIL), replaced by its new row (re-judged PASS), or held in
    `pending_rejudge` OUTSIDE the survivor set (not reached, or PENDING_HISTORY under the
    `carry_pit` patch).
The promoter's own automatic retirement then acts on the survivor set. This script only
writes the queue. It never edits a certificate, a sleeve or a cap.

Runs hourly as the `carry_rejudge` leg of hourly_cycle (`--write`), so adoption of the release
is all the box needs; by hand on the box:

    py -3 desks\\mt5\\scripts\\queue_carry_rejudge.py           # dry run: lists the queue
    py -3 desks\\mt5\\scripts\\queue_carry_rejudge.py --write    # merges into priority_remint.json

It MERGES into a queue already there for the attestation in force and does not replace a queue
written for another attestation (that one belongs to an attestation change in flight): the
report reads WAITING and the next hour tries again.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK), str(DESK / "research"), str(DESK.parents[1])):
    if _p not in sys.path:
        sys.path.insert(0, _p)

SURVIVOR_FILES = (DESK / "reports" / "UNIVERSAL_SURVIVORS.json",
                  DESK / "data" / "UNIVERSAL_SURVIVORS.canon.json")
PRIORITY = DESK / "data" / "hypotheses" / "priority_remint.json"
#: What each pass found and did; its consumer is the judge through PRIORITY.
REPORT = DESK / "reports" / "CARRY_REJUDGE.json"
#: Certificates gated before this instant were judged by the look-ahead family.
FIXED_AT = "2026-10-07T00:00:00+00:00"


def _read(path: Path) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def carry_certificates(files: tuple[Path, ...] = SURVIVOR_FILES,
                       fixed_at: str = FIXED_AT) -> dict[str, dict[str, Any]]:
    """{certificate key: {cell, symbol, spec, gated_at, source}} for carry rows gated pre-fix."""
    cutoff = datetime.fromisoformat(fixed_at)
    out: dict[str, dict[str, Any]] = {}
    for f in files:
        doc = _read(f)
        rows = (doc or {}).get("survivors") if isinstance(doc, dict) else None
        if not isinstance(rows, dict):
            continue
        for key, row in rows.items():
            if not isinstance(row, dict):
                continue
            raw = row.get("shadow_spec")
            spec: dict[str, Any] = raw if isinstance(raw, dict) else {}
            if spec.get("family") != "carry" and ".carry.p=" not in str(key):
                continue
            gated = row.get("gated_at")
            try:
                if gated and datetime.fromisoformat(str(gated)) >= cutoff:
                    continue                    # judged by the point-in-time family already
            except (TypeError, ValueError):
                pass                            # unreadable stamp: re-judge, never assume clean
            rec = out.setdefault(str(key), {"cell": row.get("cell"),
                                            "symbol": spec.get("symbol") or row.get("sym"),
                                            "spec": spec, "gated_at": gated, "source": []})
            rec["source"].append(f.name)
    return out


def build_queue(certs: dict[str, dict[str, Any]], existing: Any,
                attestation: Any) -> tuple[dict[str, Any] | None, str]:
    """The merged queue, or (None, why) when an existing queue belongs to another attestation."""
    if isinstance(existing, dict) and existing and existing.get("attestation") != attestation:
        return None, ("priority_remint.json holds a queue for ANOTHER attestation; it belongs to "
                      "an attestation change in flight and is not replaced. Re-run after it "
                      "drains.")
    base = existing if isinstance(existing, dict) else {}
    cells = {str(c) for c in (base.get("cells") or []) if c}
    stale = {str(k) for k in (base.get("stale_certificate_keys") or []) if k}
    cells |= {str(r["cell"]) for r in certs.values() if r.get("cell")}
    stale |= set(certs)
    doc = dict(base)
    doc.update({"attestation": attestation, "cells": sorted(cells),
                "stale_certificate_keys": sorted(stale)})
    doc.setdefault("reasons", {})
    if isinstance(doc["reasons"], dict):
        for k in certs:
            doc["reasons"][k] = ("carry_pit 2026-10-07: minted by the look-ahead family_carry "
                                 "(today's swap on every past bar); re-judged point-in-time")
    doc["carry_pit_queued_at"] = datetime.now(UTC).isoformat(timespec="seconds")
    return doc, "ok"


def _report(certs: dict[str, dict[str, Any]], status: str, why: str) -> None:
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps({
        "generated_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "status": status, "why": why, "fixed_at": FIXED_AT, "n_queued": len(certs),
        "consumer": "external_gauntlet.remint_cells / remint_partition via priority_remint.json",
        "certificates": {k: {"cell": r["cell"], "symbol": r["symbol"], "gated_at": r["gated_at"]}
                         for k, r in sorted(certs.items())},
    }, indent=1, default=str), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--write", action="store_true",
                    help="merge into priority_remint.json and write the report")
    ap.add_argument("--fixed-at", default=FIXED_AT)
    args = ap.parse_args(argv)
    from research.gate_policy import ATTESTATION

    certs = carry_certificates(fixed_at=args.fixed_at)
    print(f"carry certificates gated before {args.fixed_at}: {len(certs)}")
    for key, r in sorted(certs.items()):
        print(f"  {key}  sym={r['symbol']}  gated_at={r['gated_at']}  in={','.join(r['source'])}")
    if not certs:
        if args.write:
            _report(certs, "CLEAN", "no carry certificate gated before the fix is in the "
                                    "survivor set")
        return 0
    doc, why = build_queue(certs, _read(PRIORITY), ATTESTATION)
    if doc is None:
        print(f"REFUSED: {why}")
        if args.write:
            _report(certs, "WAITING", why)
        return 0
    if not args.write:
        print(f"dry run: would queue {len(doc['cells'])} cell(s), "
              f"{len(doc['stale_certificate_keys'])} stale key(s) -> {PRIORITY}")
        return 0
    PRIORITY.parent.mkdir(parents=True, exist_ok=True)
    PRIORITY.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    _report(certs, "QUEUED", "merged into priority_remint.json under the attestation in force")
    print(f"queued -> {PRIORITY}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""THE CERTIFICATE-TRUTH FENCE: one certificate lane, and every derived store agrees with it.

    python scripts/check_certificate_truth.py [--require-state] [--json]

Runs `desks/mt5/research/certificate_truth.audit` (never --apply) and fails on any FATAL
divergence: a banned-family certificate, power-cure candidate, claim, clock or live sleeve still
standing; a survivors-ledger claim the canon no longer holds; a LIVE registry row or running
shadow clock no ten-gate certificate or power-cure candidate backs; the authority file carrying no
exact attestation while clocks run; the reconciler counting certified clocks on an empty canon.

THE SPLIT BRAIN IT CATCHES (principal, 2026-09-22): `UNIVERSAL_SURVIVORS.json` n=0 while the
sleeve registry held ~693 clocks, 124 of a banned family, and four other stores each kept their
own count. Each store was internally consistent; the lie was between them, and nothing compared
them until a person did.

STATE FENCE. In CI or a fresh clone none of the stores exist; that is "no desk state", not a
broken law, so the fence passes with the verdict UNMEASURED unless `--require-state` is given
(the hourly box gate passes it, where an absent authority file IS a defect).

Exit: 2 on a fatal divergence (or, with --require-state, on no desk state); 0 clean.
"""
from __future__ import annotations

import argparse
import contextlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DESK = ROOT / "desks" / "mt5"
for _p in (str(DESK / "research"), str(DESK), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)


def measure(base: Path | None = None) -> dict[str, Any]:
    import certificate_truth as ct  # type: ignore[import-not-found]
    paths = ct.Paths.at(base or DESK)
    doc: dict[str, Any] = ct.audit(paths)
    with contextlib.suppress(OSError):
        ct._atomic(paths.out, doc)
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--require-state", action="store_true",
                    help="an absent authority file or store set is a failure (box gate)")
    ap.add_argument("--base", type=Path, default=None)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    doc = measure(a.base)
    if a.json:
        print(json.dumps(doc, indent=1, default=str))
    c = doc["canon"]
    if not doc["state_present"]:
        print("certificate truth: UNMEASURED -- no desk state on this machine"
              + (" (FAILED: --require-state)" if a.require_state else ""))
        return 2 if a.require_state else 0
    import certificate_truth as ct
    fatal = [d for d in doc["divergences"] if d["kind"] in ct.FATAL_KINDS]
    print(f"certificate truth: canon {c['status']} n={c['n']} (cure {c.get('cure_n')}) from "
          f"{c['source']}; {doc['n_divergences']} divergence(s), {len(fatal)} fatal {doc['by_kind']}")
    for d in fatal[:12]:
        print(f"   FATAL {d['kind']} {d['store']}: {d['key'][:90]}")
    if fatal:
        print("   migrate once on the box: python desks/mt5/research/certificate_truth.py --once --apply")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

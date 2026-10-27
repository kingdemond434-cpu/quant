#!/usr/bin/env python3
"""THE CLEAR RECORD THE AUTO-SIGN TRUSTS MUST BE WELL-FORMED AND ONLY EVER GROW (D-20261027-003).

    python scripts/check_seal_clears.py [--json]

With the principal sign removed, `scripts/sign_train.py` re-signs a sealed judge file only when a
CLEAR row for its exact sha256 sits in `desks/mt5/data/SEAL_CLEARS.jsonl`. The train checks the
record when it runs; this fence checks it on every push and every law-gate hour, so a garbled
row, a dropped HOLD or a rewritten history is named the moment it is committed rather than the
next time someone tries to sign. It calls the train's own parser and append-only check -- one
judgement, two clocks.

VERDICTS. PASS (the record parses and every committed version is kept at HEAD), BREACH (exit 1),
UNMEASURED in a shallow clone, which cannot see the history: a real answer about the host, and
exit 0, as for the other portable fences (L1.28a, L1.43) -- EXCEPT under CI (CI=true), whose
checkout is full by design: there UNMEASURED means the gating run lost its history, and fails.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location("sign_train", ROOT / "scripts" / "sign_train.py")
assert SPEC and SPEC.loader
sign_train = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sign_train)


def judge() -> dict[str, object]:
    try:
        head = sign_train._git("rev-parse", "HEAD")
        text = sign_train._committed_clears(head)
        cleared = sign_train.parse_clears(text)
    except ValueError as exc:
        if "shallow clone" in str(exc):
            return {"verdict": "UNMEASURED", "why": str(exc)}
        return {"verdict": "BREACH", "why": str(exc)}
    return {
        "verdict": "PASS",
        "rows": len([ln for ln in text.splitlines() if ln.strip()]),
        "cleared_paths": sorted(cleared),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    doc = judge()
    print(
        json.dumps(doc, indent=1)
        if a.json
        else f"seal clears: {doc['verdict']} -- "
        f"{doc.get('why') or str(doc.get('rows')) + ' row(s)'}"
    )
    if doc["verdict"] == "UNMEASURED" and os.environ.get("CI") == "true":
        return 1
    return 1 if doc["verdict"] == "BREACH" else 0


if __name__ == "__main__":
    sys.exit(main())

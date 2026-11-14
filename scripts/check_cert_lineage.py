#!/usr/bin/env python3
"""CERT LINEAGE FENCE -- every live window names one canon certificate.

    python scripts/check_cert_lineage.py                  # report only, exit 0
    python scripts/check_cert_lineage.py --require-state  # FAIL (exit 1) on the trading box

A LIVE row of `desks/mt5/data/sleeves.json`, every gold window `decision_core.roster` emits
(every GOLD_WINDOWS window GOLD_RETIRED does not name), and every positively sized key of
`desks/mt5/data/CERT_BOOK_LIVE.json` (the gateway sizes `gold_asia` by window name from it) must
resolve to exactly one canon survivor that IS the traded cell (`research/cert_lineage.resolve`).
NEAREST_CERT (a certificate on the window that is not the traded bracket), an AMBIGUOUS join,
UNRESOLVED, EXPLICIT_MISMATCH, SPEC_DRIFT, PENDING_REJUDGE, NOT_IN_CANON and UNMEASURED are
violations.

WHERE IT FAILS. Only with `--require-state` on the trading box (Windows), where sleeves.json,
the cert book and the canon are the box's own live state. Anywhere else (the VPS's copies, CI, a
fresh clone) it reports the same verdict and exits 0: a copy of another machine's state is not
the state a law is broken in. Unreadable state is UNMEASURED, and on the box that FAILS too --
absence never resolves to a clean verdict (L1.28a).

It sizes, retires and edits nothing. It writes desks/mt5/reports/CERT_LINEAGE.json ONLY on the
trading box (or to an explicit --out): off the box it reads another machine's copies, and writing
the tracked report there would publish a verdict about state that is not the box's.

CADENCE: the box's MT5-LawGate task (hourly) runs `run_law_gate.py --rotate`, which spends its
budget on the fences oldest-first; this fence runs when it reaches the head of that queue, and at
least once inside the 48 h rotation window or the gate reports it as never run.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "desks" / "mt5" / "research"))
sys.path.insert(0, str(ROOT))

import cert_lineage as cl  # noqa: E402


def on_trading_box() -> bool:
    return bool(cl.on_trading_box())


def judge(doc: dict[str, Any], *, require_state: bool, box: bool) -> tuple[int, str]:
    enforce = require_state and box
    if not doc.get("sleeves_readable") or not doc.get("canon_readable"):
        why = (f"UNMEASURED: sleeves readable={doc.get('sleeves_readable')}, canon readable="
               f"{doc.get('canon_readable')}")
        return (1 if enforce else 0), why
    n = int(doc.get("n_violations") or 0)
    if n == 0:
        return 0, ("OK: every LIVE row, roster gold window and sized cert-book window resolves to "
               "one canon survivor that is the traded cell")
    names = ", ".join(str(v.get("name") or (f"{v['venue']}:{v.get('key')}" if v.get("venue")
                                               else f"{v.get('kind')}:{v.get('key')}"))
                      + f" ({v.get('lineage')})" for v in doc["violations"][:8])
    return (1 if enforce else 0), (f"{'FAIL' if enforce else 'REPORT'}: {n} live window(s) "
                                    f"without certificate lineage: {names}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--require-state", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--out", type=Path, default=None,
                    help="write the report here (default: CERT_LINEAGE.json on the box only)")
    a = ap.parse_args(argv)
    doc = cl.build()
    rc, why = judge(doc, require_state=a.require_state, box=on_trading_box())
    doc["fence"] = {"rc": rc, "why": why, "enforced": a.require_state and on_trading_box()}
    dest = cl.out_path(a.out)  # the box's own report, or an explicit --out; else none
    try:
        if dest is not None:
            cl.write(doc, dest)
    except OSError as exc:
        why += f" (artifact not written: {exc})"
    print(json.dumps(doc["fence"]) if a.json else f"check_cert_lineage: {why}")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""§33 mining gate -- RECOMPUTED, never read from a flag. Exit 1 = mining suspended.

A gate that is a file is a gate anything can delete: `rm data/mining_suspended` would have
restored mining without converting a thing, which makes the whole law advisory again. So the
diggers no longer TRUST a flag -- they RUN this, and it derives the backlog from the same source
of truth the daily sweep uses. Deleting state cannot help, because there is no state to delete;
the only way to open the gate is to actually dispose of the findings, and the only way to disable
it is to edit tracked code, which shows up in a diff and in review.

    python3 scripts/mine_gate.py            # exit 0 = authorised, 1 = SUSPENDED (reason to stdout)
    python3 scripts/mine_gate.py --explain  # always exit 0; print the full §33 block

FAIL-OPEN, LOUDLY. If this script itself breaks, it exits 0 (mining proceeds) and prints a
GATE-ERROR line. The asymmetry is deliberate and costed: a day of over-mining is cheap and
recoverable, while a bug that silently freezes every digger for a week is a self-inflicted outage
of the desk's entire research intake. The failure is not swallowed -- `max_audit.check_mine_gate`
fires a defect whenever this script cannot run, so a broken gate surfaces within one sweep instead
of hiding behind either outcome.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def evaluate() -> tuple[bool, str]:
    """Return (suspended, reason). Recomputes from the docs -- reads no gate file."""
    from datetime import UTC, datetime

    from scripts.max_audit import _mine_backing, _mine_items

    from libs.research.mine_conversion import conversion_report

    items = _mine_items()
    if not items:
        return False, "no carded finds -- nothing owed"
    rep = conversion_report(items, as_of=datetime.now(UTC).date(),
                            backing=_mine_backing(), root=ROOT)
    return rep.suspend_mining, rep.verdict


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--explain", action="store_true",
                    help="print the verdict but always exit 0 (for humans, not for the shells)")
    a = ap.parse_args()
    try:
        suspended, reason = evaluate()
    except Exception as exc:
        print(f"[§33] GATE-ERROR {type(exc).__name__}: {exc} -- failing OPEN; "
              "max_audit.check_mine_gate will raise this as a defect")
        return 0
    print(f"[§33] {'SUSPENDED' if suspended else 'AUTHORISED'} -- {reason}")
    return 1 if (suspended and not a.explain) else 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""DAILY EXECUTION MONITOR -- forensics with memory, and a defect ledger that survives the morning.

`run_trade_forensics.py` already answers "what is wrong today", and answers it well. This answers
the three questions a daily reader actually needs: what is STILL wrong, what is NEW, and what came
BACK after someone believed it fixed.

Reads the forensics artifact, folds today's flags into `data/exec_defects.json`, and reports.
Places nothing, changes nothing, sizes nothing.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.execution.exec_monitor import (  # noqa: E402
    ExecHealth,
    render,
    update,
)

# THE PRODUCER'S OWN OUTPUT PATH, not a fourth spelling of it (found by the R0356 rewrite of the
# phantom-paths fence). This read `data/trade_forensics.json`, which nothing has ever written:
# run_trade_forensics.py:36,40 writes `web/trade_forensics.json` and the tracked
# `docs/research/trade_forensics_latest.json`. So this monitor reported "UNMEASURED, not a clean
# book: run scripts/run_trade_forensics.py first" no matter how many times that was done -- the
# read-without-writer class the fence exists for, invisible to it because the path was built from
# split literals. The tracked copy is the target: it survives a fresh checkout and carries the
# same schema plus `written`.
FORENSICS = ROOT / "docs/research/trade_forensics_latest.json"
LEDGER = ROOT / "data" / "exec_defects.json"

#: Map a forensics flag to a STABLE key. The flag text carries live numbers ("-37.54 bps over 23
#: trades") which change daily, so keying on the message would make every morning a NEW defect and
#: destroy the memory this script exists to provide.
_KEYS: tuple[tuple[str, str], ...] = (
    ("hold_class_bleed", r"hold-class.*bleeding"),
    ("entry_gate_regression", r"ENTRY-GATE REGRESSION"),
    ("maker_leg_asymmetry", r"maker conversion is LEG-ASYMMETRIC"),
    ("cost_exceeds_edge", r"net of fees|loses money net"),
    ("liquidation_risk", r"liquidat"),
)


def keyed_flags(flags: list[str]) -> dict[str, str]:
    """Stable key -> today's message. An unrecognised flag keeps its own text as the key.

    UNRECOGNISED FLAGS ARE KEPT, NOT DROPPED. A monitor that only tracked the five defects someone
    thought of would go quiet on the sixth -- and the sixth is the one nobody is watching for.
    """
    out: dict[str, str] = {}
    for f in flags:
        key = next((k for k, pat in _KEYS if re.search(pat, f, re.I)), None)
        out[key or f"unclassified:{f[:48]}"] = f.strip()
    return out


def load_flags(path: Path) -> tuple[list[str], str]:
    """(flags, state). state is BLOCKED when the forensics artifact is absent -- NOT 'clean'."""
    try:
        doc = json.loads(path.read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        return [], "BLOCKED"
    flags = doc.get("flags") or doc.get("defects") or []
    if isinstance(flags, int):          # some writers report a count, not the rows
        return [], "COUNT-ONLY"
    return [str(f) for f in flags], "OK"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--forensics", type=Path, default=FORENSICS)
    ap.add_argument("--ledger", type=Path, default=LEDGER)
    ap.add_argument("--fixed", nargs="*", default=[],
                    help="defect keys with a RECORDED code change -- required alongside a clean "
                         "streak before anything may be called RESOLVED")
    a = ap.parse_args()

    flags, state = load_flags(a.forensics)
    if state == "BLOCKED":
        print(f"exec-monitor: BLOCKED -- no forensics artifact at {a.forensics}. "
              "That is UNMEASURED, not a clean book: run scripts/run_trade_forensics.py first.")
        return 0

    try:
        history = json.loads(a.ledger.read_text("utf-8")).get("defects", {})
    except (OSError, json.JSONDecodeError):
        history = {}

    states = update(history, keyed_flags(flags), changes=set(a.fixed))
    health = ExecHealth(defects=tuple(states))

    a.ledger.parent.mkdir(parents=True, exist_ok=True)
    a.ledger.write_text(json.dumps({
        "ts": datetime.now(tz=UTC).isoformat(),
        "source": str(a.forensics),
        "defects": {d.key: {"status": d.status, "first_seen": d.first_seen,
                            "last_seen": d.last_seen, "occurrences": d.occurrences,
                            "clean_streak": d.clean_streak,
                            "times_regressed": d.times_regressed, "detail": d.detail}
                    for d in states},
        "note": ("RESOLVED requires consecutive clean readings AND a recorded change. A quiet day "
                 "on a sporadic book is an absence of evidence, and letting absence close a "
                 "money-path defect is the desk's most-repeated error aimed at its most expensive "
                 "target."),
    }, indent=1), "utf-8")

    print(render(health))
    print(f"  ledger: {a.ledger}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

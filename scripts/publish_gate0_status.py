#!/usr/bin/env python3
"""PUBLISH GATE 0 READINESS TO THE DASHBOARD -- the VPS-visibility channel this session needed.

THE GAP THIS CLOSES. A Claude Code container gets a fresh clone every session and cannot reach
the VPS by SSH (outbound is HTTPS-only through the session's egress proxy) or read data/ (gitignored,
box-local). Every "is Gate 0 ready" and "is net_of_fees_positive true" question this session asked
was answerable only by guessing or asking the principal to paste command output by hand -- even
though dash.quanttt.xyz already serves web/*.json over HTTPS and a container CAN fetch that.
web/discovery.json and web/trade_forensics.json already prove the channel works; nothing published
Gate 0's own readiness board through it, so the one artifact most worth checking before funding
was the one thing still invisible from outside the box.

WHAT THIS DOES: republishes data/gate0_readiness.json (scripts/check_gate0_ready.py, already
hourly) to web/gate0_status.json, stamped with the source artifact's age. It computes nothing --
same verdicts, same rows, same "BLOCKED-UNKNOWN is never READY" rule -- because a publisher that
recomputes is a second implementation of the same question, and two implementations are how they
quietly disagree (the exact class of bug this session already found once in check_build_standard.py
and _scheduled_parent).

WHY THE AGE STAMP IS NOT DECORATION. A dashboard rendering an 8-hour-old readiness board as
"right now" is the 2026-08-05 stale-artifact failure with a nicer font (see publish_pipeline.py,
which this mirrors). Any consumer -- human or another Claude session -- reads source_age_h before
trusting a row.

    python scripts/publish_gate0_status.py [--json]
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path("/home/quant/quant-platform")
if not _ROOT.exists():
    _ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from libs.ops.lawful import guard as _law_guard  # noqa: E402

_SRC = "data/gate0_readiness.json"
_OUT = "web/gate0_status.json"


def _age_h(p: Path) -> float | None:
    try:
        return round((datetime.now(tz=UTC).timestamp() - p.stat().st_mtime) / 3600.0, 1)
    except OSError:
        return None


def publish(root: Path | None = None, *, now: datetime | None = None) -> dict[str, Any]:
    root = root or _ROOT
    now = now or datetime.now(tz=UTC)
    src = root / _SRC
    age = _age_h(src)

    try:
        board = json.loads(src.read_text("utf-8"))
    except (OSError, ValueError) as exc:
        doc = {"published": now.isoformat(), "status": "UNMEASURED",
               "why": f"{_SRC} unreadable ({type(exc).__name__}: {exc})",
               "source_age_h": age, "rows": []}
    else:
        doc = {
            "published": now.isoformat(),
            "status": "OK",
            "source_age_h": age,
            "stale_warning": (age is not None and age > 3.0),
            # check_gate0_ready.py runs hourly; >3x that interval unread means the schedule
            # itself has gone quiet, not just "a bit behind".
            "gate": board.get("gate"), "ready": board.get("ready"),
            "n_ready": board.get("n_ready"), "n_criteria": board.get("n_criteria"),
            "desk_owes": board.get("desk_owes"), "principal_owes": board.get("principal_owes"),
            "rows": board.get("rows", []),
        }

    out = root / _OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2), "utf-8")
    return doc


def main(argv: list[str] | None = None) -> int:
    _law_guard()
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    doc = publish()
    if args.json:
        print(json.dumps(doc, indent=2))
    else:
        print(f"gate0 status published: {doc['status']}, source age "
              f"{doc.get('source_age_h')}h, ready={doc.get('ready')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""RECORD EVERY REFUSED TOOL CALL OF ONE AGENT PASS, SO A SKIP COUNTS AS MISSED.

    python scripts/record_agent_denials.py --stream <stream.jsonl> --ledger <ledger.jsonl>
        [--log <human log>] [--review <TIER1_BREADTH_REVIEW.json>] [--started-at <iso>]
        [--surface cro_cycle] [--lane noon] [--agent claude] [--date 2026-09-30]

Called by desks/mt5/scripts/Run-DeskCycle.ps1 (task MT5-CycleNoon) after the claude lane exits.
It reads the `claude -p --output-format stream-json --verbose` stream the launcher teed to disk,
and:

  1. appends the pass's final result text to the human log, so the log reads as it did when the
     lane ran in text mode;
  2. appends one row per refused tool call to the ledger:
     `{"verdict":"UNMEASURED","counts_as":"MISSED","reason":"permission_denied","tool":..,
       "input_summary":..,"duties":[..]}` (the summary is capped and scrubbed of secrets paths
     and key-shaped strings);
  3. marks each duty a refused step served as MISSED in the review THIS pass wrote.

It prints one JSON line (`denials`, `changed_duties`, `result_seen`, `malformed`) for the launcher
and ALWAYS exits 0 when it could read the stream: the pass's own exit code is the task's truth,
and a recorder that failed the task would hide the pass's result behind its own. A stream it
cannot read at all exits 2, which the launcher logs as UNMEASURED.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.ops.agent_denials import (  # noqa: E402
    append_jsonl,
    denial_rows,
    parse_stream,
    score_review,
)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--stream", required=True, type=Path)
    ap.add_argument("--ledger", required=True, type=Path)
    ap.add_argument("--log", type=Path)
    ap.add_argument("--review", type=Path)
    ap.add_argument("--started-at")
    ap.add_argument("--surface", default="cro_cycle")
    ap.add_argument("--lane")
    ap.add_argument("--agent")
    ap.add_argument("--date")
    a = ap.parse_args(argv)

    try:
        text = a.stream.read_text("utf-8", errors="replace")
    except OSError as e:
        print(json.dumps({"status": "UNMEASURED", "why": f"stream unreadable: {type(e).__name__}",
                          "counts_as": "MISSED"}))
        return 2
    summary = parse_stream(text.splitlines())
    rows = denial_rows(summary, surface=a.surface, lane=a.lane, agent=a.agent, date=a.date,
                       pass_started_at=a.started_at)
    append_jsonl(a.ledger, rows)

    if a.log is not None:
        a.log.parent.mkdir(parents=True, exist_ok=True)
        with a.log.open("a", encoding="utf-8") as f:
            f.write("---- agent result ----\n")
            f.write((summary.result_text or "(no result event: the stream ended early)") + "\n")
            for r in rows:
                f.write(f"PERMISSION DENIED (counts as MISSED; duties {','.join(r['duties'])}): "
                        f"{r['tool']}: {r['input_summary']}\n")

    scored: dict[str, object] = {"applied": False}
    if a.review is not None:
        scored = score_review(a.review, rows, a.started_at)

    print(json.dumps({
        "status": "RECORDED", "denials": len(rows), "result_seen": summary.result_seen,
        "malformed": summary.malformed, "changed_duties": scored.get("changed", []),
        "review_applied": scored.get("applied", False), "review_why": scored.get("why"),
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

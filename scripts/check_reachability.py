#!/usr/bin/env python3
"""CI gate: every capability must reach a decision, or be declared as advisory by name.

    python scripts/check_reachability.py            # exit 1 on any fatal finding
    python scripts/check_reachability.py --status   # also write the generated-truth reports

Fails the build on DEAD_PRODUCER, DEAD_CONSUMER, ADVISORY_ONLY, UNMEASURED_AUTHORITY and
MISSING_MODULE. UNDECLARED paths are printed as warnings: they are the graph drifting from the
code, which is the next commit's problem rather than this one's, but they are never silent.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from libs.ops.capability_graph import check, generate_status  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--status", action="store_true", help="write CAPABILITY_STATUS/LIVE_REACHABILITY")
    a = ap.parse_args()
    st = generate_status() if a.status else check()
    fatal = st["fatal"]
    warn = [f for f in st["findings"] if f not in fatal]
    print(f"capability graph: {st['nodes']} nodes, {st['artifacts']} artifacts, "
          f"{len(fatal)} fatal, {len(warn)} warnings")
    for f in fatal:
        print(f"  FATAL {f['check']:22s} {f['node']:26s} {f['artifact']}  -- {f['why']}")
    for f in warn[:40]:
        print(f"  warn  {f['check']:22s} {f['node']:26s} {f['artifact']}  -- {f['why']}")
    if a.status and st.get("stale"):
        for s in st["stale"]:
            print(f"  STALE {s['node']:26s} {s['artifact']}  -- {s['why']}")
    return 1 if fatal else 0


if __name__ == "__main__":
    raise SystemExit(main())

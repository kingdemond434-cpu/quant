#!/usr/bin/env python3
"""Ratcheting branch-coverage floor for the MT5 MONEY PATH -- the files that move capital.

    pytest desks/mt5/tests --cov=desks/mt5/mt5desk --cov=desks/mt5/research --cov-branch \\
           --cov-report=json:mt5cov.json
    python scripts/check_mt5_coverage_floor.py --report mt5cov.json

WHY A SEPARATE FLOOR. The repo's headline coverage measures `libs`, and its "money path" list
names the retired crypto executor. The MT5 gateway, sizing, promoter and allocator bridge --
the code that actually places orders -- were outside every coverage number the CI reported. A
green gate that measures the wrong heart is worse than no gate, because it is believed.

THE FLOOR RATCHETS. Per money-path file, the highest branch coverage ever recorded is stored and
a run may not fall more than TOLERANCE below it. Nothing here sets a target by fiat; the target
is what the desk has already achieved, and the only direction allowed is up.
"""
from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HIGH_WATER = ROOT / "desks" / "mt5" / "data" / "coverage_high_water.json"
TOLERANCE = 0.02

#: The MT5 money path, by file. Every one either places an order, sizes one, decides what may
#: trade, or feeds a number the sizer trusts.
MONEY_PATH = (
    "desks/mt5/mt5desk/gateway.py",
    "desks/mt5/mt5desk/engine.py",
    "desks/mt5/mt5desk/independence.py",
    "desks/mt5/mt5desk/markout.py",
    "desks/mt5/research/pf_allocator.py",
    "desks/mt5/research/promoter.py",
    "desks/mt5/research/state_admission_run.py",
    "desks/mt5/research/session_phase.py",
    "desks/mt5/research/allocator_attribution.py",
)


def _branch_pct(entry: dict) -> float | None:
    s = entry.get("summary") or {}
    if "percent_covered" in s:
        return float(s["percent_covered"]) / 100.0
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", default="mt5cov.json")
    ap.add_argument("--tolerance", type=float, default=TOLERANCE)
    a = ap.parse_args()
    try:
        cov = json.loads(Path(a.report).read_text("utf-8"))
    except (OSError, ValueError) as exc:
        print(f"coverage report unreadable: {exc}")
        return 1
    files = cov.get("files") or {}
    try:
        hw = json.loads(HIGH_WATER.read_text("utf-8"))
    except (OSError, ValueError):
        hw = {}
    failures, new_hw = [], dict(hw)
    print(f"{'file':52s} {'now':>7s} {'high':>7s}")
    for rel in MONEY_PATH:
        entry = next((v for k, v in files.items() if k.replace("\\", "/").endswith(rel)), None)
        if entry is None:
            # GATEWAY CANNOT BE IMPORTED OFF WINDOWS (MetaTrader5). Its tests read the source.
            # Absent from the report is reported, never scored as zero and never skipped silently.
            print(f"{rel:52s} {'absent':>7s} {'-':>7s}   (not imported on this host)")
            continue
        now = _branch_pct(entry)
        if now is None:
            continue
        prev = float(hw.get(rel, 0.0))
        flag = ""
        if now + 1e-9 < prev - a.tolerance:
            failures.append((rel, now, prev))
            flag = "  <-- REGRESSION"
        if now > prev:
            new_hw[rel] = round(now, 4)
        print(f"{rel:52s} {now:7.1%} {prev:7.1%}{flag}")
    if new_hw != hw:
        HIGH_WATER.parent.mkdir(parents=True, exist_ok=True)
        new_hw["_updated"] = datetime.now(tz=UTC).isoformat()
        HIGH_WATER.write_text(json.dumps(new_hw, indent=1), "utf-8")
    if failures:
        print(f"{len(failures)} money-path file(s) fell more than {a.tolerance:.0%} below their "
              "high-water mark")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

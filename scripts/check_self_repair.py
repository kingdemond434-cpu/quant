#!/usr/bin/env python3
"""THE SELF-REPAIR FENCE: a known defect class may not lose its detector, its repair or its clock.

    python scripts/check_self_repair.py [--json] [--update]

Three failures, and only three:

  * UNCOVERED. A class with no detector, no repair AND no owner is a defect this desk has written
    down and done nothing about. Naming it without owning it is worse than not naming it.
  * SILENT DETECTOR. A class whose detector has not produced inside its own declared window. A
    stopped detector reads exactly like a clean class, which is the failure mode this whole
    registry exists to make impossible (L1.28a).
  * THE MANUAL COUNT ROSE. The number of classes found by hand ratchets DOWN. It rising means a
    class lost its detector, or a new class was declared without one -- either way a human is
    back in the loop, which is what "it never needs builders again" forbids.

The floor lives in `docs/research/self_repair_floor.json` and is lowered automatically whenever
the manual count falls; it is never raised by this fence.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
for _p in (str(ROOT / "desks" / "mt5" / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

FLOOR = ROOT / "docs" / "research" / "self_repair_floor.json"


def measure(root: Path | None = None, *, require: bool = False) -> dict[str, Any]:
    import self_repair_registry as reg  # type: ignore[import-not-found]

    base = Path(root or ROOT)
    doc: dict[str, Any] = reg.measure(base)
    # HOST-AWARE, LIKE THE ATTESTATION. A detector's silence is judgeable only where the detector
    # is supposed to run. On the build box every MT5 clock is disabled BY DESIGN, so a stale
    # artifact there is a fact about the machine, not about the class -- and a fence that is red
    # on the day it is built gets switched off (L1.43). `--require-state` arms the half that the
    # box's own law gate runs, which is where silence IS the defect.
    try:
        gw = (base / "desks" / "mt5" / "data" / "gateway_state.json").stat().st_mtime
        import time as _t
        trading = (_t.time() - gw) < 3 * 3600
    except OSError:
        trading = False
    floor_path = base / "docs" / "research" / "self_repair_floor.json"
    try:
        floor = json.loads(floor_path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        floor = {}
    was = floor.get("manual") if isinstance(floor, dict) else None

    failures: list[str] = []
    for r in doc["rows"]:
        if not r["detector_present"] and not r["repair_declared"] \
                and r["owner"] == "department:meta":
            failures.append(f"{r['key']}: no detector, no repair and no owner -- a class named "
                            f"and abandoned is worse than one never named")
        if r["detector_present"] and r["bucket"] == reg.UNMEASURED and (trading or require):
            failures.append(f"{r['key']}: {r['why']}")
    if isinstance(was, int) and doc["manual"] > was:
        failures.append(f"the manual count rose {was} -> {doc['manual']}: a class lost its "
                        f"detector, or a new class was declared without one. It ratchets DOWN.")
    doc["trading_host"] = trading
    doc["floor_manual"] = was if isinstance(was, int) else reg.UNMEASURED
    doc["failures"] = failures
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", type=Path, default=None)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--require-state", action="store_true",
                    help="a silent detector is a failure here (the box's law gate)")
    ap.add_argument("--update", action="store_true", help="record today's manual count as floor")
    a = ap.parse_args(argv)
    base = Path(a.root or ROOT)
    v = measure(base, require=bool(a.require_state))
    c = v["census"]
    if a.json:
        print(json.dumps({k: x for k, x in v.items() if k != "rows"}, indent=1, default=str))
    print(f"self-repair: {v['classes']} defect class(es) -- AUTOMATED {c['AUTOMATED']}, "
          f"DETECTED {c['DETECTED']}, MANUAL {c['MANUAL']} (floor {v['floor_manual']}), "
          f"UNMEASURED {c['UNMEASURED']}"
          + ("" if v["trading_host"] else " -- not the trading host, so detector silence here is "
                                          "UNMEASURED, not a defect"))
    if a.update:
        path = base / "docs" / "research" / "self_repair_floor.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        keep = min(v["manual"], v["floor_manual"]) if isinstance(v["floor_manual"], int) \
            else v["manual"]
        path.write_text(json.dumps({
            "schema": "self_repair_floor/1", "at": v["generated_at"], "manual": keep,
            "note": "the count of defect classes still found by hand. It may only FALL.",
        }, indent=1), encoding="utf-8")
        print(f"   floor written: manual {keep}")
        return 0
    for f in v["failures"]:
        print(f"   FAILED {f}")
    return 2 if v["failures"] else 0


if __name__ == "__main__":
    raise SystemExit(main())

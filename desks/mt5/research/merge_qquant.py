"""merge_qquant: final REAL3 merge — runs only after BOTH fragility (REAL2) and the
qquant universal gauntlet (QQUANT_GATES.json) are done, then writes the complete
REAL3 verdict (REAL && DSR && fragility && all 10 universal gates) into
REAL_SURVIVORS.json and the aggregate counts into QQUANT_GATES.json summary.
"""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
REPORTS = BASE / "reports"


def wait_for(marker: str, name: str) -> None:
    for _ in range(600):
        if (REPORTS / marker).exists():
            print(f"merge: {name} done", flush=True)
            return
        time.sleep(30)
    print(f"merge: TIMEOUT waiting for {name}", flush=True)
    sys.exit(2)


def main() -> int:
    wait_for("DONE_fragility", "fragility")
    wait_for("DONE_qquant_gates", "qquant_gates")
    sv = json.loads((REPORTS / "REAL_SURVIVORS.json").read_text("utf-8"))
    qq = json.loads((REPORTS / "QQUANT_GATES.json").read_text("utf-8"))
    rows = sv["real_survivors"]
    v_by_id: dict[tuple, dict] = {}
    for v in qq["verdicts"]:
        if "id" not in v:
            continue
        parts = v["id"].split()
        sym, win, state = parts[0], parts[-2], parts[-1]
        fam = parts[1] if parts[1] != "breakout" else None
        side = parts[2]
        v_by_id[(sym, fam, side, win, state, v["hunt"])] = v
    n3 = 0
    for r in rows:
        key = (r["sym"], r.get("fam"), r.get("side") or "LONG", r["win"], r["state"], r["hunt"])
        v = v_by_id.get(key)
        if v is None:
            r["qquant_gates"] = None
            r["REAL3"] = False
            continue
        r["qquant_gates"] = {
            "passed": bool(v.get("passed")),
            "stages": v.get("stages", {}),
        }
        r["REAL3"] = bool(v.get("passed"))
        if r["REAL3"]:
            n3 += 1
    gate_counts: dict[str, int] = {}
    for v in qq["verdicts"]:
        for name, s in v.get("stages", {}).items():
            if not s["passed"]:
                gate_counts[name] = gate_counts.get(name, 0) + 1
    sv["qquant_universal_gates"] = {
        "gate_list": qq["gates"],
        "n_trials": qq["n_trials"],
        "program_level": qq["program_level"],
        "gate_fails": gate_counts,
        "real2": int(sum(1 for r in rows if r.get("REAL2"))),
        "real3": n3,
    }
    sv["total_real3"] = n3
    sv["swept_at"] = datetime.now(timezone.utc).isoformat()
    (REPORTS / "REAL_SURVIVORS.json").write_text(
        json.dumps(sv, indent=2, default=str), encoding="utf-8")
    qq["real3_summary"] = {"real2": int(sv["qquant_universal_gates"]["real2"]), "real3": n3}
    (REPORTS / "QQUANT_GATES.json").write_text(
        json.dumps(qq, indent=2, default=str), encoding="utf-8")
    (REPORTS / "DONE_merge").write_text(datetime.now(timezone.utc).isoformat(),
                                        encoding="utf-8")
    print(f"\nMERGE COMPLETE: REAL2={sv['qquant_universal_gates']['real2']} "
          f"REAL3={n3} of {len(rows)}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
"""real_survivors: one canonical, fully-validated survivor list across ALL hunts.

Every candidate passes, at once:
  1. battery gate (n, t, deflation, PF, maxDD, 2x costs)            [already in each hunt]
  2. walk-forward: mean OOS fold expectancy > 0 AND >=2 of 3 folds positive
  3. PBO/CPCV of its hunt population (from pbo_cpcv_<hunt>.json)
  4. machinery placebo verdict (CLEAN = pipeline does not fabricate alpha)
  5. hunt completion marker (DONE_<hunt> must exist)

Output: reports/REAL_SURVIVORS.json (full evidence per survivor + per-hunt summary)
and a printed table. Re-run anytime; pending hunts are reported as pending.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

BASE = Path(__file__).resolve().parent.parent
REPORTS = BASE / "reports"
HUNTS = ["hunt12.json", "hunt13.json", "hunt15.json", "hunt16.json"]


def load(hf: str) -> dict | None:
    p = REPORTS / hf
    if not p.exists():
        return None
    return json.loads(p.read_text("utf-8"))


def main() -> int:
    placebo = None
    if (REPORTS / "placebo_test.json").exists():
        placebo = json.loads((REPORTS / "placebo_test.json").read_text("utf-8"))
    rows = []
    summaries = {}
    for hf in HUNTS:
        data = load(hf)
        if data is None:
            summaries[hf] = {"status": "not run yet"}
            continue
        done = (REPORTS / f"DONE_{hf.split('.')[0]}").exists()
        pbo_f = REPORTS / f"pbo_cpcv_{hf}"
        pbo = json.loads(pbo_f.read_text("utf-8")) if pbo_f.exists() else None
        survivors = data.get("survivors", [])
        passed = 0
        for s in survivors:
            wf = np.array([float(x) for x in s.get("wf", []) if x == x], dtype=float)
            ok_wf = bool(len(wf) == 3 and np.all(wf > 0))
            ok_stress = bool(s.get("exp_stress", 0.0) is not None and s.get("exp_stress", 0.0) > 0)
            ok_pbo = bool(pbo is not None and pbo["pbo"] < 0.30)
            ok_placebo = bool(placebo is not None and placebo["verdict"] == "CLEAN")
            ok_done = bool(done)
            row = dict(hunt=hf, sym=s["sym"], fam=s.get("fam", "SESSION_RANGE_BREAKOUT"),
                       side=s.get("side", "LONG"), win=s.get("win", ""),
                       state=s.get("state", ""), n=s["n"], exp=s["exp"], t=s["t"],
                       defl=s["defl"], pf=s["pf"], maxdd=s["maxdd"],
                       exp_stress=s.get("exp_stress", None),
                       wf=[round(float(x), 3) if x == x else None for x in s.get("wf", [])],
                       wf_ok=ok_wf, pbo=round(pbo["pbo"], 4) if pbo else None,
                       pbo_ok=ok_pbo, placebo=placebo["verdict"] if placebo else None,
                       hunt_done=done)
            row["REAL"] = bool(ok_wf and ok_stress and ok_pbo and ok_placebo and ok_done)
            rows.append(row)
            passed += int(row["REAL"])
        summaries[hf] = {"status": "COMPLETE" if done else "RUNNING",
                         "survivors": len(survivors), "real": passed,
                         "pbo": round(pbo["pbo"], 4) if pbo else None}
    real = [r for r in rows if r["REAL"]]
    out = {
        "placebo_verdict": placebo["verdict"] if placebo else None,
        "summaries": summaries,
        "real_survivors": real,
        "total_real": len(real),
        "swept_at": datetime.now(timezone.utc).isoformat(),
    }
    (REPORTS / "REAL_SURVIVORS.json").write_text(json.dumps(out, indent=2, default=str),
                                                 encoding="utf-8")
    print(f"\n{'hunt':<16} {'status':<9} {'surv':>4} {'REAL':>4} {'PBO':>6}")
    for hf, s in summaries.items():
        print(f"{hf:<16} {s['status']:<9} {s.get('survivors', 0):>4} {s.get('real', 0):>4} "
              f"{str(s.get('pbo')):>6}")
    print(f"\nTOTAL REAL SURVIVORS: {len(real)}\n")
    for r in real:
        print(f"  {r['sym']:<8} {r['fam']:<28} {r['side']:<5} {r['win']:<10} {r['state']:<11} "
              f"n={r['n']:>4} exp={r['exp']:+.3f} t={r['t']:5.2f} PF={r['pf']:4.2f} "
              f"wf={r['wf']} PBO={r['pbo']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
"""run_hunt18.py — single-experiment executor for the autonomous research loop.

Loads ONE experiment spec from data/research_queue.json (by id), runs the full
institutional battery (run_hunt17 battery: n>60, defl t>2, PF>1.05, maxDD>-30R,
3-fold WF all>0, 2x cost stress exp>0 & t>1.5) over all universe symbols for that
family/side/params overlay on H4+D1 bars, writes reports/hunt18_<id>.json, appends
the permanent registry record, and runs diagnosis + descendant generation.

No human handoff: the research_loop supervises the queue; the supervisor guards
this script; the registry prevents rediscovery.

Usage: python research/run_hunt18.py <experiment_id>
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from mt5desk import families  # noqa: E402
from mt5desk.engine import Costs  # noqa: E402
from registry import append_hunt_record  # noqa: E402
from run_hunt17 import (FAMILIES, PARAMS, battery, resample)  # noqa: E402

BASE = Path(__file__).resolve().parent.parent
UNI = BASE / "data" / "universe"
REPORTS = BASE / "reports"
QUEUE = BASE / "data" / "research_queue.json"


def load_queue() -> list[dict]:
    if not QUEUE.exists():
        return []
    try:
        return json.loads(QUEUE.read_text("utf-8"))
    except Exception:
        return []


def save_queue(q: list[dict]) -> None:
    QUEUE.write_text(json.dumps(q, indent=2, default=str), encoding="utf-8")


def main() -> int:
    exp_id = sys.argv[1] if len(sys.argv) > 1 else ""
    q = load_queue()
    item = next((it for it in q if it.get("id") == exp_id), None)
    if item is None:
        print(f"experiment {exp_id!r} not found in queue", flush=True)
        return 2
    if item.get("status") not in ("QUEUED", "RUNNING"):
        print(f"experiment {exp_id} status {item.get('status')} — skip", flush=True)
        return 0
    item["status"] = "RUNNING"
    item["started_at"] = datetime.now(timezone.utc).isoformat()
    save_queue(q)

    meta = json.loads((UNI / "universe.json").read_text("utf-8"))
    fam = item["family"]
    if fam not in FAMILIES:
        print(f"family {fam} not available", flush=True)
        item["status"] = "FAILED_SPEC"
        save_queue(q)
        return 2
    fn = FAMILIES[fam]
    params = dict(item.get("params", {}))
    # overlay: family default params unless the spec overrides
    p0 = dict(PARAMS[fam][0])
    for k, v in item.get("param_overrides", {}).items():
        p0[k] = v
    params = {**p0, **params}
    side = 1 if item.get("side", "LONG") == "LONG" else -1

    results = []
    tprint = lambda *a: print(*a, flush=True)  # noqa: E731
    tprint(f"hunt18 [{exp_id}]: {fam} {'LONG' if side > 0 else 'SHORT'} {params} "
           f"geneology={item.get('geneology_id')}")
    for sym in sorted(meta):
        fp = UNI / f"{sym}_H1.parquet"
        if not fp.exists():
            continue
        h1 = families._h1(pd.read_parquet(fp))
        h4, d1 = resample(h1)
        m = meta[sym]
        costs = Costs(spread_per_lot=0.48 if sym == "XAUUSD" else max(
            m["median_spread_pts"] * m["tick_size"] * m["contract_size"], 0.05),
            commission_per_lot=3.50, contract_oz=m["contract_size"])
        sigs = fn(h4, d1, side, **params)
        if len(sigs) < 60:
            continue
        b = battery(h4, sigs, costs)
        wfs = " ".join(f"{x:+.3f}" if x == x else "  nan" for x in b["wf"])
        tprint(f"{sym:>8} {b['n']:5d} {b['exp']:+7.3f} {b['t']:5.2f} {b['defl']:5.2f} "
               f"{b['pf']:5.2f} {b['maxdd']:7.1f} "
               f"{'PASS' if b['gate'] else 'fail':>5}  WF[{wfs}]")
        results.append(dict(sym=sym, fam=fam, side="LONG" if side > 0 else "SHORT",
                            param=item.get("param_overrides", {}), **b))
    report = {
        "experiment_id": exp_id, "hypothesis": item.get("hypothesis"),
        "geneology_id": item.get("geneology_id"), "family": fam,
        "side": "LONG" if side > 0 else "SHORT", "params": params,
        "survivors": [r for r in results if r["gate"]],
        "all": results,
        "swept_at": datetime.now(timezone.utc).isoformat(),
    }
    (REPORTS / f"hunt18_{exp_id}.json").write_text(
        json.dumps(report, indent=2, default=str), encoding="utf-8")
    append_hunt_record(f"hunt18_{exp_id}", item, report)
    tprint(f"\n{len(report['survivors'])} survivors of {len(results)} tests")
    (REPORTS / f"DONE_loop_{exp_id}").write_text(report["swept_at"], encoding="utf-8")
    item["status"] = "DONE"
    item["finished_at"] = report["swept_at"]
    item["n_survivors"] = len(report["survivors"])
    save_queue(q)
    return 0


if __name__ == "__main__":
    sys.exit(main())
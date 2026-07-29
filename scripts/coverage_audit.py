"""COVERAGE AUDIT -- one honest number per surface. "Everything is covered" is a claim; this is a
measurement.

Six surfaces, each with a different denominator, because "coverage" means something different at
every layer and quoting the best one is how a desk fools itself.
"""
from __future__ import annotations

import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent


def _j(p, d=None):
    try:
        return json.loads((ROOT / p).read_text("utf-8"))
    except Exception:  # blind-except intentional (BLE001)
        return d


rows = []

# 1 PANEL CODE COVERAGE
sh = _j("data/audit_shards.json", {})
if sh:
    rows.append(("panel: merit code reviewed", sh.get("union_coverage_pct", 0), 100.0,
                 f"{sh.get('tier1_files',0)+sh.get('tier2_files',0)} files; "
                 f"{sh.get('inert_withheld',0)} INERT withheld by design"))

# 2 DQS COLLECTOR COVERAGE -- how many data sources are health-scored at all?
dv = _j("data/data_vitals.json", {})
scored = {c["source"] for c in dv.get("collectors", [])}
all_data = {p.name for p in (ROOT / "data").glob("*.jsonl")}
extra = len([c for c in dv.get("collectors", []) if c["source"] not in all_data])
rows.append(("data: sources health-scored",
             len(scored) / max(len(all_data) + extra, 1) * 100, 100.0,
             f"{len(scored)} scored of {len(all_data)} jsonl + {extra} live sources"))

# 3 MEASUREMENT GATE COVERAGE
mg = _j("data/measurement_gate.json", {})
gated = set(mg.get("datasets", {}))
rows.append(("data: datasets gated", len(gated) / max(len(all_data), 1) * 100, 100.0,
             f"{len(gated)} gated of {len(all_data)} jsonl files"))

# 4 DEPENDENCY GRAPH COVERAGE
dg = _j("data/dependency_graph.json", {})
nodes = dg.get("nodes", [])
unmon = [n for n in nodes if n.get("state") == "UNMONITORED"]
rows.append(("data: graph nodes monitored",
             (len(nodes) - len(unmon)) / max(len(nodes), 1) * 100, 100.0,
             f"{len(unmon)} UNMONITORED of {len(nodes)} declared sources"))

# 5 CONSTRUCTION / FEATURE-SPACE COVERAGE  -- the real research frontier
fl = _j("data/feature_library.json", {})
props = fl.get("n_proposals", 0)
tested = 3
rows.append(("research: construction space tested",
             tested / max(props + tested, 1) * 100, 100.0,
             f"{tested} tested of {props + tested} enumerated cells"))

# 6 NORTH STAR -- alpha pipeline conversion
al = _j("data/alpha_lifecycle.json", {})
alphas = al.get("alphas", [])
deployed = sum(1 for a in alphas if a.get("state") in ("SMALL_CAPITAL", "SCALED", "MONITORED"))
rows.append(("alpha: reached capital", deployed / max(len(alphas), 1) * 100, 100.0,
             f"{deployed} deployed of {len(alphas)} tracked alphas"))

print("=== COVERAGE AUDIT -- one honest number per surface ===")
print("    different denominators; quoting the best one is how a desk fools itself\n")
print(f"  {'surface':<36}{'actual':>9}{'target':>9}   detail")
for name, act, tgt, detail in rows:
    flag = "" if act >= 99.5 else "   <-- GAP"
    print(f"  {name:<36}{act:>8.1f}%{tgt:>8.0f}%   {detail}{flag}")

full = [r for r in rows if r[1] >= 99.5]
print(f"\n  {len(full)}/{len(rows)} surfaces at 100%.")
print("  Anything below is a real gap, not a rounding artifact. 'Everything is covered' is")
print("  false unless every line above reads 100.")

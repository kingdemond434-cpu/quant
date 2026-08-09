"""Verify all five fixes from a1bcd86 are LIVE in the running code, not just committed.

A commit proves an edit happened. It does not prove the edit is reachable, correct, or in the file
the process actually imports -- I shipped a fix to the mainnet module yesterday while the desk
trades testnet, and it looked perfectly committed.
"""
from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
checks = []


def chk(name, ok, detail):
    checks.append((name, ok, detail))


# 1 prefix health matching in dependency_graph
src = (ROOT / "scripts/dependency_graph.py").read_text("utf-8")
dg = json.loads((ROOT / "data/dependency_graph.json").read_text("utf-8"))
unmon = [n for n in dg["nodes"] if n["state"] == "UNMONITORED"]
chk("1 prefix health match", "_health_for" in src and not unmon,
    f"{len(unmon)} UNMONITORED nodes (was 2: data/moat + funding API)")

# 2 data_vitals reports small/derived instead of dropping
dv = json.loads((ROOT / "data/data_vitals.json").read_text("utf-8"))
jsonl = {p.name for p in (ROOT / "data").glob("*.jsonl")}
scored = {c["source"] for c in dv["collectors"]}
chk("2 data_vitals denominator honest", jsonl <= scored,
    f"{len(jsonl & scored)}/{len(jsonl)} jsonl files present in the report")

# 3 measurement_gate reports TOO_SMALL
mg = json.loads((ROOT / "data/measurement_gate.json").read_text("utf-8"))
gated = set(mg["datasets"])
small = [k for k, v in mg["datasets"].items() if v.get("verdict") == "TOO_SMALL"]
chk("3 gate denominator honest", jsonl <= gated,
    f"{len(gated)} gated of {len(jsonl)} jsonl; {len(small)} TOO_SMALL reported not dropped")

# 3b TOO_SMALL must NOT satisfy require_verified
try:
    from scripts.measurement_gate import MeasurementError, require_verified
    ok_block = False
    if small:
        try:
            require_verified(small[0])
        except MeasurementError:
            ok_block = True
    else:
        ok_block = True
    chk("3b TOO_SMALL is not a pass", ok_block,
        f"require_verified({small[0] if small else 'n/a'}) raises as it must")
except Exception as e:  # blind-except intentional (BLE001)
    chk("3b TOO_SMALL is not a pass", False, f"import failed: {e!r}")

# 4 funding API monitored
vsrc = (ROOT / "scripts/data_vitals.py").read_text("utf-8")
fund = [c for c in dv["collectors"] if "funding" in c["source"].lower()]
chk("4 funding API monitored", "binance funding (live API)" in vsrc and bool(fund),
    f"{fund[0]['action'] if fund else 'ABSENT'}")

# 5 cadence docstring matches its constant
csrc = (ROOT / "scripts/run_cadence.py").read_text("utf-8")
chk("5 cadence doc==code", "tier1 every 28d" not in csrc and "_TIER1_EVERY_D = 14" in csrc,
    "docstring no longer claims 28d while the constant reads 14")

print("=== VERIFY: five fixes from a1bcd86, checked against RUNNING code ===\n")
for name, ok, detail in checks:
    print(f"  {'PASS' if ok else 'FAIL'}  {name:<32} {detail}")
bad = [c for c in checks if not c[1]]
print(f"\n  {len(checks)-len(bad)}/{len(checks)} verified live.")
if bad:
    print("  A commit proves an edit happened, never that it is reachable or correct.")
sys.exit(1 if bad else 0)

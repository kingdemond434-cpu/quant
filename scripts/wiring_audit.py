"""WIRING AUDIT -- is everything INTENDED to run actually reachable from something that fires?

"Wired" has been used loosely all session. Adding a line to daily_research_cycle.py is only wiring
IF that file is itself scheduled AND actually executes the entry. Three failure modes, each
invisible from the file you edited:

  ORPHAN ENTRY   listed in the cycle, but the cycle is not scheduled -> never runs
  DEAD CRON      cron references a script that does not exist -> silent nightly failure
  UNREACHED      script exists, is scheduled, but has never produced its artifact

The last one is the killer: a scheduled script that errors every run looks identical to a healthy
one from the crontab. Only its output proves it.
"""
from __future__ import annotations

import json
import pathlib
import re
import subprocess
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
CYCLE = ROOT / "scripts/daily_research_cycle.py"


def crontab() -> str:
    try:
        return subprocess.run(["crontab", "-l"], capture_output=True, text=True,
                              check=False, timeout=20).stdout
    except Exception:  # blind-except intentional (BLE001)
        return ""


def timers() -> str:
    try:
        return subprocess.run(["systemctl", "list-timers", "--all", "--no-pager"],
                              capture_output=True, text=True, check=False, timeout=20).stdout
    except Exception:  # blind-except intentional (BLE001)
        return ""


cron, tmr = crontab(), timers()
cycle_txt = CYCLE.read_text("utf-8") if CYCLE.exists() else ""

# 1 -- is the cycle itself scheduled?
cycle_sched = "daily_research_cycle" in cron or "daily_research_cycle" in tmr
print("=== WIRING AUDIT ===\n")
print(f"  daily_research_cycle.py scheduled: {cycle_sched}")
if not cycle_sched:
    print("    !! CRITICAL: every entry wired to the cycle is UNREACHABLE.")
    print("    Adding a line to that file is not wiring if nothing invokes the file.")

# 2 -- entries listed in the cycle, and whether their artifact exists
entries = re.findall(r'\("([a-z_0-9]+)",\s*"(scripts/[a-z_0-9]+\.py)[^"]*"', cycle_txt)
print(f"\n  {len(entries)} entries listed in daily_research_cycle.py")
missing_script, no_artifact = [], []
for name, path in entries:
    if not (ROOT / path).exists():
        missing_script.append((name, path))
for name, path in entries:
    stem = pathlib.Path(path).stem
    arts = list(ROOT.glob(f"data/{stem}.json")) + list(ROOT.glob(f"data/{stem}.jsonl"))
    if not arts:
        no_artifact.append(name)
if missing_script:
    print(f"    !! {len(missing_script)} reference a script that does not exist:")
    for n, p in missing_script:
        print(f"       {n} -> {p}")
else:
    print("    all referenced scripts exist")
if no_artifact:
    print(f"    {len(no_artifact)} have produced no data/<stem>.json artifact "
          f"(may be by design): {', '.join(no_artifact[:8])}")

# 3 -- cron entries pointing at scripts
cron_scripts = re.findall(r'(scripts/[a-zA-Z_0-9]+\.py)', cron)
print(f"\n  {len(set(cron_scripts))} distinct scripts referenced directly in crontab")
dead = [c for c in set(cron_scripts) if not (ROOT / c).exists()]
if dead:
    print(f"    !! DEAD CRON -- referenced but absent: {dead}")
else:
    print("    all cron-referenced scripts exist")

# 4 -- collectors: registered vs actually producing fresh output
print("\n  COLLECTOR LIVENESS (registered -> is it producing?)")
try:
    dv = json.loads((ROOT / "data/data_vitals.json").read_text("utf-8"))
    now = time.time()
    for c in dv.get("collectors", []):
        act = c.get("action", "")
        if act.startswith(("DEAD", "MISSING")):
            print(f"    {c['source']:<42} {act}")
except Exception as e:  # blind-except intentional (BLE001)
    print(f"    vitals unreadable: {e!r}")

# 5 -- this session's builds, each must be reachable
# THREE ENTRIES DROPPED 2026-09-05 (universe mandate): hedge_integrity (the spot-perp carry
# invariant), collect_defi_lending (Aave/Compound/Morpho) and collect_oi_ls_live (Binance
# open-interest and long/short ratios). All three modules are deleted, and a REACHABILITY list
# naming an absent file reports UNREACHABLE forever about something that is not supposed to
# exist -- which is the same crying-wolf failure this audit exists to surface, pointed inward.
BUILT = ["experiment_registry", "research_exchange", "measurement_gate", "feature_library",
         "leakage_detector", "execution_bottleneck", "research_cio",
         "data_vitals", "alpha_lifecycle", "dependency_graph", "knowledge_engine",
         "module_justification", "kimi_hunter",
         "build_audit_shards", "coverage_audit"]
print(f"\n  SESSION BUILDS -- reachability ({len(BUILT)} modules)")
print(f"  {'module':<26}{'in cycle':>10}{'in cron':>9}{'artifact':>10}   reachable")
unreachable = []
for m in BUILT:
    inc = m in cycle_txt
    icr = m in cron
    art = bool(list(ROOT.glob(f"data/{m}.json")) + list(ROOT.glob(f"data/{m}.jsonl"))
               or list(ROOT.glob(f"data/{m.replace('collect_','')}*.jsonl")))
    # TRANSITIVE REACHABILITY. One hop was not enough: the real chain is
    # cron -> run_cadence -> run_external_panel -> build_audit_shards. Walk the invocation graph
    # to a depth limit instead of checking direct callers only.
    def _reaches(target: str, depth: int = 0, seen: set | None = None):
        seen = seen or set()
        if depth > 3 or target in seen:
            return None
        seen.add(target)
        for other in ROOT.glob("scripts/*.py"):
            if other.stem == target:
                continue
            body = other.read_text("utf-8", errors="ignore")
            if f"{target}.py" not in body:
                continue
            if other.stem in cron or (other.stem in cycle_txt and cycle_sched):
                return other.stem
            deeper = _reaches(other.stem, depth + 1, seen)
            if deeper:
                return f"{other.stem}<-{deeper}"
        return None

    indirect = None if (inc or icr) else _reaches(m)
    reach = (inc and cycle_sched) or icr or bool(indirect)
    if not reach:
        unreachable.append(m)
    _how = "YES" if reach else "NO"
    if indirect:
        _how = f"via {indirect}"
    print(f"  {m:<26}{inc!s:>10}{icr!s:>9}{art!s:>10}   {_how}")

print(f"\n  {len(BUILT)-len(unreachable)}/{len(BUILT)} reachable from a scheduler.")
if unreachable:
    print(f"  UNREACHABLE: {', '.join(unreachable)}")
    print("  These run only when invoked by hand. That is not wired.")

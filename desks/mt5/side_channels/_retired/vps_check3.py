import json, os, glob
base = "/home/quant/quant-platform/desks/mt5"
# 1. survivors
sv = base + "/reports/UNIVERSAL_SURVIVORS.json"
if os.path.exists(sv):
    d = json.load(open(sv))
    print("UNIVERSAL_SURVIVORS n:", d.get("n"))
    for k, v in (d.get("survivors") or {}).items():
        print("  ", k, "days:", v.get("days"), "gated_at:", v.get("gated_at"))
else:
    print("UNIVERSAL_SURVIVORS: not yet")
# 2. universal gate progress
log = base + "/logs/child/universal_super.log"
if os.path.exists(log):
    lines = open(log, errors="ignore").read().splitlines()
    print("gate log tail:")
    for l in lines[-12:]:
        print("  ", l[:120])
# 3. done markers
marks = sorted(glob.glob(base + "/reports/DONE_universal_*"))
print("universal DONE markers:", [m.split("/")[-1] for m in marks])
# 4. allocation
al = base + "/reports/allocation.json"
print("allocation.json exists:", os.path.exists(al))
if os.path.exists(al):
    d = json.load(open(al))
    print("  weights:", list(d.get("weights", {}).items())[:6])
    print("  excluded:", d.get("excluded"))
# 5. signal gates complete?
sg = sorted(glob.glob(base + "/reports/DONE_signal_gate_*"))
print("signal gate DONE:", [m.split("/")[-1] for m in sg])
# 6. chain wiring: check supervisor targets + gate module wiring
sup = open(base + "/research/research_supervisor.py").read()
for t in ["signal_gate", "universal", "allocation", "merge", "qquant_gates", "research_loop"]:
    print("supervisor target", t, ":", t in sup)
print("signal_gate wired in supervisor:", "signal_gate" in sup)
print("allocation requires signal gate:", "signal_gate_" in open(base + "/research/allocation.py").read())
print("gate processes:", [p.split("/")[-1] for p in glob.glob(base + "/reports/universal_gates_*.json")])
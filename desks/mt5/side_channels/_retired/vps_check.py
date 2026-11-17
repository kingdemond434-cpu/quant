import json
base = "/home/quant/quant-platform/desks/mt5"
r = json.load(open(base + "/reports/signal_gate_hunt18_h18-004.json"))
print("h18-004 cells:", len(r["cells"]))
for c in r["cells"]:
    if c["cell"].startswith("XAUUSD") or c["verdict"] == "INFORMED":
        print(c["cell"], c["n"], c["verdict"])
q = json.load(open(base + "/data/research_queue.json"))
print("queue:", [(i["id"], i["status"]) for i in q])
import glob
print("hunt18 reports:", [p.split("/")[-1] for p in sorted(glob.glob(base + "/reports/hunt18_*.json"))])
sv = base + "/reports/UNIVERSAL_SURVIVORS.json"
import os
print("UNIVERSAL_SURVIVORS exists:", os.path.exists(sv))
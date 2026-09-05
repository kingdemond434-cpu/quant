import json, os, subprocess
base = "/home/quant/quant-platform/desks/mt5"
q = json.load(open(base + "/data/research_queue.json"))
print("queue:", [(i["id"], i["status"]) for i in q[-4:]])
log = base + "/logs/child/universal_super.log"
n = open(log).read().count("gauntlet: hunt17")
print("hunt17 gauntlet starts:", n)
import glob
marks = sorted(glob.glob(base + "/reports/DONE_universal_*"))
print("universal DONE markers:", [m.split("/")[-1] for m in marks])
print("UNIVERSAL_SURVIVORS:", os.path.exists(base + "/reports/UNIVERSAL_SURVIVORS.json"))
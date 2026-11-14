# YOUTUBE_API_KEY is read on the VPS by youtube_miner._load_api_key (env or
# data/secrets/youtube.json) -- never pass or hard-code it here.
import subprocess

# Test YouTube with debug
r = subprocess.run(["ssh", "quant@95.216.191.70",
    "cd /home/quant/quant-platform/desks/mt5/side_channels && "
    "/home/quant/quant-platform/.venv/bin/python -c '"
    "import os; print(\"API_KEY:\", bool(os.environ.get(\"YOUTUBE_API_KEY\"))); "
    "from youtube_miner import mine; "
    "r = mine(); "
    "print(f\"youtube: {len(r)} items\"); "
    "[print(x.symbol, x.source_url[:80]) for x in r[:5]]"
    "' 2>&1"],
    capture_output=True, text=True, timeout=30)
print(r.stdout)
if r.stderr:
    print("ERR:", r.stderr[:500])

# Test Reddit
r2 = subprocess.run(["ssh", "quant@95.216.191.70",
    "cd /home/quant/quant-platform/desks/mt5/side_channels && "
    "/home/quant/quant-platform/.venv/bin/python -c '"
    "from reddit_miner import mine_all; "
    "r = mine_all(); "
    "print(f\"reddit: {len(r)} items\"); "
    "[print(x.get(\"symbol\",\"?\"), x.get(\"source_url\",\"?\")[:80]) for x in r[:5]]"
    "' 2>&1"],
    capture_output=True, text=True, timeout=30)
print(r2.stdout)
if r2.stderr:
    print("ERR:", r2.stderr[:500])

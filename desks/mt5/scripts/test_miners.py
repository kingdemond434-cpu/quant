import subprocess

# Test YouTube miner
r = subprocess.run(["ssh", "quant@95.216.191.70",
    "cd /home/quant/quant-platform/desks/mt5/side_channels && "
    "/home/quant/quant-platform/.venv/bin/python -c '"
    "from youtube_miner import mine; "
    "r = mine(); "
    "print(f\"youtube: {len(r)} items\"); "
    "[print(x.get(\"symbol\",\"?\"), x.get(\"source_url\",\"?\")[:60]) for x in r[:5]]"
    "' 2>&1"],
    capture_output=True, text=True, timeout=30)
print(r.stdout)
if r.stderr:
    print("ERR:", r.stderr[:500])

# Test Reddit - check rate limiting
r2 = subprocess.run(["ssh", "quant@95.216.191.70",
    "cd /home/quant/quant-platform/desks/mt5/side_channels && "
    "/home/quant/quant-platform/.venv/bin/python -c '"
    "from reddit_miner import mine; "
    "r = mine(); "
    "print(f\"reddit: {len(r)} items\"); "
    "[print(x.get(\"symbol\",\"?\"), x.get(\"source_url\",\"?\")[:60]) for x in r[:5]]"
    "' 2>&1"],
    capture_output=True, text=True, timeout=30)
print(r2.stdout)
if r2.stderr:
    print("ERR:", r2.stderr[:500])

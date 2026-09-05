import subprocess

r = subprocess.run(["ssh", "quant@95.216.191.70",
    "cd /home/quant/quant-platform/desks/mt5/side_channels && "
    "/home/quant/quant-platform/.venv/bin/python -c '"
    "from reddit_miner import mine_all; "
    "r = mine_all(); "
    "print(f\"reddit: {len(r)} items total\")"
    "' 2>&1"],
    capture_output=True, text=True, timeout=120)
print(r.stdout)
if r.stderr:
    print("ERR:", r.stderr[:500])

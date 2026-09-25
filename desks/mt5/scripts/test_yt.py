# YOUTUBE_API_KEY is read on the VPS by youtube_miner._load_api_key (env or
# data/secrets/youtube.json) -- never pass or hard-code it here.
import subprocess

r = subprocess.run(["ssh", "quant@95.216.191.70",
    "cd /home/quant/quant-platform/desks/mt5/side_channels && "
    "/home/quant/quant-platform/.venv/bin/python -c '"
    "from youtube_miner import _search_youtube, QUERIES; "
    "print(\"queries:\", QUERIES[:3]); "
    "r = _search_youtube(QUERIES[0]); "
    "print(f\"API returned {len(r)} items for first query\"); "
    "if r: print(r[0])"
    "' 2>&1"],
    capture_output=True, text=True, timeout=30)
print(r.stdout)
if r.stderr:
    print("ERR:", r.stderr[:500])

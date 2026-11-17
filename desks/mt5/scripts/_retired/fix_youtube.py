import subprocess

# Fix YouTube: check quota before running, skip gracefully on 429
fix_yt = subprocess.run(
    ["ssh", "quant@95.216.191.70",
     "grep -n 'resp.raise_for_status\\|except Exception' /home/quant/quant-platform/desks/mt5/side_channels/youtube_miner.py"],
    capture_output=True, text=True, timeout=15
)
print("YouTube miner exception handling:")
print(fix_yt.stdout)

# Patch: catch 429 specifically and skip
patch = '''
    try:
        resp = requests.get(SEARCH_URL, params=params, timeout=15)
        if resp.status_code == 429:
            return []
        resp.raise_for_status()
        return resp.json().get("items", [])
    except Exception:
        return []
'''

proc = subprocess.run(
    ["ssh", "quant@95.216.191.70",
     "cd /home/quant/quant-platform/desks/mt5/side_channels && "
     "sed -i 's/resp.raise_for_status()/if resp.status_code == 429: return []\\n        resp.raise_for_status()/' youtube_miner.py"],
    capture_output=True, text=True, timeout=15
)
print("YouTube patched:", "OK" if proc.returncode == 0 else proc.stderr[:200])

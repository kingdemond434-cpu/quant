# The VPS-side youtube_miner loads YOUTUBE_API_KEY (env or data/secrets/youtube.json).
import subprocess, textwrap

code = textwrap.dedent("""\
import os
import sys
sys.path.insert(0, "/home/quant/quant-platform/desks/mt5/side_channels")
from youtube_miner import _search_youtube, QUERIES
print("queries:", QUERIES[:3])
for q in QUERIES[:3]:
    r = _search_youtube(q)
    print(f"  '{q}' -> {len(r)} items")
""")

# Write to temp file on VPS
proc = subprocess.run(
    ["ssh", "quant@95.216.191.70", f"cat > /tmp/test_yt.py << 'PYEOF'\n{code}\nPYEOF"],
    capture_output=True, text=True, timeout=10
)

proc2 = subprocess.run(
    ["ssh", "quant@95.216.191.70",
     "cd /home/quant/quant-platform && /home/quant/quant-platform/.venv/bin/python /tmp/test_yt.py 2>&1"],
    capture_output=True, text=True, timeout=30
)
print(proc2.stdout)
if proc2.stderr:
    print("ERR:", proc2.stderr[:500])

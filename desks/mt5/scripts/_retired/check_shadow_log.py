import json
from pathlib import Path

log = Path("/home/quant/quant-platform/desks/mt5/logs/shadow.log")
if log.exists():
    lines = log.read_text("utf-8").split("\n")
    # Get last 30 non-empty lines
    recent = [l for l in lines if l.strip()][-30:]
    for l in recent:
        print(l)
else:
    print("No shadow.log found")

#!/usr/bin/env python3
import json
from pathlib import Path

d = Path("/home/quant/quant-platform/data/x_deep_mine")
for f in sorted(d.glob("*_2026*.json")):
    p = json.load(open(f))
    print(f"=== {p['account']} ===")
    print("  name:", p.get("name"), "| followers:", p.get("followers"))
    for t in p["tweets"]:
        print(f"  [{t['posted_at'][:16] if t['posted_at'] else '?'}] likes={t['likes']} links={t['links']}")
        print(f"    {t['text'][:250]}")
    print()
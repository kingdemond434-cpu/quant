#!/usr/bin/env python3
import json
import re
import urllib.request
try:
    from libs.data.polite_fetch import DESK_UA, polite_urlopen
except ImportError:  # run as a script: the repo root is not on the path
    import sys as _sys
    from pathlib import Path as _Path
    _sys.path.insert(0, str(_Path(__file__).resolve().parents[3]))
    from libs.data.polite_fetch import DESK_UA, polite_urlopen

UA = DESK_UA

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html"})
    with polite_urlopen(req, timeout=20) as resp:
        return resp.read().decode("utf-8", errors="replace")

html = fetch("https://x.com/L1vsun")
ids = sorted(set(re.findall(r"data-tweet-id=\"(\d+)\"", html)))
print("tweet ids:", ids)

for tid in ids:
    idx = html.find(f'data-tweet-id="{tid}"')
    if idx < 0:
        continue
    window = html[idx:idx + 6000]
    texts = re.findall(r">([^<>]{40,400})<", window)
    texts = [t for t in texts if not t.startswith("http") and " " in t and "RT" != t[:2]]
    seen = set()
    out = []
    for t in texts:
        t = t.strip()
        if t not in seen and len(t) > 40:
            seen.add(t)
            out.append(t)
        if len(out) >= 3:
            break
    print(f"--- {tid} ---")
    for t in out[:2]:
        print("  ", t[:400])
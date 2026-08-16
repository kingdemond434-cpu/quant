#!/usr/bin/env python3
import json
import re
import urllib.request

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36"

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html"})
    with urllib.request.urlopen(req, timeout=20) as resp:
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
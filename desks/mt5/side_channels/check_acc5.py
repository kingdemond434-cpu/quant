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
print("HTML length:", len(html))

m = re.search(r"<meta property=\"og:description\" content=\"([^\"]*)\"", html)
if m:
    print("OG description:", m.group(1)[:500])
m = re.search(r"<title>([^<]*)</title>", html)
if m:
    print("Title:", m.group(1))

for pat in ["followers_count", "statuses_count", "friends_count"]:
    for mm in re.finditer(pat + r":(\d+)", html):
        print(pat, "=", mm.group(1))
        break

print("--- timeline entries ---")
ids = set(re.findall(r"data-tweet-id=\"(\d+)\"", html))
print("tweet ids found:", len(ids), sorted(ids)[:10])
if not ids:
    ids = set(re.findall(r"status/(\d{15,})", html))
    print("status ids found:", len(ids), sorted(ids)[:10])
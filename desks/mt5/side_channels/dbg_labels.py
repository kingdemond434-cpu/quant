#!/usr/bin/env python3
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
req = urllib.request.Request("https://x.com/whale_alert", headers={"User-Agent": UA, "Accept": "text/html"})
with polite_urlopen(req, timeout=20) as resp:
    html = resp.read().decode("utf-8", errors="replace")

print("len:", len(html))
m = re.findall(r'aria-label="([^"]*like[^"]*)"', html)
print("like labels:", m[:10])
m2 = re.findall(r'aria-label="([^"]*(?:replies|reposts|views)[^"]*)"', html)
print("other labels:", m2[:10])
m3 = re.findall(r'data-testid="like"', html)
print("data-testid like:", len(m3))
idx = html.find('data-tweet-id=')
if idx > 0:
    w = html[idx:idx+4000]
    m4 = re.findall(r'aria-label="([^"]+)"', w)
    print("all labels in first tweet window:", m4[:20])
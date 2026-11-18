#!/usr/bin/env python3
import re
import urllib.request
try:
    from libs.data.honest_ua import HONEST_UA
except ImportError:  # run as a bare script, repo root not on sys.path
    HONEST_UA = "quant-desk-research/1.0 (automated research; honours robots.txt)"

UA = HONEST_UA
req = urllib.request.Request("https://x.com/whale_alert", headers={"User-Agent": UA, "Accept": "text/html"})
with urllib.request.urlopen(req, timeout=20) as resp:
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
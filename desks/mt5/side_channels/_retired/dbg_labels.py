#!/usr/bin/env python3
import re
import urllib.request

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36"
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
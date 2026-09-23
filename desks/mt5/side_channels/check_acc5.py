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
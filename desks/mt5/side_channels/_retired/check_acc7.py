#!/usr/bin/env python3
import re
import urllib.request

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36"

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.read().decode("utf-8", errors="replace")

for handle in ["shmidt", "cvxv666", "L1vsun"]:
    try:
        html = fetch(f"https://x.com/{handle}")
        title = re.search(r"<title>([^<]*)</title>", html)
        desc = re.search(r"<meta property=\"og:description\" content=\"([^\"]*)\"", html)
        ids = sorted(set(re.findall(r"data-tweet-id=\"(\d+)\"", html)))
        print(f"=== {handle} ===")
        print("  title:", title.group(1) if title else "NONE")
        print("  bio:", (desc.group(1)[:200] if desc else "NONE"))
        print("  tweets in SSR:", len(ids))
    except Exception as e:
        print(f"=== {handle} === ERROR: {e}")
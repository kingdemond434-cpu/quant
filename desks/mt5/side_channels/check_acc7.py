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

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html"})
    with polite_urlopen(req, timeout=20) as resp:
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
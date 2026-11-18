import json
import urllib.request
try:
    from libs.data.honest_ua import HONEST_UA
except ImportError:  # run as a bare script, repo root not on sys.path
    HONEST_UA = "quant-desk-research/1.0 (automated research; honours robots.txt)"

u = "https://publicreporting.cftc.gov/resource/6dca-aqww.json?$limit=1"
req = urllib.request.Request(u, headers={"User-Agent": HONEST_UA})
with urllib.request.urlopen(req, timeout=30) as r:
    d = json.load(r)
print(sorted(d[0].keys()))
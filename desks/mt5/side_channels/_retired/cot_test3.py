import json
import urllib.request

u = "https://publicreporting.cftc.gov/resource/6dca-aqww.json?$limit=1"
req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"})
with urllib.request.urlopen(req, timeout=30) as r:
    d = json.load(r)
print(sorted(d[0].keys()))
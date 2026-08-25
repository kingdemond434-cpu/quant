import json
import urllib.parse
import urllib.request

base = "https://publicreporting.cftc.gov/resource/6dca-aqww.json"
tests = [
    ("min", base + "?$limit=2"),
    (
        "gold",
        base
        + "?$where="
        + urllib.parse.quote("commodity_name like 'GOLD%'")
        + "&$limit=2",
    ),
]
for name, u in tests:
    try:
        req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            d = json.load(r)
            print(name, "OK rows=", len(d))
    except urllib.error.HTTPError as e:
        print(name, "ERR", e.code, e.read().decode()[:400])
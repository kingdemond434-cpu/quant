import json
import urllib.parse
import urllib.request
try:
    from libs.data.polite_fetch import DESK_UA, polite_urlopen
except ImportError:  # run as a script: the repo root is not on the path
    import sys as _sys
    from pathlib import Path as _Path
    _sys.path.insert(0, str(_Path(__file__).resolve().parents[3]))
    from libs.data.polite_fetch import DESK_UA, polite_urlopen

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
        req = urllib.request.Request(u, headers={"User-Agent": DESK_UA})
        with polite_urlopen(req, timeout=30) as r:
            d = json.load(r)
            print(name, "OK rows=", len(d))
    except urllib.error.HTTPError as e:
        print(name, "ERR", e.code, e.read().decode()[:400])
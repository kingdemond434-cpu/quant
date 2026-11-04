import json, urllib.parse, urllib.request
try:
    from libs.data.polite_fetch import DESK_UA, polite_urlopen
except ImportError:  # run as a script: the repo root is not on the path
    import sys as _sys
    from pathlib import Path as _Path
    _sys.path.insert(0, str(_Path(__file__).resolve().parents[3]))
    from libs.data.polite_fetch import DESK_UA, polite_urlopen

base = "https://publicreporting.cftc.gov/resource/6dca-aqww.json"
for pat in ["EURO", "POUND", "S&P", "NASDAQ", "DOLLAR"]:
    p = {"$select": "distinct commodity_name",
         "$where": "commodity_name like '{0}%'".format(pat)}
    url = base + "?" + urllib.parse.urlencode(p)
    req = urllib.request.Request(url, headers={"User-Agent": DESK_UA})
    try:
        rows = json.load(polite_urlopen(req, timeout=60))
        print(pat, "->", [r.get("commodity_name") for r in rows][:12])
    except Exception as e:
        print(pat, "ERR", repr(e))
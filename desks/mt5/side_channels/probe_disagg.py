import json
import urllib.request
try:
    from libs.data.polite_fetch import DESK_UA, polite_urlopen
except ImportError:  # run as a script: the repo root is not on the path
    import sys as _sys
    from pathlib import Path as _Path
    _sys.path.insert(0, str(_Path(__file__).resolve().parents[3]))
    from libs.data.polite_fetch import DESK_UA, polite_urlopen

req = urllib.request.Request(
    "https://publicreporting.cftc.gov/resource/72hh-3qpy.json?$limit=1",
    headers={"User-Agent": DESK_UA})
try:
    rows = json.load(polite_urlopen(req, timeout=60))
    print("rows:", len(rows))
    if rows:
        print("keys:", sorted(rows[0].keys()))
        print("commodity:", rows[0].get("commodity_name"),
              "| market:", rows[0].get("contract_market_name"))
except Exception as e:
    print("ERR", repr(e))
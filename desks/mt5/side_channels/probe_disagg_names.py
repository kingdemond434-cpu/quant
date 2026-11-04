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

UA = {"User-Agent": DESK_UA}
for pat in ["YEN", "FX", "POUND", "DOLLAR", "S&P", "NASDAQ"]:
    params = {"$select": "distinct commodity_name",
              "$where": "commodity_name like '{}%'".format(pat)}
    url = "https://publicreporting.cftc.gov/resource/72hh-3qpy.json?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers=UA)
    try:
        rows = json.load(polite_urlopen(req, timeout=60))
        print(pat, "->", [r.get("commodity_name") for r in rows][:12])
    except Exception as e:
        print(pat, "ERR", repr(e))
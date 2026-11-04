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
params = {"$select": "distinct commodity_name"}
url = "https://publicreporting.cftc.gov/resource/72hh-3qpy.json?" + urllib.parse.urlencode(params)
req = urllib.request.Request(url, headers=UA)
rows = json.load(polite_urlopen(req, timeout=120))
names = sorted(r.get("commodity_name") for r in rows)
print("total distinct:", len(names))
for n in names:
    if any(k in n.upper() for k in ["YEN", "POUND", "DOLLAR", "EURO", "FRANC",
                                    "S&P", "NASDAQ", "GOLD", "SILVER", "INDEX"]):
        print(" ", n)
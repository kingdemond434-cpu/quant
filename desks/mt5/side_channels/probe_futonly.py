import json
import urllib.request
try:
    from libs.data.polite_fetch import DESK_UA, polite_urlopen
except ImportError:  # run as a script: the repo root is not on the path
    import sys as _sys
    from pathlib import Path as _Path
    _sys.path.insert(0, str(_Path(__file__).resolve().parents[3]))
    from libs.data.polite_fetch import DESK_UA, polite_urlopen

url = ("https://publicreporting.cftc.gov/resource/72hh-3qpy.json?"
       "$select=futonly_or_combined,commodity_name&$where=commodity_name='GOLD'")
req = urllib.request.Request(url, headers={"User-Agent": DESK_UA})
rows = json.load(polite_urlopen(req, timeout=90))
vals = {}
for r in rows:
    v = r.get("futonly_or_combined")
    vals[str(v)] = vals.get(str(v), 0) + 1
print(vals)
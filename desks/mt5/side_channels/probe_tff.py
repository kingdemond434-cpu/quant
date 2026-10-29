import json
import urllib.request
try:
    from libs.data.polite_fetch import DESK_UA, polite_urlopen
except ImportError:  # run as a script: the repo root is not on the path
    import sys as _sys
    from pathlib import Path as _Path
    _sys.path.insert(0, str(_Path(__file__).resolve().parents[3]))
    from libs.data.polite_fetch import DESK_UA, polite_urlopen

UA = {"User-Agent": DESK_UA}
for vid in ["r4w3-av2u", "rxbv-e226"]:
    url = "https://publicreporting.cftc.gov/resource/{}.json?$limit=1".format(vid)
    req = urllib.request.Request(url, headers=UA)
    try:
        rows = json.load(polite_urlopen(req, timeout=90))
        if not rows:
            print(vid, "empty")
            continue
        keys = sorted(rows[0].keys())
        print(vid, "rows-sample keys:", len(keys))
        interesting = [k for k in keys if any(w in k.lower() for w in
                        ["asset", "lever", "dealer", "fund", "m_money", "swap",
                         "report_date", "commodity", "market"])]
        print(vid, "->", interesting[:30])
        print(vid, "commodity:", rows[0].get("commodity_name"))
    except Exception as e:
        print(vid, "ERR", repr(e))
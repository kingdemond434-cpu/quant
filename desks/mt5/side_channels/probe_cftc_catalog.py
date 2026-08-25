import json
import urllib.request

UA = {"User-Agent": "Mozilla/5.0"}


def get(url, timeout=60):
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", errors="replace")
    except Exception as e:
        return "ERR", repr(e)


st, body = get("https://publicreporting.cftc.gov/api/views.json?limit=100")
if st == 200:
    try:
        views = json.loads(body)
        print("total views:", len(views))
        for v in views:
            name = (v.get("name") or "")
            if any(k in name.upper() for k in ["TRADERS", "DISAGGREG", "SUPPLEMENT", "SWAPS"]):
                print(" -", name, "|", v.get("id"))
    except Exception as e:
        print("parse ERR", repr(e), body[:300])
else:
    print(st, body[:300])
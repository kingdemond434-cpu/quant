import json
import urllib.parse
import urllib.request
try:
    from libs.data.honest_ua import HONEST_UA
except ImportError:  # run as a bare script, repo root not on sys.path
    HONEST_UA = "quant-desk-research/1.0 (automated research; honours robots.txt)"

UA = {"User-Agent": HONEST_UA}
params = {"$select": "distinct commodity_name"}
url = "https://publicreporting.cftc.gov/resource/72hh-3qpy.json?" + urllib.parse.urlencode(params)
req = urllib.request.Request(url, headers=UA)
rows = json.load(urllib.request.urlopen(req, timeout=120))
names = sorted(r.get("commodity_name") for r in rows)
print("total distinct:", len(names))
for n in names:
    if any(k in n.upper() for k in ["YEN", "POUND", "DOLLAR", "EURO", "FRANC",
                                    "S&P", "NASDAQ", "GOLD", "SILVER", "INDEX"]):
        print(" ", n)
import json
import urllib.parse
import urllib.request
try:
    from libs.data.honest_ua import HONEST_UA
except ImportError:  # run as a bare script, repo root not on sys.path
    HONEST_UA = "quant-desk-research/1.0 (automated research; honours robots.txt)"

UA = {"User-Agent": HONEST_UA}
for pat in ["YEN", "FX", "POUND", "DOLLAR", "S&P", "NASDAQ"]:
    params = {"$select": "distinct commodity_name",
              "$where": "commodity_name like '{}%'".format(pat)}
    url = "https://publicreporting.cftc.gov/resource/72hh-3qpy.json?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers=UA)
    try:
        rows = json.load(urllib.request.urlopen(req, timeout=60))
        print(pat, "->", [r.get("commodity_name") for r in rows][:12])
    except Exception as e:
        print(pat, "ERR", repr(e))
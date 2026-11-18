import json, urllib.parse, urllib.request
try:
    from libs.data.honest_ua import HONEST_UA
except ImportError:  # run as a bare script, repo root not on sys.path
    HONEST_UA = "quant-desk-research/1.0 (automated research; honours robots.txt)"

base = "https://publicreporting.cftc.gov/resource/6dca-aqww.json"
for pat in ["EURO", "POUND", "S&P", "NASDAQ", "DOLLAR"]:
    p = {"$select": "distinct commodity_name",
         "$where": "commodity_name like '{0}%'".format(pat)}
    url = base + "?" + urllib.parse.urlencode(p)
    req = urllib.request.Request(url, headers={"User-Agent": HONEST_UA})
    try:
        rows = json.load(urllib.request.urlopen(req, timeout=60))
        print(pat, "->", [r.get("commodity_name") for r in rows][:12])
    except Exception as e:
        print(pat, "ERR", repr(e))
import json, urllib.parse, urllib.request

base = "https://publicreporting.cftc.gov/resource/6dca-aqww.json"
for pat in ["%FX%", "%CURRENC%", "S&P 500", "NASDAQ 100", "%INDEX%"]:
    p = {"$select": "distinct commodity_name",
         "$where": "commodity_name like '{0}'".format(pat)}
    url = base + "?" + urllib.parse.urlencode(p)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        rows = json.load(urllib.request.urlopen(req, timeout=60))
        print(pat, "->", [r.get("commodity_name") for r in rows][:15])
    except Exception as e:
        print(pat, "ERR", repr(e))
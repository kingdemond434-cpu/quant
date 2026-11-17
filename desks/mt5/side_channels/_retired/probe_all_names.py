import json
import urllib.parse
import urllib.request

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"}
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
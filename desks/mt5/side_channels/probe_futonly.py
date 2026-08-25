import json
import urllib.request

url = ("https://publicreporting.cftc.gov/resource/72hh-3qpy.json?"
       "$select=futonly_or_combined,commodity_name&$where=commodity_name='GOLD'")
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
rows = json.load(urllib.request.urlopen(req, timeout=90))
vals = {}
for r in rows:
    v = r.get("futonly_or_combined")
    vals[str(v)] = vals.get(str(v), 0) + 1
print(vals)
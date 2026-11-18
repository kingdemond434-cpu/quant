import json
import urllib.request
try:
    from libs.data.honest_ua import HONEST_UA
except ImportError:  # run as a bare script, repo root not on sys.path
    HONEST_UA = "quant-desk-research/1.0 (automated research; honours robots.txt)"

url = ("https://publicreporting.cftc.gov/resource/72hh-3qpy.json?"
       "$select=futonly_or_combined,commodity_name&$where=commodity_name='GOLD'")
req = urllib.request.Request(url, headers={"User-Agent": HONEST_UA})
rows = json.load(urllib.request.urlopen(req, timeout=90))
vals = {}
for r in rows:
    v = r.get("futonly_or_combined")
    vals[str(v)] = vals.get(str(v), 0) + 1
print(vals)
import json
import urllib.request
try:
    from libs.data.honest_ua import HONEST_UA
except ImportError:  # run as a bare script, repo root not on sys.path
    HONEST_UA = "quant-desk-research/1.0 (automated research; honours robots.txt)"

req = urllib.request.Request(
    "https://publicreporting.cftc.gov/resource/72hh-3qpy.json?$limit=1",
    headers={"User-Agent": HONEST_UA})
try:
    rows = json.load(urllib.request.urlopen(req, timeout=60))
    print("rows:", len(rows))
    if rows:
        print("keys:", sorted(rows[0].keys()))
        print("commodity:", rows[0].get("commodity_name"),
              "| market:", rows[0].get("contract_market_name"))
except Exception as e:
    print("ERR", repr(e))
#!/usr/bin/env python3
import json
import urllib.request

base = "https://publicreporting.cftc.gov/resource/6dca-aqww.json"
params = "?$where=market_and_exchange_names%20like%20%22%25BITCOIN%25%22&$order=report_date_as_yyyy_mm_dd%20DESC&$limit=5&$select=report_date_as_yyyy_mm_dd,market_and_exchange_names,noncomm_positions_long_all,noncomm_positions_short_all,comm_positions_long_all,comm_positions_short_all,open_interest_all"
req = urllib.request.Request(base + params, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"})
try:
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.loads(resp.read())
    print("rows:", len(data))
    for r in data:
        print(r.get("report_date_as_yyyy_mm_dd"), r.get("market_and_exchange_names"),
              "spec_L:", r.get("noncomm_positions_long_all"),
              "spec_S:", r.get("noncomm_positions_short_all"),
              "comm_L:", r.get("comm_positions_long_all"),
              "comm_S:", r.get("comm_positions_short_all"))
except Exception as e:
    print("ERROR:", e)
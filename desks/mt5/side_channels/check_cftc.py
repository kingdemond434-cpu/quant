#!/usr/bin/env python3
import json
import urllib.request
try:
    from libs.data.polite_fetch import DESK_UA, polite_urlopen
except ImportError:  # run as a script: the repo root is not on the path
    import sys as _sys
    from pathlib import Path as _Path
    _sys.path.insert(0, str(_Path(__file__).resolve().parents[3]))
    from libs.data.polite_fetch import DESK_UA, polite_urlopen

base = "https://publicreporting.cftc.gov/resource/6dca-aqww.json"
params = "?$where=market_and_exchange_names%20like%20%22%25BITCOIN%25%22&$order=report_date_as_yyyy_mm_dd%20DESC&$limit=5&$select=report_date_as_yyyy_mm_dd,market_and_exchange_names,noncomm_positions_long_all,noncomm_positions_short_all,comm_positions_long_all,comm_positions_short_all,open_interest_all"
req = urllib.request.Request(base + params, headers={"User-Agent": DESK_UA})
try:
    with polite_urlopen(req, timeout=20) as resp:
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
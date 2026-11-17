#!/usr/bin/env python3
import json
import urllib.request

def q(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())

for market, label in [
    ("%25BITCOIN%25CHICAGO%25", "BTC CME"),
    ("%25ETHER%25CHICAGO%25", "ETH CME"),
]:
    url = ("https://publicreporting.cftc.gov/resource/6dca-aqww.json"
           f"?$where=market_and_exchange_names%20like%20%22{market}%22"
           "&$order=report_date_as_yyyy_mm_dd%20ASC&$limit=1"
           "&$select=report_date_as_yyyy_mm_dd")
    try:
        rows = q(url)
        print(f"{label}: earliest = {rows[0]['report_date_as_yyyy_mm_dd'][:10] if rows else 'NONE'}")
    except Exception as e:
        print(f"{label}: ERROR {e}")

url = ("https://publicreporting.cftc.gov/resource/6dca-aqww.json"
       "?$where=market_and_exchange_names%20like%20%22%25ETHER%25CHICAGO%25%22"
       "&$order=report_date_as_yyyy_mm_dd%20DESC&$limit=1"
       "&$select=report_date_as_yyyy_mm_dd,noncomm_positions_long_all,noncomm_positions_short_all,comm_positions_long_all,comm_positions_short_all,open_interest_all")
rows = q(url)
print("ETH latest:", rows[0])
import json
import sys
import urllib.parse
import urllib.request

sys.path.insert(0, r"C:\Users\dell\mt5-research\mt5desk")

params = {
    "$where": "commodity_name='GOLD'",
    "$select": ("report_date_as_yyyy_mm_dd,commodity_name,contract_market_name,"
                "futonly_or_combined,open_interest_all,"
                "m_money_positions_long_all,m_money_positions_short_all,"
                "swap_positions_long_all,swap__positions_short_all,"
                "other_rept_positions_long,other_rept_positions_short,"
                "conc_net_le_4_tdr_long_all,conc_net_le_4_tdr_short_all"),
    "$order": "report_date_as_yyyy_mm_dd",
    "$limit": "3",
    "$offset": "0",
}
url = "https://publicreporting.cftc.gov/resource/72hh-3qpy.json?" + urllib.parse.urlencode(params)
print(url[:300])
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"})
try:
    body = urllib.request.urlopen(req, timeout=90).read().decode()
    print("OK len:", len(body))
    print(body[:400])
except Exception as e:
    print("ERR", repr(e))
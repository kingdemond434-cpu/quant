import json
import urllib.parse
import urllib.request

base = "https://publicreporting.cftc.gov/resource/6dca-aqww.json"
sel = (
    "report_date_as_yyyy_mm_dd,commodity_name,open_interest_all,"
    "m_money_manager_positions_long_all,m_money_manager_positions_short_all,"
    "m_producer_merchant_processor_user_positions_long_all,"
    "m_producer_merchant_processor_user_positions_short_all"
)
tests = [
    ("select", base + "?$select=" + urllib.parse.quote(sel) + "&$limit=2"),
    (
        "order",
        base
        + "?$select="
        + urllib.parse.quote(sel)
        + "&$order=report_date_as_yyyy_mm_dd"
        + "&$limit=2",
    ),
    (
        "gold+select",
        base
        + "?$where="
        + urllib.parse.quote("commodity_name like 'GOLD%'")
        + "&$select="
        + urllib.parse.quote(sel)
        + "&$order=report_date_as_yyyy_mm_dd"
        + "&$limit=2",
    ),
]
for name, u in tests:
    try:
        req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            d = json.load(r)
            print(name, "OK rows=", len(d), "cols=", sorted(d[0].keys()) if d else [])
    except urllib.error.HTTPError as e:
        print(name, "ERR", e.code, e.read().decode()[:400])
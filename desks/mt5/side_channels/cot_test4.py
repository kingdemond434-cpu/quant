import json
import urllib.request

ids = ["6dca-aqww", "72ab-akqy", "3q7j-xw4t", "5li7-ypmy", "h7ma-k3bu"]
for did in ids:
    u = f"https://publicreporting.cftc.gov/resource/{did}.json?$select=m_money_manager_positions_long_all&$limit=1"
    try:
        req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            d = json.load(r)
            print(did, "HAS m_money_manager, rows=", len(d))
    except urllib.error.HTTPError as e:
        msg = e.read().decode()[:120]
        print(did, "ERR", e.code, msg)
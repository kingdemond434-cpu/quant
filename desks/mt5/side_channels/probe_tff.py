import json
import urllib.request

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"}
for vid in ["r4w3-av2u", "rxbv-e226"]:
    url = "https://publicreporting.cftc.gov/resource/{}.json?$limit=1".format(vid)
    req = urllib.request.Request(url, headers=UA)
    try:
        rows = json.load(urllib.request.urlopen(req, timeout=90))
        if not rows:
            print(vid, "empty")
            continue
        keys = sorted(rows[0].keys())
        print(vid, "rows-sample keys:", len(keys))
        interesting = [k for k in keys if any(w in k.lower() for w in
                        ["asset", "lever", "dealer", "fund", "m_money", "swap",
                         "report_date", "commodity", "market"])]
        print(vid, "->", interesting[:30])
        print(vid, "commodity:", rows[0].get("commodity_name"))
    except Exception as e:
        print(vid, "ERR", repr(e))
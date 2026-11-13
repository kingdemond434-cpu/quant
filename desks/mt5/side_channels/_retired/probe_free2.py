import json
import re
import urllib.parse
import urllib.request

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"}


def get(url, headers=None, timeout=40):
    h = dict(UA)
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", errors="replace")
    except Exception as e:
        return "ERR", repr(e)


print("== LBMA page csv/xlsx links ==")
st, body = get("https://www.lbma.org.uk/prices-and-data/precious-metal-prices")
if st == 200:
    for m in re.findall(r'href="([^"]+\.(?:csv|xlsx?|json))"', body)[:10]:
        print("  ", m)
else:
    print("  ", st)

print("== CME with referer ==")
st, body = get("https://www.cmegroup.com/CmeWS/mvc/Metals/GetDepositary/GC",
               headers={"Referer": "https://www.cmegroup.com/markets/metals.html",
                        "Accept": "application/json"})
print("  ", st, body[:150].replace("\n", " "))

print("== CFTC catalog: traders in financial futures ==")
st, body = get("https://api.us.socrata.com/api/catalog/v1?domains=publicreporting.cftc.gov&q=traders&limit=10")
if st == 200:
    try:
        res = json.loads(body).get("results", [])
        print("   results:", len(res))
        for d in res[:10]:
            m = d.get("metadata", {})
            print("   -", m.get("name"), "|", d.get("resource", {}).get("id"))
    except Exception as e:
        print("   parse ERR", repr(e))
else:
    print("  ", st, body[:150])

print("== NY Fed nowcast ==")
for url in [
    "https://www.newyorkfed.org/research/policy/nowcast",
    "https://www.newyorkfed.org/medialibrary/media/research/regional_economy/nowcast/nowcast_data.json",
]:
    st, body = get(url)
    print("  ", st, url[-60:], "->", body[:120].replace("\n", " "))
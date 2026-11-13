import json
import urllib.parse
import urllib.request

UA = {"User-Agent": "Mozilla/5.0 (research; desk)"}


def get(url, timeout=40):
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", errors="replace")
    except Exception as e:
        return "ERR", repr(e)


print("== 1. CFTC Socrata catalog search for TFF/disaggregated schemas ==")
st, body = get("https://api.us.socrata.com/api/catalog/v1?domains=publicreporting.cftc.gov&q=tff&limit=8")
if st == 200:
    try:
        for d in json.loads(body).get("results", []):
            m = d.get("metadata", {})
            print(" ", m.get("name"), "|", d.get("resource", {}).get("id"))
    except Exception as e:
        print(" parse ERR", repr(e), body[:200])
else:
    print(" ", st, body[:200])

print("== 2. CME COMEX metals warehouse stocks (depositary) ==")
for url in [
    "https://www.cmegroup.com/CmeWS/mvc/Metals/GetDepositary/GC/",
    "https://www.cmegroup.com/market-data/delayed-quotes/metals/warehouse-reports.html",
]:
    st, body = get(url)
    print(" ", st, url[:60], "->", body[:120].replace("\n", " "))

print("== 3. LBMA benchmark prices ==")
for url in [
    "https://www.lbma.org.uk/prices-and-data/precious-metal-prices",
    "https://www.lbma.org.uk/_next/data/1eOvyIQdOh-b7LwIlQYDF/en/prices-and-data/precious-metal-prices.json",
]:
    st, body = get(url)
    print(" ", st, url[:60], "->", body[:120].replace("\n", " "))

print("== 4. Atlanta Fed GDPNow CSV ==")
st, body = get("https://www.atlantafed.org/cps/asset/cms/gdpnow/forecastdata_vintages.csv")
print(" ", st, "->", body[:150].replace("\n", " "))
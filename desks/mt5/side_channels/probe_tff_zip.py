import io
import ssl
import urllib.request
import zipfile

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE
UA = {"User-Agent": "Mozilla/5.0"}
url = "https://www.cftc.gov/files/dea/history/fut_fin_txt_2024.zip"
req = urllib.request.Request(url, headers=UA)
try:
    data = urllib.request.urlopen(req, timeout=120, context=ctx).read()
    print("zip bytes:", len(data))
    z = zipfile.ZipFile(io.BytesIO(data))
    names = z.namelist()
    print("files:", len(names))
    print("sample:", names[:20])
    fx = [n for n in names if any(k in n.upper() for k in
          ["YEN", "EURO", "POUND", "DOLLAR", "GOLD", "FRANC"])]
    print("fx-ish:", fx[:20])
except Exception as e:
    print("ERR", repr(e))
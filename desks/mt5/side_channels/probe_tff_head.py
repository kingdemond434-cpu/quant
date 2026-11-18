import io
import ssl
import urllib.request
import zipfile
try:
    from libs.data.honest_ua import HONEST_UA
except ImportError:  # run as a bare script, repo root not on sys.path
    HONEST_UA = "quant-desk-research/1.0 (automated research; honours robots.txt)"

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE
UA = {"User-Agent": HONEST_UA}
url = "https://www.cftc.gov/files/dea/history/fut_fin_txt_2024.zip"
req = urllib.request.Request(url, headers=UA)
data = urllib.request.urlopen(req, timeout=120, context=ctx).read()
z = zipfile.ZipFile(io.BytesIO(data))
text = z.read("FinFutYY.txt").decode("utf-8", errors="replace")
lines = text.splitlines()
print("n lines:", len(lines))
for l in lines[:3]:
    print(repr(l[:400]))
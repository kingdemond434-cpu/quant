import io
import ssl
import urllib.request
import zipfile
try:
    from libs.data.polite_fetch import DESK_UA
except ImportError:  # run as a script: the repo root is not on the path
    import sys as _sys
    from pathlib import Path as _Path
    _sys.path.insert(0, str(_Path(__file__).resolve().parents[3]))
    from libs.data.polite_fetch import DESK_UA

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE
UA = {"User-Agent": DESK_UA}
url = "https://www.cftc.gov/files/dea/history/fut_fin_txt_2024.zip"
req = urllib.request.Request(url, headers=UA)
data = urllib.request.urlopen(req, timeout=120, context=ctx).read()
z = zipfile.ZipFile(io.BytesIO(data))
text = z.read("FinFutYY.txt").decode("utf-8", errors="replace")
lines = text.splitlines()
print("n lines:", len(lines))
for l in lines[:3]:
    print(repr(l[:400]))
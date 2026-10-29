import io
import urllib.request
import zipfile
try:
    from libs.data.polite_fetch import DESK_UA, polite_urlopen
except ImportError:  # run as a script: the repo root is not on the path
    import sys as _sys
    from pathlib import Path as _Path
    _sys.path.insert(0, str(_Path(__file__).resolve().parents[3]))
    from libs.data.polite_fetch import DESK_UA, polite_urlopen

UA = {"User-Agent": DESK_UA}
url = "https://www.cftc.gov/files/dea/history/fut_fin_txt_2024.zip"
req = urllib.request.Request(url, headers=UA)
try:
    data = polite_urlopen(req, timeout=120).read()
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
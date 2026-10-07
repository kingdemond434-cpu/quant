import re, subprocess, sys, textwrap
from pathlib import Path

# A requests error carries the full URL, query string and key included. Everything this probe
# prints passes through the same redaction, here and on the VPS.
sys.path.append(str(Path(__file__).resolve().parents[3]))
from libs.ops.secret_scrub import scrub_text  # noqa: E402

_KEY_PARAM = re.compile(r"(?i)((?:^|[?&;\s])key=)[^&\s'\"]+")


def _redact(msg) -> str:
    return _KEY_PARAM.sub(r"\1[REDACTED]", scrub_text(str(msg)))


code = textwrap.dedent("""\
import os, json, re, sys
sys.path.insert(0, "/home/quant/quant-platform/desks/mt5/side_channels")
sys.path.append("/home/quant/quant-platform")
from libs.ops.secret_scrub import scrub_text
_KEY_PARAM = re.compile(r"(?i)((?:^|[?&;\\s])key=)[^&\\s'\\x22]+")
def _redact(msg):
    return _KEY_PARAM.sub(r"\\1[REDACTED]", scrub_text(str(msg)))
from youtube_miner import API_KEY  # env YOUTUBE_API_KEY or data/secrets/youtube.json
if not API_KEY:
    raise SystemExit("no YOUTUBE_API_KEY in env or data/secrets/youtube.json")
os.environ["YOUTUBE_API_KEY"] = API_KEY
import requests
url = "https://www.googleapis.com/youtube/v3/search"
params = {
    "part": "snippet",
    "q": "forex trading strategy 2026",
    "type": "video",
    "maxResults": 3,
    "order": "date",
    "key": os.environ["YOUTUBE_API_KEY"],
}
try:
    r = requests.get(url, params=params, timeout=15)
    print(f"status: {r.status_code}")
    d = r.json()
    if "error" in d:
        print(f"error: {d['error'].get('code')} {_redact(d['error'].get('message',''))[:200]}")
    else:
        items = d.get("items", [])
        print(f"items: {len(items)}")
        for i in items[:3]:
            s = i.get("snippet", {})
            print(f"  {s.get('title','')[:60]} | {s.get('channelTitle','')}")
except Exception as e:
    print(f"exception: {_redact(e)}")
""")


proc = subprocess.run(
    ["ssh", "quant@95.216.191.70", f"cat > /tmp/test_yt3.py << 'PYEOF'\n{code}\nPYEOF"],
    capture_output=True, text=True, timeout=10
)

proc2 = subprocess.run(
    ["ssh", "quant@95.216.191.70",
     "/home/quant/quant-platform/.venv/bin/python /tmp/test_yt3.py 2>&1"],
    capture_output=True, text=True, timeout=30
)
print(_redact(proc2.stdout))
if proc2.stderr:
    print("ERR:", _redact(proc2.stderr)[:300])

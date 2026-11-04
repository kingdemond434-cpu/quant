import subprocess, textwrap

code = textwrap.dedent("""\
import os, json
os.environ["YOUTUBE_API_KEY"] = "AIzaSyAIudkX3epD1dJZKNPMIr5x6J_9ayTGBoc"
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
        print(f"error: {d['error'].get('code')} {d['error'].get('message','')[:200]}")
    else:
        items = d.get("items", [])
        print(f"items: {len(items)}")
        for i in items[:3]:
            s = i.get("snippet", {})
            print(f"  {s.get('title','')[:60]} | {s.get('channelTitle','')}")
except Exception as e:
    print(f"exception: {e}")
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
print(proc2.stdout)
if proc2.stderr:
    print("ERR:", proc2.stderr[:300])

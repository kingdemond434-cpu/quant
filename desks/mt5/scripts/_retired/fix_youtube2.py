import subprocess

# Read the current youtube_miner.py
proc = subprocess.run(
    ["ssh", "quant@95.216.191.70", "cat /home/quant/quant-platform/desks/mt5/side_channels/youtube_miner.py"],
    capture_output=True, text=True, timeout=15
)
content = proc.stdout

# Fix the _search_api function to handle 429 gracefully
old = """    try:
        resp = requests.get(SEARCH_URL, params=params, timeout=15)
        resp.raise_for_status()
        return resp.json().get("items", [])
    except Exception:
        return []"""

new = """    try:
        resp = requests.get(SEARCH_URL, params=params, timeout=15)
        if resp.status_code == 429:
            print(f"  youtube: quota exceeded (429), skipping remaining queries")
            return []
        resp.raise_for_status()
        return resp.json().get("items", [])
    except Exception:
        return []"""

if old in content:
    content = content.replace(old, new)
    # Also fix mine() to break early on 429
    old_mine = """        items = _search_api(q) if API_KEY else _search_web(q)
        for item in items:"""
    new_mine = """        if not API_KEY:
            items = _search_web(q)
        else:
            items = _search_api(q)
            if not items and QUERIES.index(q) > 0:
                break
        for item in items:"""
    if old_mine in content:
        content = content.replace(old_mine, new_mine)

    # Write back via heredoc
    proc2 = subprocess.run(
        ["ssh", "quant@95.216.191.70",
         f"cat > /home/quant/quant-platform/desks/mt5/side_channels/youtube_miner.py << 'PYEOF'\n{content}\nPYEOF"],
        capture_output=True, text=True, timeout=15
    )
    print("YouTube miner patched:", "OK" if proc2.returncode == 0 else proc2.stderr[:200])
else:
    print("YouTube miner: patch target not found, skipping")

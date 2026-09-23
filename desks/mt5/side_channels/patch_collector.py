#!/usr/bin/env python3
"""Patch collect_x_signals.py: add x.com SSR fallback (Nitter is dead)."""
from pathlib import Path

p = Path("/home/quant/quant-platform/scripts/collect_x_signals.py")
src = p.read_text()

if "_try_xcom_ssr" in src:
    print("Already patched")
    raise SystemExit

fn = '''

def _try_xcom_ssr(account: str, limit: int = 20) -> list[dict[str, Any]]:
    """Fetch tweets from x.com server-side-rendered profile HTML (no auth)."""
    import html as _html
    import re as _re
    import urllib.request
    ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36"
    try:
        req = urllib.request.Request(
            f"https://x.com/{account}",
            headers={"User-Agent": ua, "Accept": "text/html"},
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode("utf-8", errors="replace")
    except Exception:
        return []
    items: list[dict] = []
    seen: set[str] = set()
    for tid in sorted(set(_re.findall(r'data-tweet-id="(\\d+)"', html))):
        if len(items) >= limit:
            break
        idx = html.find(f'data-tweet-id="{tid}"')
        if idx < 0:
            continue
        window = html[idx:idx + 12000]
        segments = [_html.unescape(s.strip()) for s in _re.findall(r">([^<>]{40,800})<", window)]
        parts: list[str] = []
        for s in segments:
            if s not in seen and not s.startswith("http") and " " in s and len(s) >= 40:
                seen.add(s)
                parts.append(s)
            if len(parts) >= 3:
                break
        text = " ".join(parts).strip()
        if not text:
            continue
        likes = _re.search(r'aria-label="([\\d,]+) likes"', window)
        replies = _re.search(r'aria-label="([\\d,]+) replies"', window)
        reposts = _re.search(r'aria-label="([\\d,]+) reposts"', window)
        posted = _re.search(r'<time datetime="([^"]+)"', window)
        metrics = {}
        if likes:
            metrics["like_count"] = int(likes.group(1).replace(",", ""))
        if replies:
            metrics["reply_count"] = int(replies.group(1).replace(",", ""))
        if reposts:
            metrics["retweet_count"] = int(reposts.group(1).replace(",", ""))
        items.append({
            "account": account,
            "text": text[:500],
            "url": f"https://x.com/{account}/status/{tid}",
            "timestamp": posted.group(1) if posted else "",
            "cashtags": list(CASTAG_RE.findall(text.upper())),
            "metrics": metrics,
            "source": "xcom_ssr",
        })
    return items


'''

marker = "# Optional: Twitter API v2 (requires bearer token in env)"
if marker not in src:
    print("Marker not found")
    raise SystemExit(2)
src = src.replace(marker, fn + marker)

old_main = """    # 1) Free Nitter RSS for high-signal accounts
    for acct in CRYPTO_ACCOUNTS:
        all_items.extend(_try_nitter(acct, limit=15))
        time.sleep(0.2)"""
new_main = """    # 1) Nitter RSS -> x.com SSR fallback for high-signal accounts
    for acct in CRYPTO_ACCOUNTS:
        items = _try_nitter(acct, limit=15)
        if not items:
            items = _try_xcom_ssr(acct, limit=15)
        all_items.extend(items)
        time.sleep(0.3)"""
if old_main not in src:
    print("Main loop pattern not found")
    raise SystemExit(3)
src = src.replace(old_main, new_main)

p.write_text(src)
print("Patched OK")
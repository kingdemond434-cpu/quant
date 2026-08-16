#!/usr/bin/env python3
"""
Deep-mine priority X accounts (l1vsun, shmidtqq, antpalkin) for research systems,
quant data and article content. Uses x.com SSR HTML (no auth needed), extracts
tweets, links, engagement, then follows external article links (substack,
medium, blogs, telegram) to pull full research text.

    python scripts/deep_mine_x.py            # all priority accounts
    python scripts/deep_mine_x.py l1vsun     # single account

Writes:
    data/x_deep_mine/{account}_{YYYYMMDD}.json
    data/x_deep_mine/index.json             (latest run summary)
    data/x_deep_mine.parquet                (append-only per-tweet rows)
    agent_feed entries (type=research_intel)
"""

from __future__ import annotations

import html as html_mod
import json
import re
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36"

PRIORITY_ACCOUNTS = ["L1vsun", "shmidtqq", "antpalkin"]
OUT_DIR = Path("data/x_deep_mine")
PARQUET = Path("data/x_deep_mine.parquet")
MAX_ARTICLES_PER_RUN = 6

ARTICLE_DOMAINS_OK = re.compile(
    r"(substack\.com|medium\.com|mirror\.xyz|paragraph\.xyz|telegram\.org|t\.me|"
    r"blog\..*|\.blog|notion\.site|ghost\.io|hashnode\.dev|dev\.to|github\.com)"
)
EXTERNAL_LINK_RE = re.compile(r'href="(https?://[^"]+)"')
TCO_RE = re.compile(r"https://t\.co/\w+")


def fetch(url: str, timeout: int = 20) -> str:
    import urllib.request
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html,application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def extract_tweets(html: str) -> list[dict]:
    tweets = []
    ids = sorted(set(re.findall(r'data-tweet-id="(\d+)"', html)))
    for tid in ids:
        idx = html.find(f'data-tweet-id="{tid}"')
        if idx < 0:
            continue
        window = html[idx:idx + 12000]
        segments = re.findall(r">([^<>]{40,800})<", window)
        segments = [html_mod.unescape(s.strip()) for s in segments]
        segments = [s for s in segments if not s.startswith("http") and " " in s]
        seen: set[str] = set()
        text_parts: list[str] = []
        for s in segments:
            if s not in seen and len(s) >= 40:
                seen.add(s)
                text_parts.append(s)
            if len(text_parts) >= 4:
                break
        text = " ".join(text_parts).strip()
        links = []
        for m in EXTERNAL_LINK_RE.finditer(window):
            url = m.group(1)
            if not re.search(r"(twitter\.com|x\.com|twimg\.com)", url):
                links.append(TCO_RE.sub("", url).rstrip("&amp;"))
        likes = re.search(r'aria-label="([\d,]+) likes"', window)
        replies = re.search(r'aria-label="([\d,]+) replies"', window)
        rt = re.search(r'aria-label="([\d,]+) reposts"', window)
        time_match = re.search(r'<time datetime="([^"]+)"', window)
        if text:
            tweets.append({
                "tweet_id": tid,
                "text": text[:2000],
                "links": list(dict.fromkeys(links))[:5],
                "likes": int(likes.group(1).replace(",", "")) if likes else None,
                "replies": int(replies.group(1).replace(",", "")) if replies else None,
                "reposts": int(rt.group(1).replace(",", "")) if rt else None,
                "posted_at": time_match.group(1) if time_match else None,
            })
    return tweets


def extract_article(url: str) -> str | None:
    try:
        html = fetch(url, timeout=15)
    except Exception:
        return None
    for pat in [r'<meta property="og:description" content="([^"]{80,1000})"',
                r'<meta name="description" content="([^"]{80,1000})"']:
        m = re.search(pat, html)
        if m:
            return html_mod.unescape(m.group(1))
    main = re.search(r"<article[^>]*>(.*?)</article>", html, re.S)
    body = main.group(1) if main else html
    body = re.sub(r"<script.*?</script>", " ", body, flags=re.S)
    body = re.sub(r"<style.*?</style>", " ", body, flags=re.S)
    body = re.sub(r"<[^>]+>", " ", body)
    body = html_mod.unescape(re.sub(r"\s+", " ", body)).strip()
    return body[:4000] if len(body) >= 200 else None


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    accounts = sys.argv[1:] if len(sys.argv) > 1 else PRIORITY_ACCOUNTS
    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    today = datetime.now(UTC).strftime("%Y%m%d")
    rows = []
    index: dict = {"run_id": run_id, "accounts": {}}

    for acct in accounts:
        acct_l = acct.lower()
        profile = {"account": acct, "name": None, "bio": None, "followers": None,
                   "tweets": [], "articles": []}
        try:
            html = fetch(f"https://x.com/{acct}")
            title = re.search(r"<title>([^<]*)</title>", html)
            desc = re.search(r'<meta property="og:description" content="([^"]*)"', html)
            profile["name"] = html_mod.unescape(title.group(1)) if title else None
            profile["bio"] = html_mod.unescape(desc.group(1)) if desc else None
            fcount = re.search(r'aria-label="([\d,]+) followers"', html)
            profile["followers"] = int(fcount.group(1).replace(",", "")) if fcount else None
            tweets = extract_tweets(html)
            profile["tweets"] = tweets
            for t in tweets:
                rows.append({
                    "run_id": run_id, "account": acct_l, "tweet_id": t["tweet_id"],
                    "text": t["text"], "links": json.dumps(t["links"]),
                    "likes": t["likes"], "replies": t["replies"], "reposts": t["reposts"],
                    "posted_at": t["posted_at"], "fetched_at": datetime.now(UTC).isoformat(),
                })
                for url in t["links"]:
                    if not ARTICLE_DOMAINS_OK.search(url):
                        continue
                    article_text = extract_article(url)
                    if article_text:
                        profile["articles"].append({"url": url, "text": article_text})
                        rows.append({
                            "run_id": run_id, "account": acct_l, "tweet_id": t["tweet_id"],
                            "text": f"[ARTICLE] {article_text}", "links": json.dumps([url]),
                            "likes": None, "replies": None, "reposts": None,
                            "posted_at": t["posted_at"], "fetched_at": datetime.now(UTC).isoformat(),
                        })
        except Exception as e:
            profile["error"] = str(e)
        with open(OUT_DIR / f"{acct_l}_{today}.json", "w", encoding="utf-8") as f:
            json.dump(profile, f, indent=2, ensure_ascii=False)
        index["accounts"][acct_l] = {
            "name": profile["name"], "bio": profile["bio"],
            "followers": profile["followers"], "tweets": len(profile["tweets"]),
            "articles": len(profile["articles"]), "error": profile.get("error"),
        }
        print(f"{acct}: {len(profile['tweets'])} tweets, {len(profile['articles'])} articles")

    with open(OUT_DIR / "index.json", "w", encoding="utf-8") as f:
        json.dump(index, f, indent=2)

    if rows:
        new_df = pd.DataFrame(rows)
        if PARQUET.exists():
            old = pd.read_parquet(PARQUET)
            df = pd.concat([old, new_df], ignore_index=True)
        else:
            df = new_df
        df.to_parquet(PARQUET, index=False)
        print(f"total rows: {len(df)} -> {PARQUET}")

    try:
        import subprocess
        summary = " | ".join(
            f"{a}: {v['tweets']} tweets/{v['articles']} articles" for a, v in index["accounts"].items()
        )
        subprocess.run(
            ["/home/quant/quant-platform/.venv/bin/python",
             "/home/quant/quant-platform/scripts/agent_feed.py", "write",
             "--type", "research_intel", "--agent", "x_deep_mine",
             "--payload", json.dumps({"summary": summary, "index": index})],
            capture_output=True, timeout=30,
        )
    except Exception:
        pass


if __name__ == "__main__":
    main()
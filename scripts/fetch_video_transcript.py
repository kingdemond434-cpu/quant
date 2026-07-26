#!/usr/bin/env python3
"""VIDEO TRANSCRIPT FETCHER -- free, keyless, works from this VPS (verified 2026-07-26).

REFUTES a standing desk belief. prospector_coverage.md recorded "VIDEO: direct transcript fetch is
IP-BLOCKED from this VPS (RequestBlocked, tested 07-18)", and GAP #26 gated a PAID residential-proxy
purchase on that finding. The direct youtube.com/api/timedtext route does return empty from here --
that part was right -- but PIPED instances (open-source YouTube proxies) serve the same caption
tracks fine: api.piped.private.coffee returned 6 subtitle tracks and 2,165 characters of real
transcript text on first try. The paid unlock is not needed for YouTube.

Instances die often, so this rotates through several and reports which one served. Bilibili is
handled through its own public API (subtitle list -> json subtitle file).

    fetch_video_transcript.py <youtube-url-or-id> [--lang en]
    fetch_video_transcript.py --bilibili <BVid>
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
import urllib.request

# Public Piped instances, tried in order. Add more as they appear -- they rotate constantly.
_PIPED = (
    "https://api.piped.private.coffee",
    "https://pipedapi.kavin.rocks",
    "https://pipedapi.adminforge.de",
    "https://api.piped.yt",
)
_UA = {"User-Agent": "Mozilla/5.0 (quant-desk video-transcript)"}


def _get(url: str, timeout: int = 25) -> bytes:
    return urllib.request.urlopen(urllib.request.Request(url, headers=_UA), timeout=timeout).read()


def _clean(raw: str) -> str:
    """Strip caption markup (XML/VTT) down to readable prose."""
    txt = re.sub(r"<[^>]+>", " ", raw)
    txt = re.sub(r"^\d+\s*$|^[\d:.,\s>-]+$", " ", txt, flags=re.M)   # cue numbers / timestamps
    txt = html.unescape(txt)
    return re.sub(r"\s+", " ", txt).strip()


def youtube(video: str, lang: str = "en") -> tuple[str, str]:
    """Return (transcript, instance) for a YouTube id/URL, trying each Piped instance."""
    vid = video
    m = re.search(r"(?:v=|youtu\.be/|shorts/)([A-Za-z0-9_-]{11})", video)
    if m:
        vid = m.group(1)
    last = ""
    for host in _PIPED:
        try:
            meta = json.loads(_get(f"{host}/streams/{vid}").decode())
            subs = meta.get("subtitles") or []
            if not subs:
                last = f"{host}: no subtitle tracks"
                continue
            pick = next((s for s in subs if (s.get("code") or "").startswith(lang)), subs[0])
            text = _clean(_get(pick["url"], timeout=35).decode(errors="ignore"))
            if text:
                return text, host
            last = f"{host}: empty caption body"
        except Exception as exc:
            last = f"{host}: {type(exc).__name__} {exc}"
    raise SystemExit(f"all Piped instances failed -- last: {last}")


def bilibili(bvid: str, lang: str = "") -> tuple[str, str]:
    """Bilibili captions via its own public API (view -> cid -> subtitle json)."""
    view = json.loads(_get(f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}").decode())
    if view.get("code") != 0:
        raise SystemExit(f"bilibili view failed: code={view.get('code')} {view.get('message')}")
    data = view["data"]
    cid = data["cid"]
    pl = json.loads(_get(
        f"https://api.bilibili.com/x/player/v2?bvid={bvid}&cid={cid}").decode())
    subs = (pl.get("data", {}).get("subtitle", {}) or {}).get("subtitles", []) or []
    if not subs:
        raise SystemExit(f"bilibili: no public subtitles for {bvid} ({data.get('title','')[:40]})")
    pick = next((s for s in subs if lang and lang in str(s.get("lan", ""))), subs[0])
    url = pick["subtitle_url"]
    if url.startswith("//"):
        url = "https:" + url
    body = json.loads(_get(url).decode())
    return " ".join(x.get("content", "") for x in body.get("body", [])), "api.bilibili.com"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--lang", default="en")
    ap.add_argument("--bilibili", action="store_true")
    a = ap.parse_args()
    text, src = (bilibili(a.video, a.lang) if a.bilibili else youtube(a.video, a.lang))
    print(f"[transcript via {src}] {len(text)} chars\n")
    sys.stdout.write(text)


if __name__ == "__main__":
    main()

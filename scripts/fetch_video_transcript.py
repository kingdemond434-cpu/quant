#!/usr/bin/env python3
"""VIDEO TRANSCRIPT FETCHER -- free, keyless, multi-family route rotation.

YOUTUBE IS REFUSED, 2026-11-14 (governance/wayback-youtube-ruling-2026-11-14.md). The Piped and
Invidious rotation described below was a mirror route around YouTube's own terms, which is
banned, so it was removed: `youtube()` raises TranscriptUnavailable carrying the terms reason and
its missed_growth line, and sends no request. Bilibili is unaffected. The measured history below
is kept because it records why no YouTube route ever served.

ROUTE STATUS, MEASURED 2026-08-27 (supersedes the 2026-07-26 "works from this VPS" claim, which
is no longer true and had been silently returning nothing for weeks):

  * youtube.com/api/timedtext and /youtubei/  -- SS13 HARD STOP, not a failure. youtube.com
    robots.txt Disallow: /api/ and Disallow: /youtubei/ under User-agent: *, so the caption-track
    and InnerTube routes are barred by the site's own access preference. Never route around this.
  * PIPED  -- 11/11 public instances from the TeamPiped directory dead or refusing (403/502/DNS/
    SSL) on 2026-08-27. The four instances hardcoded here before today had ALL DNS-failed.
  * INVIDIOUS -- 11/11 public instances: the caption INDEX serves (200 + a real track list) but
    the caption TEXT serves 200 with ZERO bytes. A 200 is not content (desk lesson).

So YouTube transcript retrieval is currently UNRESOLVED from this box on every legitimate
automated route tested (22 endpoints). Callers must record that as ACCESS_LIMIT with the video
retained in the retry queue -- NEVER as an empty/clean result, and never as "the video held
nothing". Bilibili is unaffected and still works through its own public API.

Instance lists rotate constantly, so this refreshes from the public directories rather than
trusting the hardcoded seeds below (LAWS anti-hardcode: seeds, never a boundary).

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

_UA = {"User-Agent": "quant-desk-video-transcript/1.0 (research)"}

#: YouTube transcripts are refused on every automated route (Governance,
#: governance/wayback-youtube-ruling-2026-11-14.md): no YouTube API key, the box never contacts
#: YouTube, and a keyless Piped/Invidious mirror is YouTube content reached around YouTube's own
#: terms -- a banned mirror route. youtube() therefore sends no request at all.
YOUTUBE_TERMS = ("terms-refused: YouTube transcripts through YouTube or any keyless mirror "
                 "(Piped, Invidious) are refused (wayback-youtube-ruling-2026-11-14)")
YOUTUBE_MISSED_GROWTH = ("missed_growth: no YouTube transcripts reach the video lanes; "
                         "video mechanisms are mined from text, code and Bilibili routes")


def _get(url: str, timeout: int = 25) -> bytes:
    with urllib.request.urlopen(
            urllib.request.Request(url, headers=_UA), timeout=timeout) as resp:
        body: bytes = resp.read()
    return body


def _clean(raw: str) -> str:
    """Strip caption markup (XML/VTT) down to readable prose."""
    txt = re.sub(r"<[^>]+>", " ", raw)
    txt = re.sub(r"^\d+\s*$|^[\d:.,\s>-]+$", " ", txt, flags=re.M)   # cue numbers / timestamps
    txt = html.unescape(txt)
    return re.sub(r"\s+", " ", txt).strip()


class TranscriptUnavailable(RuntimeError):
    """Every legitimate route was tried and none served text.

    Distinct from "the video has no captions" and distinct from "the video held nothing": callers
    MUST record this as ACCESS_LIMIT and keep the video in the retry queue (video-hunter brief:
    a video skipped without a record is indistinguishable from a video that contained nothing).
    """

    def __init__(self, attempts: list[str]) -> None:
        self.attempts = attempts
        super().__init__(f"no route served text; {len(attempts)} attempted: "
                         + "; ".join(attempts[-6:]))


def youtube(video: str, lang: str = "en") -> tuple[str, str]:
    """Refused on terms: always raises TranscriptUnavailable with the terms reason and its
    missed_growth line, before any request. Callers record ACCESS_LIMIT, never an empty
    transcript, so the video stays a named gap rather than reading as one that held nothing."""
    raise TranscriptUnavailable([f"{YOUTUBE_TERMS}; {YOUTUBE_MISSED_GROWTH}"])


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
    try:
        text, src = (bilibili(a.video, a.lang) if a.bilibili else youtube(a.video, a.lang))
    except TranscriptUnavailable as exc:
        # ACCESS_LIMIT, not "nothing there": exit non-zero so no caller reads silence as a result.
        print(f"ACCESS_LIMIT {a.video}: {exc}", file=sys.stderr)
        raise SystemExit(3) from None
    print(f"[transcript via {src}] {len(text)} chars\n")
    sys.stdout.write(text)


if __name__ == "__main__":
    main()

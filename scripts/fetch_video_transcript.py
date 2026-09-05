#!/usr/bin/env python3
"""VIDEO TRANSCRIPT FETCHER -- free, keyless, multi-family route rotation.

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

# SEEDS ONLY (LAWS anti-hardcode): the live list is refreshed from the public directories at
# call time; these are the fallback if the directory fetch fails. Both families are tried because
# they fail independently -- Piped by host death, Invidious by empty caption bodies.
_PIPED = (
    "https://pipedapi.adminforge.de",
    "https://pipedapi.kavin.rocks",
    "https://pipedapi.drgns.space",
    "https://pipedapi.reallyaweso.me",
)
_PIPED_DIRECTORY = ("https://raw.githubusercontent.com/TeamPiped/documentation/main/"
                    "content/docs/public-instances/index.md")
_INVIDIOUS_DIRECTORY = "https://api.invidious.io/instances.json"

_UA = {"User-Agent": "Mozilla/5.0 (quant-desk video-transcript)"}


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


def _live_piped() -> list[str]:
    """Refresh Piped hosts from the public directory; fall back to the seeds on any failure."""
    try:
        md = _get(_PIPED_DIRECTORY, timeout=20).decode("utf-8", "replace")
        hosts = sorted(set(re.findall(r"https?://[a-z0-9.-]*pipedapi[a-z0-9.-]*", md)))
        return hosts or list(_PIPED)
    except Exception:
        return list(_PIPED)


def _live_invidious() -> list[str]:
    """Public Invidious instances reachable over https, best-uptime first."""
    try:
        data = json.loads(_get(_INVIDIOUS_DIRECTORY, timeout=20).decode())
    except Exception:
        return []
    out = []
    for _name, info in data:
        uri = (info or {}).get("uri") or ""
        if info and info.get("type") == "https" and uri.startswith("https://"):
            mon = info.get("monitor") or {}
            out.append((-(mon.get("uptime") or 0.0), uri))
    return [u for _s, u in sorted(out)]


def _invidious_text(host: str, vid: str, lang: str) -> str:
    """Invidious caption route. Its index frequently serves while its TEXT serves zero bytes --
    that empty body is the documented 2026-08-27 failure mode and must not read as success."""
    body = _get(f"{host}/api/v1/captions/{vid}", timeout=25)
    if not body.lstrip().startswith(b"{"):
        raise ValueError("not json (tarpit/interstitial html)")
    caps = json.loads(body).get("captions") or []
    if not caps:
        raise ValueError("no caption tracks")
    pick = next((c for c in caps if (c.get("languageCode") or "").startswith(lang)), caps[0])
    url = pick.get("url") or ""
    if url.startswith("/"):
        url = host + url
    return _clean(_get(url, timeout=35).decode(errors="ignore"))


def youtube(video: str, lang: str = "en") -> tuple[str, str]:
    """Return (transcript, route) for a YouTube id/URL, rotating Piped then Invidious.

    Raises TranscriptUnavailable listing every attempt -- callers record ACCESS_LIMIT, never an
    empty transcript. An empty caption body counts as a FAILURE of that route, not as a result.
    """
    vid = video
    m = re.search(r"(?:v=|youtu\.be/|shorts/)([A-Za-z0-9_-]{11})", video)
    if m:
        vid = m.group(1)
    attempts: list[str] = []
    for host in _live_piped():
        try:
            meta = json.loads(_get(f"{host}/streams/{vid}").decode())
            subs = meta.get("subtitles") or []
            if not subs:
                attempts.append(f"{host}: no subtitle tracks")
                continue
            pick = next((s for s in subs if (s.get("code") or "").startswith(lang)), subs[0])
            text = _clean(_get(pick["url"], timeout=35).decode(errors="ignore"))
            if text:
                return text, host
            attempts.append(f"{host}: empty caption body")
        except Exception as exc:
            attempts.append(f"{host}: {type(exc).__name__} {exc}")
    for host in _live_invidious():
        try:
            text = _invidious_text(host, vid, lang)
            if text:
                return text, host
            attempts.append(f"{host}: empty caption body")
        except Exception as exc:
            attempts.append(f"{host}: {type(exc).__name__} {exc}")
    raise TranscriptUnavailable(attempts)


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

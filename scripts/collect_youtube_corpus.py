#!/usr/bin/env python3
"""Token-free YouTube corpus collector (principal 2026-08-25: the video miner's enumeration
belongs in Python + the Data API, not in Claude's context).

Role split per the corpora-first law: THIS script gathers -- channels, uploads, titles,
descriptions, tags, and every external link in a description (creators link their TradingView
scripts, MQL5 pages and blogs there: the black-box corpus entry points). The daily video-hunter
dig then spends its tokens ONLY on judgment over data/intelligence/youtube/.

Seeds live in data/youtube_channels.json -- a REGISTRY, never a boundary (LAWS anti-hardcode):
the dig adds channels it judges worth following; this collector also discovers candidates via
keyword search when quota allows. Quota ledger: search costs 100 units, list costs 1, default
daily quota 10,000 -- the collector budgets and records spend, and stands down before exhausting
it (a starved key tomorrow costs more than a thinner sweep today).

    .venv/bin/python scripts/collect_youtube_corpus.py            # incremental daily sweep
"""
from __future__ import annotations

import json
import re
import sys
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KEYFILE = ROOT / "data" / "secrets" / "youtube_api_key"
REGISTRY = ROOT / "data" / "youtube_channels.json"
OUTDIR = ROOT / "data" / "intelligence" / "youtube"
COVERAGE = ROOT / "data" / "intelligence" / "video_channel_coverage.json"

API = "https://www.googleapis.com/youtube/v3"
SEARCH_COST, LIST_COST = 100, 1
UNIT_BUDGET = 2_000            # per run; well under the 10k/day default quota
MAX_VIDEOS_PER_CHANNEL = 50    # per run; cursoring covers the backlog across days

#: Seed corpus from the video-hunter brief -- the creators whose reverse-engineered strategies
#: produced hunt16/19/20 and the desk's only exact certificate. SEEDS, not a boundary.
SEED_QUERIES = [
    "DaviddTech", "ResponsibleForexTrading", "Lewis Jackson trading", "Goshawk Trades",
    "Unbiased Trading", "AI Pathways trading", "IQ Capital trading",
]
LINK_RE = re.compile(r"https?://[^\s)\"']+")


def api(endpoint: str, spent: list[int], cost: int, **params) -> dict:
    if spent[0] + cost > UNIT_BUDGET:
        raise RuntimeError(f"unit budget {UNIT_BUDGET} would be exceeded; standing down")
    params["key"] = KEYFILE.read_text("utf-8").strip()
    url = f"{API}/{endpoint}?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(url, timeout=30) as r:
        spent[0] += cost
        return json.load(r)


def read_json(p: Path, default):
    try:
        return json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return default


def main() -> int:
    if not KEYFILE.exists():
        print("youtube key absent (data/secrets/youtube_api_key) -- nothing collected, "
              "exiting quietly; the dig falls back to text/code routes")
        return 0
    now = datetime.now(tz=UTC)
    reg = read_json(REGISTRY, {"channels": {}, "discovered": {}})
    spent = [0]
    report = {"ts": now.isoformat(), "videos": 0, "channels_swept": 0, "new_links": 0,
              "discovered_channels": 0, "units_spent": 0, "errors": []}
    rows: list[dict] = []

    try:
        # 1. DISCOVERY: resolve any seed/registered name lacking a channel id (search = 100u,
        # so at most a few per run; once resolved, never searched again).
        unresolved = [q for q in SEED_QUERIES if q not in reg["channels"]
                      and q not in reg["discovered"]][:3]
        for q in unresolved:
            try:
                d = api("search", spent, SEARCH_COST, part="snippet", q=q,
                        type="channel", maxResults=3)
                for item in d.get("items", []):
                    cid = item["id"]["channelId"]
                    title = item["snippet"]["title"]
                    reg["discovered"].setdefault(q, {})[cid] = title
                    report["discovered_channels"] += 1
                reg["channels"].setdefault(q, {})   # mark resolved even if empty
            except Exception as exc:                                     # noqa: BLE001
                report["errors"].append(f"search {q}: {exc}")

        # 2. ENUMERATION: for every followed channel id, incremental uploads sweep.
        follow: dict[str, str] = {}
        for q, hits in reg["discovered"].items():
            follow.update(hits)
        follow.update({cid: t for cid, t in reg.get("follow", {}).items()})
        for cid, title in list(follow.items()):
            try:
                ch = api("channels", spent, LIST_COST, part="contentDetails", id=cid)
                items = ch.get("items", [])
                if not items:
                    continue
                uploads = items[0]["contentDetails"]["relatedPlaylists"]["uploads"]
                cursor = reg.setdefault("cursors", {}).get(cid)
                page, fetched = None, 0
                newest_seen = cursor
                while fetched < MAX_VIDEOS_PER_CHANNEL:
                    kw = {"part": "snippet", "playlistId": uploads, "maxResults": 50}
                    if page:
                        kw["pageToken"] = page
                    pl = api("playlistItems", spent, LIST_COST, **kw)
                    stop = False
                    for it in pl.get("items", []):
                        sn = it["snippet"]
                        pub = sn.get("publishedAt", "")
                        if cursor and pub <= cursor:
                            stop = True
                            break
                        newest_seen = max(newest_seen or "", pub)
                        desc = sn.get("description", "")
                        links = LINK_RE.findall(desc)
                        rows.append({
                            "channel_id": cid, "channel": title,
                            "video_id": sn.get("resourceId", {}).get("videoId"),
                            "published": pub, "title": sn.get("title"),
                            "description": desc[:2000], "links": links,
                        })
                        report["new_links"] += len(links)
                        fetched += 1
                    page = pl.get("nextPageToken")
                    if stop or not page:
                        break
                if newest_seen:
                    reg["cursors"][cid] = newest_seen
                report["channels_swept"] += 1
            except Exception as exc:                                     # noqa: BLE001
                report["errors"].append(f"channel {title}: {exc}")
    except RuntimeError as exc:
        report["errors"].append(str(exc))

    report["videos"] = len(rows)
    report["units_spent"] = spent[0]
    OUTDIR.mkdir(parents=True, exist_ok=True)
    if rows:
        out = OUTDIR / f"videos_{now:%Y%m%d}.json"
        existing = read_json(out, [])
        (out).write_text(json.dumps(existing + rows, indent=1), "utf-8")
    REGISTRY.write_text(json.dumps(reg, indent=1), "utf-8")
    cov = read_json(COVERAGE, {})
    cov.update({"last_sweep": now.isoformat(), **report})
    COVERAGE.write_text(json.dumps(cov, indent=1), "utf-8")
    print(f"youtube corpus: {report['videos']} new videos, {report['new_links']} links, "
          f"{report['channels_swept']} channels, {report['discovered_channels']} discovered, "
          f"{spent[0]} units, errors={len(report['errors'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

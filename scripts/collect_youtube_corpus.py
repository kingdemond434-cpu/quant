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
import os
import re
import sys
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fetch_video_transcript import TranscriptUnavailable as _TranscriptUnavailable
from fetch_video_transcript import youtube as _yt_transcript

ROOT = Path(__file__).resolve().parent.parent
KEYFILE = ROOT / "data" / "secrets" / "youtube_api_key"
#: The trading box keeps secrets under the desk (C:\\opt\\quant\\desks\\mt5\\data\\secrets); the VPS
#: under the repo root (KEYFILE). Either file, or the YOUTUBE_API_KEY environment variable, is the key.
DESK_KEYFILE = ROOT / "desks" / "mt5" / "data" / "secrets" / "youtube_api_key"
REGISTRY = ROOT / "data" / "youtube_channels.json"
OUTDIR = ROOT / "data" / "intelligence" / "youtube"
COVERAGE = ROOT / "data" / "intelligence" / "video_channel_coverage.json"

API = "https://www.googleapis.com/youtube/v3"
SEARCH_COST, LIST_COST = 100, 1
UNIT_BUDGET = 2_000            # per run, and never more than what is left of today's quota
DAILY_UNIT_BUDGET = 9_000      # under the 10k/day default: the collector now runs every hour
MAX_VIDEOS_PER_CHANNEL = 50    # NEW uploads per channel per run
BACKFILL_PAGES_PER_CHANNEL = 2  # older uploads per channel per run, walked from a saved page
MAX_NEW_FOLLOWS_PER_RUN = 25   # channels the sweep starts following on its own each run
#: Searched for CHANNELS, one per run in rotation, when the search quota answers. A list that
#: wraps, so discovery never ends; channels found through it, through featured-channel sections
#: and through links in video descriptions are followed without a hand-edit.
DISCOVERY_QUERIES = [
    "forex strategy backtest", "gold trading strategy backtest", "session breakout strategy",
    "mean reversion forex strategy", "trend following strategy backtest",
    "algorithmic trading strategy results", "prop firm challenge strategy",
    "MT5 expert advisor strategy", "carry trade forex", "volatility breakout strategy",
    "indices trading strategy backtest", "oil trading strategy", "silver trading strategy",
    "orderflow trading strategy", "seasonality trading strategy", "news trading strategy NFP",
]
CHANNEL_LINK_RE = re.compile(r"youtube\.com/(?:channel/(UC[A-Za-z0-9_-]{22})|@([A-Za-z0-9_.-]{3,40}))")

#: Seed corpus from the video-hunter brief -- the creators whose reverse-engineered strategies
#: produced hunt16/19/20 and the desk's only exact certificate. SEEDS, not a boundary.
SEED_QUERIES = [
    "DaviddTech", "ResponsibleForexTrading", "Lewis Jackson trading", "Goshawk Trades",
    "Unbiased Trading", "AI Pathways trading", "IQ Capital trading",
    # zuck's 2026-11-03 channels (config/video_mining_channels.json, PR #655), by exact handle
    "@QuantGuild", "@Algovibes", "@saleh.m",
]
#: The video-mining channel config, when present, adds its handles to the seeds (a REGISTRY,
#: never a boundary): a channel added there is followed here without a code change.
CHANNEL_CONFIG = ROOT / "config" / "video_mining_channels.json"


def seed_queries() -> list[str]:
    seeds = list(SEED_QUERIES)
    try:
        rows = json.loads(CHANNEL_CONFIG.read_text("utf-8")).get("channels", [])
    except (OSError, ValueError, AttributeError):
        rows = []
    for row in rows if isinstance(rows, list) else []:
        h = str((row or {}).get("handle") or "").strip() if isinstance(row, dict) else ""
        if h.startswith("@") and h not in seeds:
            seeds.append(h)
    return seeds
LINK_RE = re.compile(r"https?://[^\s)\"']+")


def api(endpoint: str, spent: list[int], cost: int, **params) -> dict:
    if spent[0] + cost > UNIT_BUDGET:
        raise RuntimeError(f"unit budget {UNIT_BUDGET} would be exceeded; standing down")
    params["key"] = _key()
    url = f"{API}/{endpoint}?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(url, timeout=30) as r:
        spent[0] += cost
        return json.load(r)


def _key() -> str:
    """The key: YOUTUBE_API_KEY, else the key file on either host's layout. Measured 2026-11-03:
    the box carries the key as a User-scope environment variable and has NO key file, so a
    file-only read left the collector "exiting quietly" there forever. MT5-Dept-Intel runs as
    SYSTEM, which cannot see User-scope variables, so the desk secrets file is read too. The value
    is never printed or written."""
    env = os.environ.get("YOUTUBE_API_KEY", "").strip()
    if env:
        return env
    for f in (KEYFILE, DESK_KEYFILE):
        try:
            k = f.read_text("utf-8").strip()
        except OSError:
            continue
        if k:
            return k
    return ""


def _redact(text: str) -> str:
    """Scrub the key out of an error string before it can reach the report.

    The report lands under data/intelligence/, which is published, and some urllib/http.client
    exceptions echo the request URL -- which carries `key=`. Every appended error passes here.
    """
    k = _key()
    text = str(text)
    if k:
        text = text.replace(k, "***")
    return re.sub(r"([?&]key=)[^&\s'\"]+", r"\1***", text)


def read_json(p: Path, default):
    try:
        return json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return default


TRANSCRIPTS_PER_RUN = 10    # best-effort, polite; misses go to a retry queue, never dropped
TRANSCRIPT_QUEUE_MAX = 5_000


def fetch_transcript(video_id: str) -> tuple[str | None, str | None]:
    """Return (text, unresolved_reason) via the shared multi-route fetcher.

    THE POINT OF THE SECOND RETURN VALUE: this collector previously swallowed every failure into
    None and reported `transcripts: 0` with no reason, so 512 enumerated videos carried ZERO
    transcripts for weeks and the coverage ledger looked merely quiet. A miss is now typed --
    ACCESS_LIMIT when every legitimate route refused, TRANSCRIPT_UNAVAILABLE when the video
    genuinely has no public captions -- exactly the vocabulary the video-hunter brief requires so
    the retry queue stays economic and a blocked video never reads as an empty one.

    The route itself is scripts/fetch_video_transcript.py (Piped + Invidious rotation). This
    collector must NOT grow a second private copy: youtube.com's own /api/ and /youtubei/ caption
    routes are robots-Disallowed (SS13 hard stop) and the previous inline implementation was
    reading exactly those.
    """
    try:
        text, _route = _yt_transcript(video_id)
    except _TranscriptUnavailable as exc:
        reason = ("TRANSCRIPT_UNAVAILABLE"
                  if all("no subtitle tracks" in a or "no caption tracks" in a
                         for a in exc.attempts) and exc.attempts
                  else "ACCESS_LIMIT")
        return None, reason
    except Exception:
        return None, "FETCH_FAILED"
    return (text[:20000], None) if text else (None, "TRANSCRIPT_UNAVAILABLE")


#: THE BOX CLOCK (2026-11-03). The VPS timer `ops/quant-youtube-corpus.timer` (hourly, :37) was
#: this collector's only clock; the box held a mirror, so the corpus froze when the VPS did (last
#: real file videos_20261022.json). hourly_cycle now runs it as the `youtube_corpus` leg of the
#: intel department, whose passes can come faster than hourly, so a pass inside MIN_INTERVAL_S of
#: the last recorded sweep returns NOT_DUE without spending a unit.
MIN_INTERVAL_S = 3_000


def _not_due(now: datetime) -> float | None:
    """Seconds since the last sweep when it is under MIN_INTERVAL_S, else None (due)."""
    last = read_json(COVERAGE, {}).get("last_sweep")
    try:
        age = (now - datetime.fromisoformat(str(last))).total_seconds()
    except (TypeError, ValueError):
        return None
    return age if 0 <= age < MIN_INTERVAL_S else None


def main() -> int:
    if "--force" not in sys.argv[1:]:
        age = _not_due(datetime.now(tz=UTC))
        if age is not None:
            print(f"youtube corpus: NOT_DUE (last sweep {int(age)}s ago)")
            return 0
    now = datetime.now(tz=UTC)
    if not _key():
        # L1.28a: an absent key is a verdict, written where the ledger is read -- never a quiet 0.
        cov = read_json(COVERAGE, {})
        cov.update({"last_sweep": now.isoformat(), "status": "KEY_MISSING",
                    "why": "no YOUTUBE_API_KEY and no youtube_api_key file on this host"})
        COVERAGE.parent.mkdir(parents=True, exist_ok=True)
        COVERAGE.write_text(json.dumps(cov, indent=1), "utf-8")
        print("youtube key absent -- KEY_MISSING written to the coverage ledger")
        return 0
    reg = read_json(REGISTRY, {"channels": {}, "discovered": {}})
    reg.setdefault("channels", {})
    reg.setdefault("discovered", {})
    day = f"{now:%Y-%m-%d}"
    quota = reg.setdefault("quota", {})
    for d in [d for d in quota if d != day]:
        quota.pop(d, None)
    left_today = max(DAILY_UNIT_BUDGET - int(quota.get(day, 0)), 0)
    # `spent` starts at what this run may NOT spend, so `api` stands down at today's remainder.
    spent = [UNIT_BUDGET - min(UNIT_BUDGET, left_today)]
    spent_at_start = spent[0]
    report = {"ts": now.isoformat(), "videos": 0, "channels_swept": 0, "new_links": 0,
              "discovered_channels": 0, "units_spent": 0, "errors": []}
    rows: list[dict] = []
    known: set[str] = set()
    new_follows = 0

    try:
        # 1. DISCOVERY, forHandle FIRST (1 unit vs search's 100 -- and the project's search
        # quota was measured exhausted on day one while list quota was untouched). Handles are
        # guessed from the seed name with spaces stripped; a miss falls back to ONE budgeted
        # search only when the search quota works at all this run.
        search_dead = False
        unresolved = [q for q in seed_queries() if q not in reg["channels"]
                      and q not in reg["discovered"]][:6]
        for q in unresolved:
            # An exact "@handle" seed is used as given; a name seed has its handle guessed.
            handle = q if q.startswith("@") else "@" + re.sub(r"[^A-Za-z0-9]", "", q)
            try:
                d = api("channels", spent, LIST_COST, part="snippet", forHandle=handle)
                items = d.get("items", [])
                if items:
                    cid, title = items[0]["id"], items[0]["snippet"]["title"]
                    reg["discovered"].setdefault(q, {})[cid] = title
                    reg["channels"].setdefault(q, {})
                    report["discovered_channels"] += 1
                    continue
            except Exception as exc:
                report["errors"].append(_redact(f"forHandle {handle}: {exc}"))
            if search_dead:
                continue
            try:
                d = api("search", spent, SEARCH_COST, part="snippet", q=q,
                        type="channel", maxResults=3)
                for item in d.get("items", []):
                    cid = item["id"]["channelId"]
                    reg["discovered"].setdefault(q, {})[cid] = item["snippet"]["title"]
                    report["discovered_channels"] += 1
                reg["channels"].setdefault(q, {})
            except Exception as exc:
                search_dead = True
                report["errors"].append(_redact(f"search {q}: {exc}"))

        # 1b. DISCOVERY THAT NEVER ENDS (2026-11-03, principal: "always fetches videos of all
        # channel searches everythin unknonws similar"). One rotating channel search per run;
        # the rest is free of search quota: featured-channel sections of channels already
        # followed (1 unit each) and channel links found in video descriptions (0 units).
        auto = reg["discovered"].setdefault("auto", {})
        for hits in reg["discovered"].values():
            known.update(hits)
        known.update(reg.get("follow", {}))
        if not search_dead:
            i = int(reg.get("discovery_cursor", 0))
            q = DISCOVERY_QUERIES[i % len(DISCOVERY_QUERIES)]
            reg["discovery_cursor"] = i + 1
            try:
                d = api("search", spent, SEARCH_COST, part="snippet", q=q, type="channel",
                        maxResults=10)
                for item in d.get("items", []):
                    cid = item["id"]["channelId"]
                    if cid not in known and new_follows < MAX_NEW_FOLLOWS_PER_RUN:
                        auto[cid] = item["snippet"]["title"]
                        known.add(cid)
                        new_follows += 1
            except Exception as exc:
                report["errors"].append(_redact(f"discovery search {q}: {exc}"))
        sect_cur = int(reg.get("sections_cursor", 0))
        followed = sorted(known)
        for cid in followed[sect_cur % max(len(followed), 1):][:10] if followed else []:
            try:
                d = api("channelSections", spent, LIST_COST, part="contentDetails",
                        channelId=cid)
            except Exception as exc:
                report["errors"].append(_redact(f"channelSections {cid}: {exc}"))
                break
            for sec in d.get("items", []):
                for sim in (sec.get("contentDetails") or {}).get("channels", []) or []:
                    if sim not in known and new_follows < MAX_NEW_FOLLOWS_PER_RUN:
                        auto[sim] = f"featured by {cid}"
                        known.add(sim)
                        new_follows += 1
        reg["sections_cursor"] = sect_cur + 10
        report["discovered_channels"] += new_follows

        # 2. ENUMERATION: for every followed channel id, incremental uploads sweep.
        follow: dict[str, str] = {}
        for _q, hits in reg["discovered"].items():
            follow.update(hits)
        follow.update(dict(reg.get("follow", {}).items()))
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
                # BACKFILL: the first sweep took the newest 50 and the rest of the channel was
                # never read. Older pages are walked from a saved token until the channel's
                # start, then the channel is marked walked (new uploads still arrive above).
                bf = reg.setdefault("backfill", {})
                tok = bf.get(cid, page or "DONE")
                for _ in range(BACKFILL_PAGES_PER_CHANNEL):
                    if tok == "DONE":
                        break
                    pl = api("playlistItems", spent, LIST_COST, part="snippet",
                             playlistId=uploads, maxResults=50, pageToken=tok)
                    for it in pl.get("items", []):
                        sn = it["snippet"]
                        desc = sn.get("description", "")
                        links = LINK_RE.findall(desc)
                        rows.append({
                            "channel_id": cid, "channel": title,
                            "video_id": sn.get("resourceId", {}).get("videoId"),
                            "published": sn.get("publishedAt", ""), "title": sn.get("title"),
                            "description": desc[:2000], "links": links, "backfill": True,
                        })
                        report["new_links"] += len(links)
                    tok = pl.get("nextPageToken") or "DONE"
                bf[cid] = tok
                report["channels_swept"] += 1
            except Exception as exc:
                report["errors"].append(_redact(f"channel {title}: {exc}"))
    except RuntimeError as exc:
        report["errors"].append(_redact(str(exc)))

    # 2b. Channels named in descriptions are followed next run (0 units; handles resolved then).
    pending = reg.setdefault("pending_handles", [])
    for row in rows:
        for m in CHANNEL_LINK_RE.finditer(row.get("description") or ""):
            cid_, handle = m.group(1), m.group(2)
            if cid_ and cid_ not in known and new_follows < MAX_NEW_FOLLOWS_PER_RUN:
                reg["discovered"].setdefault("auto", {})[cid_] = f"linked by {row['channel_id']}"
                known.add(cid_)
                new_follows += 1
            elif handle and handle not in pending and len(pending) < 500:
                pending.append(handle)
    for handle in list(pending)[:10]:
        try:
            d = api("channels", spent, LIST_COST, part="snippet", forHandle="@" + handle)
        except Exception:
            break
        pending.remove(handle)
        for it in d.get("items", []):
            if it["id"] not in known:
                reg["discovered"].setdefault("auto", {})[it["id"]] = it["snippet"]["title"]
                known.add(it["id"])
                report["discovered_channels"] += 1

    # 3. TRANSCRIPTS, best-effort, newest videos first, hard-capped per run. A miss is queued
    # and retried on later runs (the old collector tried each video once, only the run it was
    # new, and dropped it), so a route that comes back serves the whole backlog.
    got_t, attempted = 0, 0
    unresolved: dict[str, int] = {}
    queue = reg.setdefault("transcript_queue", [])
    queued_rows = [{"video_id": v, "queued": True} for v in queue
                   if v not in {r.get("video_id") for r in rows}]
    for row in sorted(rows, key=lambda r: r.get("published", ""), reverse=True) + queued_rows:
        if got_t >= TRANSCRIPTS_PER_RUN:
            break
        vid = row.get("video_id")
        if not vid:
            continue
        attempted += 1
        t, reason = fetch_transcript(vid)
        row["transcript"] = t
        row["transcript_status"] = "NEAR_FULL" if t else "UNAVAILABLE"
        # start/end are NOT verified by an automated pull -- the brief requires both before any
        # extraction may be recorded, so this route can never mint a FULL row on its own.
        row["start_verified"] = False
        row["end_verified"] = False
        if reason:
            row["unresolved_reason"] = reason
            unresolved[reason] = unresolved.get(reason, 0) + 1
            if reason != "TRANSCRIPT_UNAVAILABLE" and vid not in queue:
                queue.append(vid)
        if t:
            got_t += 1
            if vid in queue:
                queue.remove(vid)
            if row.get("queued"):
                rows.append({"video_id": vid, "transcript": t, "transcript_status": "NEAR_FULL",
                             "start_verified": False, "end_verified": False, "retried": True})
    del queue[:-TRANSCRIPT_QUEUE_MAX]
    report["transcript_queue"] = len(queue)
    report["transcripts"] = got_t
    report["transcript_attempts"] = attempted
    report["transcripts_unresolved"] = unresolved
    if attempted and not got_t:
        # L1.28a: a silent zero is not a clean verdict. Say so where the ledger is read.
        report["errors"].append(
            f"TRANSCRIPT ROUTE DEAD: {attempted} attempted, 0 served ({unresolved}) -- "
            "video-hunter Role A is blind until a route is restored")

    report["videos"] = len(rows)
    report["units_spent"] = spent[0] - spent_at_start
    quota[day] = int(quota.get(day, 0)) + report["units_spent"]
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
          f"{report['units_spent']} units, errors={len(report['errors'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

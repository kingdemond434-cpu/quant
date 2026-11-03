#!/usr/bin/env python3
"""Mine EVERY video of the channels in channels.json: enumerate, fetch public captions, keep a
coverage ledger proving no video was skipped.

Rules (desk LAWS 5e + principal rulings):
  * Public captions only, via the normal public routes (yt-dlp enumeration, youtube-transcript-api).
  * NO bypass: no cookies, no logins, no proxies, no CAPTCHA solving. If YouTube serves a bot wall
    / IP block, the run STOPS and every remaining video is recorded ACCESS_LIMIT (retry later).
  * Polite pacing (sleep between caption fetches).
  * Resumable: videos already FULL / NO_TRANSCRIPT are not refetched.

Outputs (under --out, default ./video_mining_out):
  ledger.jsonl                       one row per video, latest row per video_id wins
  transcripts/<handle>/<video_id>.txt
  descriptions/<handle>/<video_id>.txt  video description
  links.json                         every description link -> videos citing it
  coverage_summary.json              counts per channel per status
  video_mining_out.zip               everything above, for transfer

Usage:
  pip install -U yt-dlp youtube-transcript-api
  python mine_channel_transcripts.py --config config/video_mining_channels.json [--sleep 6] [--limit N]
"""
from __future__ import annotations

import argparse
import json
import random
import shutil
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

#: Discovery never adopts a crypto-exchange's own channel (MT5 mandate; crypto = CFDs only).
EXCHANGE_BRANDS = ("binance", "coinbase", "kraken", "bybit", "okx", "kucoin", "bitget",
                   "gate.io", "huobi", "htx", "mexc", "bitfinex", "bitmex", "deribit", "crypto.com")

_ROOT = Path(__file__).resolve().parent.parent
#: The box-side coverage proof (written by --report-only in the hourly Quant-VideoCells run).
REPORT = _ROOT / "desks" / "mt5" / "reports" / "VIDEO_MINING_COVERAGE.json"

STATUSES = ("FULL", "NO_TRANSCRIPT", "UNAVAILABLE", "ACCESS_LIMIT", "FETCH_FAILED")


def now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def channel_url(handle: str) -> str:
    return (f"https://www.youtube.com/channel/{handle}" if handle.startswith("UC")
            else f"https://www.youtube.com/{handle}")


def enumerate_tab(handle: str, tab: str) -> list[dict]:
    url = f"{channel_url(handle)}/{tab}"
    cmd = [sys.executable, "-m", "yt_dlp", "--flat-playlist", "-J", "--no-warnings", url]
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if p.returncode != 0:
        msg = (p.stderr or "").strip().splitlines()[-1:] or [""]
        if "does not have a" in msg[0] or "This channel does not have" in msg[0]:
            return []
        raise RuntimeError(f"enumerate {handle}/{tab} failed: {msg[0][:300]}")
    data = json.loads(p.stdout)
    out = []
    for e in data.get("entries") or []:
        # streams/videos tabs can nest playlists one level deep
        for x in (e.get("entries") or [e]):
            vid = x.get("id")
            if vid and len(vid) == 11:
                out.append({"video_id": vid, "title": x.get("title") or "",
                            "duration": x.get("duration"), "tab": tab})
    return out


LINK_RE = None


def fetch_description(vid: str) -> tuple[str, list[str], dict]:
    """Public video metadata (description + every link in it) via yt-dlp, no download."""
    import re
    global LINK_RE
    LINK_RE = LINK_RE or re.compile(r"https?://[^\s)\"'<>]+")
    cmd = [sys.executable, "-m", "yt_dlp", "--skip-download", "-J", "--no-warnings",
           f"https://www.youtube.com/watch?v={vid}"]
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if p.returncode != 0:
        return "", [], {"desc_error": ((p.stderr or "").strip().splitlines() or [""])[-1][:200]}
    d = json.loads(p.stdout)
    desc = d.get("description") or ""
    meta = {"upload_date": d.get("upload_date"), "duration": d.get("duration"),
            "view_count": d.get("view_count"), "chapters": [c.get("title") for c in
                                                          (d.get("chapters") or [])]}
    return desc, sorted(set(LINK_RE.findall(desc))), meta


def discover(cfg: dict, out: Path, per_query: int) -> list[dict]:
    """Find NEW quant/strategy channels from config search queries (public search pages via
    yt-dlp, one request per query). Discovered channels are appended to discovered.json with
    status CANDIDATE; the yield ranker (cells passing the judge per video) promotes or prunes."""
    path = out / "discovered.json"
    disc = json.loads(path.read_text("utf-8")) if path.exists() else {}
    known = {c["handle"] for c in cfg["channels"]} | set(disc)
    for q in cfg.get("discovery_queries", []):
        cmd = [sys.executable, "-m", "yt_dlp", "--flat-playlist", "-J", "--no-warnings",
               f"ytsearch{per_query}:{q}"]
        p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                           errors="replace")
        if p.returncode != 0:
            print(f"[discover] {q!r}: error, stopping discovery this run", flush=True)
            break
        for e in (json.loads(p.stdout).get("entries") or []):
            cid = e.get("channel_id")
            if not cid or cid in known:
                continue
            cname = (e.get("channel") or e.get("uploader") or "").lower()
            if any(b in cname for b in EXCHANGE_BRANDS):
                continue  # MT5 mandate: no crypto-exchange channels as a hunted universe
            known.add(cid)
            disc[cid] = {"handle": cid, "name": e.get("channel") or e.get("uploader") or "",
                         "found_by": q, "found_ts": now(), "status": "CANDIDATE",
                         "videos_mined": 0, "cells_passed": 0}
            print(f"[discover] + {cid} {disc[cid]['name']} (via {q!r})", flush=True)
        time.sleep(5)
    path.write_text(json.dumps(disc, indent=1, ensure_ascii=False), encoding="utf-8")
    return [d for d in disc.values() if d["status"] in ("CANDIDATE", "ACTIVE")]


def load_ledger(path: Path) -> dict[str, dict]:
    rows: dict[str, dict] = {}
    if path.exists():
        for line in path.read_text("utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                rows[r["video_id"]] = r
    return rows


def fetch_transcript(api, vid: str):
    """Return (status, text, meta)."""
    from youtube_transcript_api import _errors as E  # type: ignore

    blocked = tuple(getattr(E, n) for n in ("RequestBlocked", "IpBlocked", "TooManyRequests")
                    if hasattr(E, n))
    none = tuple(getattr(E, n) for n in ("TranscriptsDisabled", "NoTranscriptFound")
                 if hasattr(E, n))
    gone = tuple(getattr(E, n) for n in ("VideoUnavailable", "VideoUnplayable", "AgeRestricted",
                                          "InvalidVideoId") if hasattr(E, n))
    try:
        tl = api.list(vid)
        tr = None
        for finder in ("find_manually_created_transcript", "find_generated_transcript"):
            try:
                tr = getattr(tl, finder)(["en", "en-US", "en-GB"])
                break
            except none:
                continue
        if tr is None:
            first = next(iter(tl), None)
            if first is None:
                return "NO_TRANSCRIPT", "", {}
            tr = first.translate("en") if getattr(first, "is_translatable", False) else first
        fetched = tr.fetch()
        snippets = getattr(fetched, "snippets", fetched)
        parts, last_end = [], 0.0
        for s in snippets:
            txt = s.text if hasattr(s, "text") else s["text"]
            st = s.start if hasattr(s, "start") else s["start"]
            du = s.duration if hasattr(s, "duration") else s.get("duration", 0)
            parts.append(f"[{int(st)//60:02d}:{int(st)%60:02d}] {txt}")
            last_end = max(last_end, float(st) + float(du or 0))
        meta = {"language": getattr(tr, "language_code", ""),
                "generated": bool(getattr(tr, "is_generated", False)),
                "caption_end_s": round(last_end, 1), "snippets": len(parts)}
        return ("FULL" if parts else "NO_TRANSCRIPT"), "\n".join(parts), meta
    except blocked as exc:
        return "ACCESS_LIMIT", "", {"error": type(exc).__name__}
    except none as exc:
        return "NO_TRANSCRIPT", "", {"error": type(exc).__name__}
    except gone as exc:
        return "UNAVAILABLE", "", {"error": type(exc).__name__}
    except Exception as exc:
        return "FETCH_FAILED", "", {"error": f"{type(exc).__name__}: {str(exc)[:200]}"}


def coverage(ledger: dict[str, dict], enum_report: dict, stopped: str | None) -> dict:
    """Per-channel status counts (every enumerated video has exactly one) + distinct links."""
    summary: dict = {"ts": now(), "enumeration": enum_report, "stopped": stopped, "channels": {}}
    for r in ledger.values():
        c = summary["channels"].setdefault(r["channel"], {})
        c[r["status"]] = c.get(r["status"], 0) + 1
    for c in summary["channels"].values():
        c["total"] = sum(c.values())
    links: dict[str, list[str]] = {}
    for r in ledger.values():
        for u in r.get("links", []):
            links.setdefault(u, []).append(r["video_id"])
    summary["distinct_links"] = len(links)
    summary["_links"] = links
    return summary


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config/video_mining_channels.json")
    ap.add_argument("--out", default="video_mining_out")
    ap.add_argument("--sleep", type=float, default=45.0, help="base seconds between caption fetches")
    ap.add_argument("--limit", type=int, default=0, help="max caption fetches this run (0 = all)")
    ap.add_argument("--discover", action="store_true",
                    help="also find new channels from config discovery_queries")
    ap.add_argument("--per-query", type=int, default=20)
    ap.add_argument("--backoff-min", type=float, default=90.0,
                    help="after an access wall, later runs exit until this many minutes pass")
    ap.add_argument("--report-only", action="store_true",
                    help="no network: publish the coverage report from an existing ledger "
                         "(the box's hourly Quant-VideoCells run uses this on unsealed bundles)")
    ap.add_argument("--report", default="", help="also write the coverage summary here")
    args = ap.parse_args()

    if args.report_only:
        led = load_ledger(Path(args.out) / "ledger.jsonl")
        summary = coverage(led, {}, None)
        summary.pop("_links")
        summary["mode"] = "report-only (box)"
        rep = Path(args.report) if args.report else REPORT
        rep.parent.mkdir(parents=True, exist_ok=True)
        rep.write_text(json.dumps(summary, indent=1), encoding="utf-8")
        print(json.dumps({k: summary[k] for k in ("channels", "distinct_links")}))
        return 0

    from youtube_transcript_api import YouTubeTranscriptApi  # type: ignore
    api = YouTubeTranscriptApi()

    cfg = json.loads(Path(args.config).read_text("utf-8"))
    out = Path(args.out)
    (out / "transcripts").mkdir(parents=True, exist_ok=True)
    wall = out / "last_access_wall.txt"
    if wall.exists():
        age_min = (time.time() - wall.stat().st_mtime) / 60
        walls = wall.read_text("utf-8").count("\n")
        need = args.backoff_min * min(2 ** max(walls - 1, 0), 8)   # 90, 180, 360, 720 min cap
        if age_min < need:
            print(f"in backoff after access wall #{walls} ({age_min:.0f} < {need:.0f} min)")
            return 0
    ledger_path = out / "ledger.jsonl"
    ledger = load_ledger(ledger_path)
    lf = ledger_path.open("a", encoding="utf-8")

    def write(row: dict) -> None:
        ledger[row["video_id"]] = row
        lf.write(json.dumps(row, ensure_ascii=False) + "\n")
        lf.flush()

    # 1. enumerate every tab of every channel (a video is never silently dropped)
    todo: list[dict] = []
    enum_report = {}
    channels = list(cfg["channels"])
    if args.discover:
        channels += [{"handle": d["handle"], "tabs": ["videos"]}
                     for d in discover(cfg, out, args.per_query)]
    for ch in channels:
        seen = set()
        for tab in ch.get("tabs", ["videos", "shorts", "streams"]):
            try:
                vids = enumerate_tab(ch["handle"], tab)
            except Exception as exc:
                enum_report[f"{ch['handle']}/{tab}"] = f"ERROR {exc}"
                print(f"[enum] {ch['handle']}/{tab}: ERROR {exc}", flush=True)
                continue
            enum_report[f"{ch['handle']}/{tab}"] = len(vids)
            print(f"[enum] {ch['handle']}/{tab}: {len(vids)} videos", flush=True)
            for v in vids:
                if v["video_id"] in seen:
                    continue
                seen.add(v["video_id"])
                v["channel"] = ch["handle"]
                prev = ledger.get(v["video_id"])
                if (prev and prev["status"] in ("FULL", "NO_TRANSCRIPT", "UNAVAILABLE")
                        and ("links" in prev or v.get("tab") == "shorts")):
                    continue
                if not prev:
                    write({**v, "status": "PENDING", "ts": now()})
                todo.append(v)

    # long-form first (where mechanisms live), shorts last
    order = {"videos": 0, "streams": 1, "shorts": 2}
    todo.sort(key=lambda v: order.get(v.get("tab"), 3))

    # 2. fetch captions, politely; stop the whole run at the first access wall (no bypass)
    stopped = None
    for fetched, v in enumerate(todo, 1):
        if args.limit and fetched > args.limit:
            break
        prev = ledger.get(v["video_id"]) or {}
        if prev.get("status") in ("FULL", "NO_TRANSCRIPT", "UNAVAILABLE"):
            status, text, meta = prev["status"], None, {}
        else:
            status, text, meta = fetch_transcript(api, v["video_id"])
        row = {**prev, **v, "status": status, "ts": now(), **meta}
        if status != "ACCESS_LIMIT" and v.get("tab") != "shorts":
            desc, links, dmeta = fetch_description(v["video_id"])
            row.update(dmeta)
            row["links"] = links
            if desc:
                dd = out / "descriptions" / v["channel"].lstrip("@")
                dd.mkdir(parents=True, exist_ok=True)
                (dd / f"{v['video_id']}.txt").write_text(desc, encoding="utf-8")
        if status == "FULL" and text is not None:
            d = out / "transcripts" / v["channel"].lstrip("@")
            d.mkdir(parents=True, exist_ok=True)
            (d / f"{v['video_id']}.txt").write_text(
                f"# {v['title']}\n# https://www.youtube.com/watch?v={v['video_id']}\n{text}\n",
                encoding="utf-8")
            row["chars"] = len(text)
        write(row)
        if status == "FULL" and wall.exists() and fetched >= 20:
            wall.unlink()   # a clean stretch resets the escalation
        print(f"[{fetched}/{len(todo)}] {v['channel']} {v['video_id']} {status} "
              f"{row.get('chars', '')} {v['title'][:60]}", flush=True)
        if status == "ACCESS_LIMIT":
            stopped = f"access wall at {v['video_id']} ({meta.get('error')}); stopping, no bypass"
            print(stopped, flush=True)
            with wall.open("a", encoding="utf-8") as wf:
                wf.write(f"{now()} {stopped}\n")
            break
        # jitter for polite pacing only, not security
        time.sleep(args.sleep + random.uniform(0, args.sleep / 2))  # noqa: S311
    lf.close()

    # 3. coverage summary: every enumerated video has exactly one status
    summary = coverage(ledger, enum_report, stopped)
    links = summary.pop("_links")
    (out / "links.json").write_text(json.dumps(links, indent=1), encoding="utf-8")
    (out / "coverage_summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    print(json.dumps(summary, indent=1))

    zip_base = out.parent / "video_mining_out"
    shutil.make_archive(str(zip_base), "zip", root_dir=out)
    print(f"zip: {zip_base}.zip")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

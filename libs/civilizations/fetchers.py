"""Three fetchers the civilizations need that the #133 spine did not have, registered into
`libs.mining.acquirer.FETCHERS` at import (same signature, same cursor contract).

  git_mirror  a PUBLIC git repository mirrored with a blob-less partial clone. The durable
              cursor is the commit SHA: the first runs BACKFILL every file matching the lane's
              `paths` globs (`walk_pos` advances per run, so nothing is re-read); after that only
              files changed between the cursor SHA and the new HEAD are emitted (the DELTA
              scan), plus one `commit` item per new commit when `commits: true`. No API rate
              limit and no key: git over HTTPS works where api.github.com is throttled.
  sitemap     a site's sitemap(s) -> every URL matching `item_regex`, fetched once each, the
              `<lastmod>` kept in the cursor so a changed page is re-fetched (the PIT store
              makes it a new vintage). This is how a client-rendered listing (the QuantConnect
              Strategy Library's first-30-titles stub) is replaced by the full article set:
              the article pages are server-rendered even when the listing is not.
  youtube_channel  one public channel's uploads (the 2026-10-06 Quant Guild directive: "monitor
              new public video descriptions/transcripts when accessible"). With the YouTube
              Data API key the box holds, the uploads playlist is walked newest page first and
              then backwards by `pageToken` until the whole back catalogue is read, each video
              with its FULL description; without the key, the channel's public RSS feed (the
              latest uploads) keeps the delta alive. Transcripts are recorded per video as NOT
              ACCESSIBLE and why: the Data API's captions.download needs the channel owner's
              OAuth grant, and the unofficial caption endpoint is not a published API.
"""
from __future__ import annotations

import fnmatch
import json
import os
import re
import subprocess
import threading
import time
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any

from libs.civilizations import licence as LIC
from libs.mining import acquirer as acq

MIRRORS = Path("desks/mt5/data/civilizations/git_mirrors")
GIT_TIMEOUT_S = 600
MAX_FILE_BYTES = 400_000
#: data files are never read from a mirror: a competition's or vendor's dataset is licensed for
#: its own use, and only the code and prose around it (method, features, validation) are mined
DATA_EXCLUDE: tuple[str, ...] = (
    # tabular and serialised data
    "*.csv", "*.tsv", "*.json", "*.jsonl", "*.ndjson", "*.txt", "*.dat", "*.parquet", "*.feather",
    "*.arrow", "*.h5", "*.hdf5", "*.pkl", "*.pickle", "*.npy", "*.npz", "*.xls", "*.xlsx",
    "*.db", "*.sqlite", "*.sqlite3", "*.mat", "*.rds", "*.RData",
    # model weights
    "*.pt", "*.pth", "*.ckpt", "*.onnx", "*.safetensors", "*.bin", "*.joblib", "*.model",
    "*.pb", "*.tflite", "*.weights",
    # archives
    "*.zip", "*.gz", "*.tgz", "*.tar", "*.bz2", "*.xz", "*.7z", "*.rar", "*.zst")
NOTICES = Path("desks/mt5/data/civilizations/notices")


def _git(args: list[str], cwd: Path | None, timeout: float) -> tuple[int, str]:
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
    try:
        p = subprocess.run(["git", *args], cwd=str(cwd) if cwd else None, env=env,
                           capture_output=True, text=True, timeout=max(5.0, timeout),
                           encoding="utf-8", errors="replace")
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 1, f"{type(exc).__name__}: {exc}"
    return p.returncode, (p.stdout if p.returncode == 0 else (p.stderr or p.stdout))


def _remaining(ctx: acq.FetchContext) -> float:
    return max(5.0, min(GIT_TIMEOUT_S, ctx.deadline - time.monotonic()))


def _match(path: str, globs: list[str], exclude: list[str] | None = None) -> bool:
    if exclude and any(fnmatch.fnmatch(path, g) for g in exclude):
        return False
    return not globs or any(fnmatch.fnmatch(path, g) for g in globs)


_LOCKS: dict[str, threading.Lock] = {}
_LOCKS_GUARD = threading.Lock()


def mirror_dir(src: acq.Source, ctx: acq.FetchContext) -> Path:
    """Lanes that read one repository through different path globs share ONE mirror
    (`config.mirror`), so LEAN is cloned once however many lanes cut it."""
    key = str(src.config.get("mirror") or src.id)
    return Path(ctx.root) / MIRRORS / re.sub(r"[^\w.-]", "_", key)


def _lock(d: Path) -> threading.Lock:
    with _LOCKS_GUARD:
        return _LOCKS.setdefault(str(d), threading.Lock())


def fetch_git_mirror(src: acq.Source, cursor: dict[str, Any], ctx: acq.FetchContext
                     ) -> Iterator[acq.Item]:
    """Serialised per mirror: concurrent lanes on one repository take turns on git."""
    with _lock(mirror_dir(src, ctx)):
        yield from _fetch_git_mirror(src, cursor, ctx)


def _fetch_git_mirror(src: acq.Source, cursor: dict[str, Any], ctx: acq.FetchContext
                      ) -> Iterator[acq.Item]:
    cfg = src.config
    repo = str(cfg.get("repo") or "")
    if not repo:
        return
    web = repo[:-4] if repo.endswith(".git") else repo
    globs = [str(g) for g in (cfg.get("paths") or [])]
    excl = [str(g) for g in (cfg.get("exclude") or [])] + list(DATA_EXCLUDE)
    per_run = int(cfg.get("files_per_run") or 150)
    d = mirror_dir(src, ctx)
    if not (d / ".git").exists():
        d.parent.mkdir(parents=True, exist_ok=True)
        rc, out = _git(["clone", "-q", "--filter=blob:none", "--no-checkout", "--depth",
                        str(int(cfg.get("depth") or 50)), repo, str(d)], None, _remaining(ctx))
        if rc != 0:
            ctx.blocked.append(f"{repo} -> clone failed: {out[:160]}")
            return
    else:
        rc, out = _git(["fetch", "-q", "--filter=blob:none", "--depth",
                        str(int(cfg.get("depth") or 50)), "origin"], d, _remaining(ctx))
        if rc != 0:
            ctx.blocked.append(f"{repo} -> fetch failed: {out[:160]}")
            return
    rc, head = _git(["rev-parse", "FETCH_HEAD" if (d / ".git" / "FETCH_HEAD").exists()
                     else "HEAD"], d, 30)
    if rc != 0:
        rc, head = _git(["rev-parse", "HEAD"], d, 30)
    head = head.strip()
    if rc != 0 or not head:
        ctx.blocked.append(f"{repo} -> no HEAD")
        return
    ctx.ok_fetches += 1
    spdx, lic_text = _licence(d, head, cfg)
    if lic_text:
        n = Path(ctx.root) / NOTICES / (re.sub(r"[^\w.-]", "_", web.split("github.com/")[-1])
                                         + ".txt")
        n.parent.mkdir(parents=True, exist_ok=True)
        if not n.exists():
            n.write_text(f"{web}\nSPDX: {spdx}\n\n{lic_text}", "utf-8")
    last = str(cursor.get("last_sha") or "")
    walk_pos = int(cursor.get("walk_pos") or 0)
    backfill_done = bool(cursor.get("backfill_done"))
    if not backfill_done and cfg.get("backfill") is False:
        # a delta-only lane (commits): start the cursor at today's HEAD, emit nothing old
        yield acq.Item(uri="", body="", cursor_update={"last_sha": head, "backfill_done": True})
        return
    if not backfill_done:
        rc, listing = _git(["ls-tree", "-r", "--name-only", head], d, 120)
        files = sorted(p for p in listing.splitlines() if _match(p, globs, excl)) if rc == 0 else []
        todo = files[walk_pos: walk_pos + per_run]
        new_pos = walk_pos + len(todo)
        done = new_pos >= len(files)
        upd_base = {"walk_pos": new_pos, "backfill_done": done, "walk_total": len(files),
                    "walk_sha": head}
        if done:
            upd_base["last_sha"] = head
        changed = todo
        kind = "file"
    else:
        if last == head:
            yield acq.Item(uri="", body="", cursor_update={"last_sha": head})
            return
        rc, diff = _git(["diff", "--name-only", last, head], d, 120) if last else (1, "")
        if rc != 0:                       # history no longer reaches the cursor: re-walk
            yield acq.Item(uri="", body="", cursor_update={"backfill_done": False,
                                                           "walk_pos": 0})
            return
        changed = sorted(p for p in diff.splitlines() if _match(p, globs, excl))[:per_run * 4]
        upd_base = {"last_sha": head}
        kind = "delta"
    for path in changed:
        if ctx.expired():
            return
        if LIC.LICENCE_FILE.match(path.rsplit("/", 1)[-1]):
            continue                                   # kept once under notices/, not a record
        rc, body = _git(["show", f"{head}:{path}"], d, _remaining(ctx))
        if rc != 0:
            continue                                   # deleted in the delta
        if len(body) > MAX_FILE_BYTES:
            body = body[:MAX_FILE_BYTES]
        body, lmeta = LIC.keep(path, body, spdx, lic_text, web)
        yield acq.Item(uri=f"{web}/blob/{head}/{path}", title=path, body=body,
                       cursor_update={}, meta={"item_kind": "file", "path": path, "sha": head,
                                               "scan": kind, "repo": web, **lmeta})
    if cfg.get("commits") and last and backfill_done:
        rc, log = _git(["log", "--format=%H%x1f%aI%x1f%s%x1f%b%x1e", "--name-only",
                        f"{last}..{head}"], d, 120)
        if rc == 0:
            for block in log.split("\x1e"):
                parts = block.strip().split("\x1f")
                if len(parts) < 4:
                    continue
                sha, when, subj, rest = parts[0], parts[1], parts[2], parts[3]
                keep_body = f"{subj}\n{rest}" if LIC.is_permissive(spdx) else subj
                yield acq.Item(uri=f"{web}/commit/{sha}", title=subj, body=keep_body,
                               publication_time=when, cursor_update={},
                               meta={"item_kind": "commit", "sha": sha, "repo": web})
    yield acq.Item(uri="", body="", cursor_update={**upd_base, "licence": spdx})


def _licence(d: Path, head: str, cfg: Mapping[str, Any]) -> tuple[str, str]:
    """(SPDX, licence text) of the repository at `head`. A lane may DECLARE its licence
    (`config.licence`) only to name one the file states in words this detector misses; an
    undetectable, absent or unreadable licence is NOASSERTION/NONE, which keeps metadata only."""
    rc, top = _git(["ls-tree", "--name-only", head], d, 60)
    names = [n for n in top.splitlines() if LIC.LICENCE_FILE.match(n)] if rc == 0 else []
    if not names:
        return "NONE", ""
    rc, text = _git(["show", f"{head}:{names[0]}"], d, 60)
    if rc != 0:
        return "NONE", ""
    found = LIC.detect(text)
    return (str(cfg.get("licence")) if found == "NOASSERTION" and cfg.get("licence")
            else found), text[:20_000]


_LOC = re.compile(r"(?is)<url>\s*<loc>\s*([^<\s]+)\s*</loc>(?:.*?<lastmod>\s*([^<\s]+)\s*"
                  r"</lastmod>)?")
_SUBMAP = re.compile(r"(?is)<sitemap>\s*<loc>\s*([^<\s]+)\s*</loc>")


def fetch_sitemap(src: acq.Source, cursor: dict[str, Any], ctx: acq.FetchContext
                  ) -> Iterator[acq.Item]:
    cfg = src.config
    rx = re.compile(str(cfg.get("item_regex") or ".")) if cfg.get("item_regex") else None
    per_run = int(cfg.get("pages_per_run") or 60)
    mods: dict[str, str] = dict(cursor.get("lastmod") or {})
    maps = [str(u) for u in (cfg.get("sitemaps") or [cfg.get("url") or ""]) if u]
    urls: list[tuple[str, str]] = []
    seen_maps: set[str] = set()
    while maps and len(seen_maps) < 60 and not ctx.expired():
        m = maps.pop(0)
        if m in seen_maps:
            continue
        seen_maps.add(m)
        r = ctx.fetch(m)
        if not r.ok:
            continue
        maps.extend(u for u in _SUBMAP.findall(r.text) if u not in seen_maps)
        urls.extend((u, lm or "") for u, lm in _LOC.findall(r.text) if not rx or rx.search(u))
    fresh = [(u, lm) for u, lm in urls if u not in mods or (lm and mods.get(u) != lm)]
    for u, lm in fresh[:per_run]:
        if ctx.expired():
            break
        r = ctx.fetch(u)
        if not r.ok:
            continue
        mods[u] = lm or mods.get(u) or "seen"
        yield acq.Item(uri=u, title=acq.html_title(r.text), body=acq.html_to_text(r.text),
                       publication_time=acq.html_time(r.text),
                       cursor_update={"lastmod": dict(mods)},
                       meta={"item_kind": "page", "lastmod": lm})
    yield acq.Item(uri="", body="", cursor_update={"lastmod": dict(mods),
                                                   "sitemap_urls": len(urls),
                                                   "sitemap_pending": max(0, len(fresh)
                                                                          - per_run)})


YT_API = "https://www.googleapis.com/youtube/v3"
YT_FEED = "https://www.youtube.com/feeds/videos.xml?channel_id="
#: what each video record says about its transcript (the directive's "when accessible")
TRANSCRIPT_STATUS = ("NOT_ACCESSIBLE: the YouTube Data API's captions.download requires OAuth "
                     "authorisation from the channel owner, and the unofficial timedtext "
                     "endpoint is not a published API; the full description is mined instead")
_YT_ENTRY = re.compile(r"(?is)<entry\b.*?</entry>")


def youtube_key(src: acq.Source, ctx: acq.FetchContext) -> str:
    """The Data API key from the environment, else the box's own secrets file
    (data/secrets/youtube.json, which never leaves the box). Never logged or stored."""
    key = os.environ.get(src.auth_env or "YOUTUBE_API_KEY", "").strip()
    if key:
        return key
    try:
        doc = json.loads((ctx.root / "data" / "secrets" / "youtube.json").read_text("utf-8"))
    except (OSError, ValueError):
        return ""
    if isinstance(doc, Mapping):
        for k in ("YOUTUBE_API_KEY", "api_key", "key"):
            if str(doc.get(k) or "").strip():
                return str(doc[k]).strip()
    return ""


def _yt_item(vid: str, title: str, body: str, when: str | None, cursor: dict[str, Any],
             channel: str, via: str) -> acq.Item:
    return acq.Item(uri=f"https://www.youtube.com/watch?v={vid}", title=title,
                    body=body, publication_time=when or None,
                    cursor_update=acq._seen_add(cursor, vid),
                    meta={"item_kind": "video", "channel": channel, "via": via,
                          "transcript": TRANSCRIPT_STATUS})


def fetch_youtube_channel(src: acq.Source, cursor: dict[str, Any], ctx: acq.FetchContext
                          ) -> Iterator[acq.Item]:
    cfg = src.config
    channel = str(cfg.get("channel_id") or "")
    if not channel.startswith("UC"):
        raise ValueError(f"youtube_channel needs a UC... channel_id, got {channel!r}")
    seen = acq._seen(cursor)
    key = youtube_key(src, ctx)
    if not key:                                    # keyless: the public feed's latest uploads
        r = ctx.fetch(YT_FEED + channel)
        if not r.ok:
            return
        for m in _YT_ENTRY.finditer(r.text):
            b = m.group(0)
            vid = acq._feed_field(b, "yt:videoId")
            if not vid or vid in seen:
                continue
            seen.add(vid)
            yield _yt_item(vid, acq._feed_field(b, "title"),
                           acq._feed_field(b, "media:description"),
                           acq._feed_field(b, "published"), cursor, channel, "rss")
        return
    hdr = {"Accept": "application/json", "X-Goog-Api-Key": key}
    uploads = "UU" + channel[2:]

    def walk(token: str, pages: int, backfill: bool) -> Iterator[acq.Item]:
        for _ in range(pages):
            if ctx.expired():
                return
            r = ctx.fetch(f"{YT_API}/playlistItems?part=snippet&maxResults=50"
                          f"&playlistId={uploads}" + (f"&pageToken={token}" if token else ""),
                          hdr)
            if not r.ok:
                return
            try:
                doc = json.loads(r.text)
            except ValueError:
                return
            for it in doc.get("items") or []:
                sn = it.get("snippet") or {}
                vid = str((sn.get("resourceId") or {}).get("videoId") or "")
                if not vid or vid in seen:
                    continue
                seen.add(vid)
                yield _yt_item(vid, str(sn.get("title") or ""), str(sn.get("description") or ""),
                               str(sn.get("publishedAt") or "") or None, cursor, channel, "api")
            token = str(doc.get("nextPageToken") or "")
            if backfill:
                cursor["page_token"] = token
                yield acq.Item(uri="", body="", cursor_update={"page_token": token,
                                                               "backfill_done": not token})
            if not token:
                return

    # page one every run (new uploads), then the backfill walk from where the last run stopped,
    # until the oldest upload has been read
    yield from walk("", 1, False)
    if not cursor.get("backfill_done"):
        yield from walk(str(cursor.get("page_token") or ""),
                        max(1, acq._as_int(cfg.get("pages_per_run"), 4)), True)


acq.FETCHERS.setdefault("git_mirror", fetch_git_mirror)
acq.FETCHERS.setdefault("youtube_channel", fetch_youtube_channel)
acq.FETCHERS.setdefault("sitemap", fetch_sitemap)

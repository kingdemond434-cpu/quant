"""Two fetchers the civilizations need that the #133 spine did not have, registered into
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
"""
from __future__ import annotations

import fnmatch
import os
import re
import subprocess
import threading
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from libs.mining import acquirer as acq

MIRRORS = Path("desks/mt5/data/civilizations/git_mirrors")
GIT_TIMEOUT_S = 600
MAX_FILE_BYTES = 400_000


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
    excl = [str(g) for g in (cfg.get("exclude") or [])]
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
        rc, body = _git(["show", f"{head}:{path}"], d, _remaining(ctx))
        if rc != 0:
            continue                                   # deleted in the delta
        if len(body) > MAX_FILE_BYTES:
            body = body[:MAX_FILE_BYTES]
        yield acq.Item(uri=f"{web}/blob/{head}/{path}", title=path, body=body,
                       cursor_update={}, meta={"item_kind": "file", "path": path, "sha": head,
                                               "scan": kind, "repo": web})
    if cfg.get("commits") and last and backfill_done:
        rc, log = _git(["log", "--format=%H%x1f%aI%x1f%s%x1f%b%x1e", "--name-only",
                        f"{last}..{head}"], d, 120)
        if rc == 0:
            for block in log.split("\x1e"):
                parts = block.strip().split("\x1f")
                if len(parts) < 4:
                    continue
                sha, when, subj, rest = parts[0], parts[1], parts[2], parts[3]
                yield acq.Item(uri=f"{web}/commit/{sha}", title=subj, body=f"{subj}\n{rest}",
                               publication_time=when, cursor_update={},
                               meta={"item_kind": "commit", "sha": sha, "repo": web})
    yield acq.Item(uri="", body="", cursor_update=upd_base)


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


acq.FETCHERS.setdefault("git_mirror", fetch_git_mirror)
acq.FETCHERS.setdefault("sitemap", fetch_sitemap)

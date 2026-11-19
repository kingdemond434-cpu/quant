"""THE BOX INBOX: how a cloud thread's work reaches the box forge with no network route and no tap.

WHY (principal 2026-11-19 20:04Z: "don't ever ask me for approvals for anything"; decision journal
D-20261119-BOXFERRY). Cloud threads cannot reach the box (their egress allows host names only, and
widening it needs a platform approval card). So nothing in the cloud connects to the box at all.
A thread writes a PACKET -- a git bundle plus a small manifest -- and the box's Remote Control
session, already approved for this box folder, copies it into the inbox folder. The release loop
imports each packet at the start of every pass, exactly as if the thread had pushed it:

  * the branch is pushed to the forge AS THE `claude` ACCOUNT, so the repository hook
    (ops/box_git/protect.py) applies unchanged: only `claude/*` work branches other than LIVE,
    fast-forward only, never a delete. A packet cannot move LIVE, production, master or a tag.
  * the bundle must verify against the forge repository and must carry the manifest's branch at
    the manifest's exact head sha; anything else is refused, never guessed.
  * a pull request into LIVE is opened for the branch if none is open, and the manifest's
    comments (an Auditor's `AUDIT CLEAR <sha>` among them) are posted as `claude`, once each:
    the same author, association and trust they had on GitHub, where every Claude session
    posted through the same app. The merge rules stay in the gate.
  * every packet is KEPT (done/ or refused/ with the reason): packets are evidence.

Manifest (`<id>.json`, next to `<id>.bundle`):
    {"branch": "claude/x", "head": "<40 hex>", "title": "...", "body": "...",
     "comments": ["AUDIT CLEAR <40 hex> merge"]}
"""
from __future__ import annotations

import json
import re
import shutil
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

LIVE = "claude/llm-auto-upgrade-verify-gcjac3"
REPO = "quant/quant"
SHA = re.compile(r"[0-9a-f]{40}")
BRANCH = re.compile(r"claude/[A-Za-z0-9._/-]{1,200}")
MAX_COMMENTS = 20
MAX_COMMENT = 20000
MAX_BUNDLE_BYTES = 200 * 1024 * 1024


@dataclass(frozen=True)
class Manifest:
    branch: str
    head: str
    title: str
    body: str
    comments: tuple[str, ...]


def parse_manifest(doc: Any) -> tuple[Manifest | None, str]:
    """A manifest, or None and why. Pure."""
    if not isinstance(doc, Mapping):
        return None, "manifest is not a JSON object"
    branch, head = doc.get("branch"), doc.get("head")
    if not isinstance(branch, str) or not BRANCH.fullmatch(branch) or ".." in branch:
        return None, f"branch {branch!r} is not a claude/* work branch"
    if branch == LIVE:
        return None, "a packet never moves LIVE: only the box merge gate does"
    if not isinstance(head, str) or not SHA.fullmatch(head):
        return None, "head must be a 40-hex sha"
    title = doc.get("title") or branch
    body = doc.get("body") or ""
    comments = doc.get("comments") or []
    if not isinstance(title, str) or not isinstance(body, str):
        return None, "title and body must be text"
    if not isinstance(comments, list) or len(comments) > MAX_COMMENTS or not all(
            isinstance(c, str) and c.strip() and len(c) <= MAX_COMMENT for c in comments):
        return None, f"comments must be up to {MAX_COMMENTS} non-empty texts"
    return Manifest(branch, head, title[:250], body[:60000], tuple(comments)), "ok"


def bundle_heads(listing: str) -> dict[str, str]:
    """`git bundle list-heads` output -> {ref: sha}. Pure."""
    out: dict[str, str] = {}
    for line in listing.splitlines():
        parts = line.split()
        if len(parts) == 2 and SHA.fullmatch(parts[0]):
            out[parts[1]] = parts[0]
    return out


def packets(inbox: Path) -> list[tuple[Path, Path]]:
    """(bundle, manifest) pairs waiting in the inbox, oldest name first."""
    if not inbox.is_dir():
        return []
    return [(b, b.with_suffix(".json")) for b in sorted(inbox.glob("*.bundle"))
            if b.with_suffix(".json").is_file()]


def _file_away(bundle: Path, manifest: Path, where: Path, why: str) -> None:
    where.mkdir(parents=True, exist_ok=True)
    for f in (bundle, manifest):
        dest = where / f.name
        n = 1
        while dest.exists():
            dest = where / f"{f.stem}.{n}{f.suffix}"
            n += 1
        shutil.move(str(f), str(dest))
    (where / f"{bundle.stem}.why.txt").write_text(why + "\n", encoding="utf-8")


Git = Callable[..., tuple[int, str]]   # git(*args, push_as=None) -> (rc, output)
Api = Callable[[str, str, Any], Any]   # api(method, path, body) as the `claude` account


def import_one(bundle: Path, manifest_path: Path, *, git: Git, api: Api) -> tuple[bool, str]:
    try:
        size = bundle.stat().st_size
        doc = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return False, f"unreadable packet: {type(exc).__name__}"
    if size > MAX_BUNDLE_BYTES:
        return False, f"bundle is {size} bytes, over the {MAX_BUNDLE_BYTES} cap"
    m, why = parse_manifest(doc)
    if m is None:
        return False, why
    rc, out = git("bundle", "verify", str(bundle))
    if rc != 0:
        return False, f"bundle does not verify against the forge repository: {out[-300:]}"
    rc, out = git("bundle", "list-heads", str(bundle))
    if rc != 0:
        return False, f"bundle heads unreadable: {out[-300:]}"
    heads = bundle_heads(out)
    if heads.get(f"refs/heads/{m.branch}") != m.head:
        return False, f"bundle does not carry refs/heads/{m.branch} at {m.head[:12]}"
    rc, out = git("fetch", "-q", str(bundle), f"refs/heads/{m.branch}")
    if rc != 0:
        return False, f"fetch from the bundle failed: {out[-300:]}"
    rc, out = git("push", m.head, f"refs/heads/{m.branch}", push_as="claude")
    if rc != 0:
        return False, f"the forge refused the push (repository hook or protection): {out[-400:]}"
    prs = api("GET", f"/repos/{REPO}/pulls?state=open&limit=50", None) or []
    pr = next((p for p in prs if (p.get("head") or {}).get("ref") == m.branch
               and (p.get("base") or {}).get("ref") == LIVE), None)
    if pr is None:
        pr = api("POST", f"/repos/{REPO}/pulls",
                 {"head": m.branch, "base": LIVE, "title": m.title, "body": m.body})
    n = int((pr or {}).get("number") or 0)
    if not n:
        return False, "pushed, but the forge returned no pull request number"
    have = {str(c.get("body") or "").strip()
            for c in api("GET", f"/repos/{REPO}/issues/{n}/comments?limit=50", None) or []}
    posted = 0
    for c in m.comments:
        if c.strip() not in have:
            api("POST", f"/repos/{REPO}/issues/{n}/comments", {"body": c})
            posted += 1
    return True, f"{m.branch} at {m.head[:12]} -> PR #{n}, {posted} comment(s) posted"


def drain(inbox: Path, *, git: Git, api: Api) -> list[str]:
    """Import every waiting packet; each lands in done/ or refused/ with its reason."""
    out = []
    for bundle, manifest in packets(inbox):
        try:
            ok, why = import_one(bundle, manifest, git=git, api=api)
        except Exception as exc:  # a forge error refuses this packet; it is kept, never lost
            ok, why = False, f"ERROR {type(exc).__name__}: {str(exc)[:300]}"
        _file_away(bundle, manifest, inbox / ("done" if ok else "refused"), why)
        out.append(f"{'IMPORTED' if ok else 'REFUSED'} {bundle.name}: {why}")
    return out

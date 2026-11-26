"""Box state onto claude/box-state (Audit route C, 2026-11-26): the forge loop's `state` stage.

MT5-ShadowSync (SYSTEM) builds a fenced, one-parent state commit on the forge LIVE tip and drops
it as a bundle in the state outbox (SYSTEM writes; the loop's quantgate account may modify).
This stage, each pass:
  1. verifies the bundle against the forge repository and reads refs/publish/pending from it;
  2. judges that commit with the byte-pinned fence (ops/box_git/state_fence.py): one parent equal
     to the LIVE tip right now, added/modified regular state files only;
  3. publishes the same tree as a fast-forward of claude/box-state, pushed as the `claude` thread
     account (no new credential). LIVE is never touched: the gate's CLEAR plus box CI stay the
     second fence for anything that could reach LIVE.
A refused bundle is filed under refused/ with its reasons and kept. A published one replaces
done/last.bundle (its content now lives in the branch's history). STATE_PUBLISH.json records
the last attempt and the last success, for the delivery guard's STATE_STALL page.
"""
from __future__ import annotations

import json
import os
import shutil
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ops.box_git import state_fence

BRANCH = "claude/box-state"
PENDING_REF = "refs/publish/pending"
BUNDLE = "pending.bundle"
STATUS = "STATE_PUBLISH.json"
Git = Callable[[Sequence[str]], tuple[int, str]]
Push = Callable[[str, str], tuple[int, str]]          # push(sha, ref) as `claude`
Remote = Callable[[str], str | None]                  # tip of a ref on the forge, or None


def _file(bundle: Path, where: Path, why: str, stamp: str) -> None:
    where.mkdir(parents=True, exist_ok=True)
    if where.name == "done":
        os.replace(bundle, where / "last.bundle")
        return
    shutil.move(str(bundle), str(where / f"{stamp}.bundle"))
    (where / f"{stamp}.why.txt").write_text(why + "\n", encoding="utf-8")


def _status(path: Path, row: dict[str, Any]) -> None:
    try:
        prev = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        prev = {}
    doc = {"last_attempt": row,
           "last_ok": row if row.get("ok") else (prev.get("last_ok") if isinstance(prev, dict)
                                                  else None)}
    tmp = path.with_name(path.name + ".part")
    tmp.write_text(json.dumps(doc, indent=1), encoding="utf-8")
    os.replace(tmp, path)


def publish(outbox: Path, status: Path, *, git: Git, push: Push, remote_tip: Remote,
            live: str, now: datetime | None = None) -> str:
    t = now or datetime.now(UTC)
    stamp = t.strftime("%Y%m%dT%H%M%SZ")
    bundle = outbox / BUNDLE
    if not bundle.is_file():
        return "no box state pending"

    def refuse(why: str) -> str:
        try:
            _file(bundle, outbox / "refused", why, stamp)
        except OSError as exc:
            why += f" (left in place: {type(exc).__name__})"
        _status(status, {"at": t.isoformat(), "ok": False, "why": why[:400]})
        return f"box state REFUSED: {why}"

    rc, out = git(["bundle", "verify", str(bundle)])
    if rc != 0:
        return refuse(f"bundle does not verify: {out[-200:]}")
    rc, out = git(["bundle", "list-heads", str(bundle)])
    heads = {r: s for s, _, r in (line.partition(" ") for line in out.splitlines())}
    commit = heads.get(PENDING_REF, "")
    if rc != 0 or len(commit) != 40:
        return refuse(f"bundle carries no {PENDING_REF}")
    rc, out = git(["fetch", "-q", str(bundle), PENDING_REF])
    if rc != 0:
        return refuse(f"fetch from the bundle failed: {out[-200:]}")
    rc, tip = git(["rev-parse", f"refs/heads/{live}"])
    if rc != 0 or len(tip.strip()) != 40:
        return refuse("the LIVE tip is unreadable")
    bad = state_fence.refusals(git, commit, tip.strip())
    if bad:
        return refuse("; ".join(bad[:10]) + (f" (+{len(bad) - 10} more)" if len(bad) > 10
                                             else ""))
    prev = remote_tip(f"refs/heads/{BRANCH}")
    head = commit
    if prev:
        rc, same = git(["rev-parse", f"{prev}^{{tree}}", f"{commit}^{{tree}}"])
        trees = same.split()
        if rc == 0 and len(trees) == 2 and trees[0] == trees[1]:
            _file(bundle, outbox / "done", "", stamp)
            _status(status, {"at": t.isoformat(), "ok": True, "commit": commit,
                             "published": prev, "why": "already published"})
            return f"box state {commit[:12]} already on {BRANCH}"
        # The box's own message, so readers (scripts/check_box_state_freshness.py) still know a
        # box write by its subject; the trailer names the fenced commit and the LIVE tip.
        rc, msg = git(["log", "-1", "--format=%B", commit])
        subject = msg.strip() if rc == 0 and msg.strip() else f"box state {commit}"
        rc, made = git(["commit-tree", f"{commit}^{{tree}}", "-p", prev, "-m", subject, "-m",
                        f"Box-State-Commit: {commit}\nFenced-On-Live: {tip.strip()}"])
        if rc != 0 or len(made.strip()) != 40:  # transient (objects not here yet): kept
            _status(status, {"at": t.isoformat(), "ok": False, "commit": commit,
                             "why": f"fast-forward commit not built: {made[-200:]}"})
            return "box state kept for the next pass: fast-forward commit not built"
        head = made.strip()
    rc, out = push(head, f"refs/heads/{BRANCH}")
    if rc != 0:  # the bundle stays for the next pass; the door refuses anything but a ff
        _status(status, {"at": t.isoformat(), "ok": False, "commit": commit,
                         "why": f"push refused: {out[-300:]}"})
        return f"box state push refused (kept for the next pass): {out[-200:]}"
    _file(bundle, outbox / "done", "", stamp)
    _status(status, {"at": t.isoformat(), "ok": True, "commit": commit, "published": head})
    return f"box state {commit[:12]} published to {BRANCH} as {head[:12]}"

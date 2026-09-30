"""THE BOX'S STATE PUBLICATION: what it carries, whether a push is only that, and whether it flows.

WHY THIS EXISTS (measured 2026-09-30 from git alone -- this container cannot reach the box).
The last "mt5 shadow state sync" commit on any branch is 2026-09-12 13:04 +0200. Every box state
file committed since carries times that stop on 2026-09-16 (shadow_health 16:37Z, stall_watch
16:30Z), and RELEASE.json on the live branch dates from 2026-09-15. Readers off the box -- the CRO
cycle, the audits, the dashboard -- have been measuring a frozen copy for two weeks and calling
the desk silent.

The chain of causes, in the order the evidence supports them:

1. THE PRE-PUSH GATE JUDGES STATE AS IF IT WERE CODE. `ops/migrate_to_new_box.ps1:82` (added
   2026-09-11, the new box) runs `git config core.hooksPath ops/githooks`, so from 2026-09-11 every
   push FROM THE BOX -- including `sync_shadow_to_git.ps1`'s plain `git push` of a JSON-only
   commit -- runs `ops/githooks/pre-push`: ruff, compileall, pytest collection and mypy over the
   whole tree, then all ~39 law fences. The box session of 2026-09-12 recorded exactly this
   ("Type-check ... unblocks pre-push", eaa869919; "All four law fences green", 6c5f05589 at
   12:08 +0200) and the last sync push landed 56 minutes later. From then on any red fence
   anywhere in the repository refused the box's state -- and the push ran three times per pass
   inside a ten-minute task limit, so a slow gate was killed before the script could log it.
   A state commit changes no code; there is nothing for those gates to judge in it.
2. The publisher exited before staging whenever origin was ahead (ff281c49b, 2026-09-30), which on
   a branch that moves every few minutes is nearly always. PR #99 addresses that.

WHAT TO DO ABOUT CAUSE 1 IS THE PRINCIPAL'S CALL, NOT A SESSION'S. Scoping the push gate is a
change to a safety check and is left to a human decision; this module does not touch the hook.
What it does is make the stall impossible to miss:

* `published_paths()` -- the exact set the publisher carries, read from the script itself (one
  list, never restated here);
* `measure_flow()` -- is the box's state actually reaching origin? Written to
  `desks/mt5/reports/BOX_STATE_FLOW.json` every hour by the `publish_state` leg and read by
  `stall_watch.ps1` every ten minutes, with a `STATE_FLOW_STALLED` event when it is not, so the
  next stall is a named alarm on the box within hours instead of a two-week silence found by an
  audit.
"""
from __future__ import annotations

import contextlib
import json
import re
import subprocess
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SYNC_REL = "desks/mt5/scripts/sync_shadow_to_git.ps1"
FLOW_REL = "desks/mt5/reports/BOX_STATE_FLOW.json"
SYNC_LOG_REL = "desks/mt5/logs/sync_shadow_to_git.log"

#: The arrays in the sync script whose quoted entries are published paths. `$reportPaths` is the
#: second list PR #99 introduces; absent today, it simply contributes nothing.
_LISTS = ("$relPaths = @(", "$reportPaths = @(")

#: WHEN SILENCE BECOMES A STALL. The publisher runs every fifteen minutes (MT5-ShadowSync) and
#: again at the end of every hourly cycle (`publish_state`), and PR #99 makes it publish even when
#: the box is behind. Three hours is twelve missed sync slots and three missed hourly legs --
#: long past any single slow pass or adoption window (MT5-AdoptRelease holds the git-writer lock
#: at most PT2H), and short enough that a stall is named the same morning rather than found by an
#: audit two weeks later.
STALL_H = 3.0


def _git(root: Path, *args: str, timeout: float = 60.0) -> tuple[int, str]:
    """Run git; (rc, stdout). UTF-8 with replacement: cp1252 decoding killed three hooks (L0304)."""
    try:
        r = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=timeout, check=False)
    except (OSError, subprocess.SubprocessError) as exc:
        return 127, f"{type(exc).__name__}: {exc}"
    return r.returncode, r.stdout


def parse_published(script_text: str) -> list[str]:
    """Every repo-relative path quoted inside the publisher's path arrays, in order."""
    out: list[str] = []
    for marker in _LISTS:
        if marker not in script_text:
            continue
        block = script_text.split(marker, 1)[1].split("\n)", 1)[0]
        for line in block.splitlines():
            code = line.split("#", 1)[0]
            for p in re.findall(r'"([^"]+)"', code):
                if "/" in p and p not in out:
                    out.append(p)
    return out


def published_paths(root: Path = ROOT, *, rev: str | None = None) -> list[str]:
    """The publisher's paths, from the working copy or (with `rev`) from that commit's copy."""
    if rev:
        rc, text = _git(root, "show", f"{rev}:{SYNC_REL}")
        return parse_published(text) if rc == 0 else []
    try:
        return parse_published((root / SYNC_REL).read_text("utf-8", errors="ignore"))
    except OSError:
        return []


# ------------------------------------------------------------------------------ the flow meter
def _branch_ref(root: Path) -> tuple[str | None, str | None]:
    rc, branch = _git(root, "rev-parse", "--abbrev-ref", "HEAD")
    branch = branch.strip()
    if rc != 0 or not branch or branch == "HEAD":
        return None, None
    for ref in (f"refs/remotes/origin/{branch}", "FETCH_HEAD"):
        if _git(root, "rev-parse", "--verify", "-q", ref)[0] == 0:
            return branch, ref
    return branch, None


def _sync_log_tail(root: Path, limit: int = 400) -> dict[str, Any]:
    """The publisher's last success and last refusal, quoted from its own log."""
    p = root / SYNC_LOG_REL
    try:
        with p.open("rb") as fh:
            fh.seek(0, 2)
            size = fh.tell()
            fh.seek(max(0, size - 256 * 1024))
            lines = fh.read().decode("utf-8", "replace").splitlines()[-limit:]
    except OSError:
        return {"readable": False}
    ok_re = re.compile(r"shadow state synced|published box state|delivered \d+")
    bad_re = re.compile(r"ABORT|push rejected|DEFER|SKIP|FAILED|refused", re.I)
    last_ok = next((ln for ln in reversed(lines) if ok_re.search(ln)), None)
    last_bad = next((ln for ln in reversed(lines) if bad_re.search(ln)), None)
    return {"readable": True, "last_success_line": last_ok, "last_refusal_line": last_bad,
            "last_line": lines[-1] if lines else None}


def measure_flow(root: Path = ROOT, *, now: datetime | None = None,
                 stall_h: float = STALL_H) -> dict[str, Any]:
    """Is the box's state reaching origin? FLOWING / STALLED / SOURCE_STALE / UNMEASURED."""
    now = now or datetime.now(UTC)
    doc: dict[str, Any] = {"schema": "box_state_flow/1", "measured_at": now.isoformat(
        timespec="seconds"), "stall_h": stall_h, "flow_rel": FLOW_REL}
    paths = published_paths(root)
    doc["published_paths"] = len(paths)
    branch, ref = _branch_ref(root)
    doc.update(branch=branch, origin_ref=ref)
    if not paths or not branch or not ref:
        doc["verdict"] = "UNMEASURED"
        doc["why"] = ("no publisher allowlist" if not paths else "no branch checked out"
                      if not branch else "no origin ref for this branch in this clone")
        return doc
    rc, who = _git(root, "config", "user.name")
    who = who.strip()
    doc["publisher_identity"] = who or None
    args = ["log", "-1", "--format=%ct %h", ref]
    if who:
        args[3:3] = ["-F", f"--author={who}"]
    rc, out = _git(root, *args, "--", *paths)
    published_at = None
    if rc == 0 and out.strip():
        ct, sha = out.split()[:2]
        published_at = datetime.fromtimestamp(int(ct), UTC)
        doc["last_published_commit"] = sha
    doc["last_published_at"] = published_at.isoformat(timespec="seconds") if published_at \
        else None
    newest = None
    for rel in paths:
        try:
            m = datetime.fromtimestamp((root / rel).stat().st_mtime, UTC)
        except OSError:
            continue
        newest = m if newest is None or m > newest else newest
    doc["newest_local_state_at"] = newest.isoformat(timespec="seconds") if newest else None
    rc, ahead = _git(root, "rev-list", "--count", f"{ref}..HEAD")
    doc["local_commits_not_on_origin"] = int(ahead.strip()) if rc == 0 and \
        ahead.strip().isdigit() else None
    doc["hooks_path"] = _git(root, "config", "core.hooksPath")[1].strip() or None
    doc["sync_log"] = _sync_log_tail(root)
    pub_age = (now - published_at).total_seconds() / 3600 if published_at else None
    src_age = (now - newest).total_seconds() / 3600 if newest else None
    doc["published_age_h"] = round(pub_age, 2) if pub_age is not None else None
    doc["local_state_age_h"] = round(src_age, 2) if src_age is not None else None
    if src_age is None:
        doc["verdict"], doc["why"] = "UNMEASURED", "none of the published files exist here"
    elif src_age > stall_h and (pub_age is None or pub_age > stall_h):
        doc["verdict"] = "SOURCE_STALE"
        doc["why"] = (f"the producers themselves are quiet: newest local state is "
                      f"{src_age:.1f}h old")
    elif pub_age is None or pub_age > stall_h:
        doc["verdict"] = "STALLED"
        doc["why"] = (f"local state is {src_age:.1f}h old but origin's newest box-published "
                      f"state is {'never' if pub_age is None else f'{pub_age:.1f}h old'} -- "
                      "delivery is broken, the desk is not idle")
    else:
        doc["verdict"], doc["why"] = "FLOWING", f"origin carries box state {pub_age:.1f}h old"
    return doc


# ------------------------------------------------------------------------ the out-of-band page
#: THE VERDICT CANNOT RIDE THE WIRE IT REPORTS ON (2026-09-30). BOX_STATE_FLOW.json and the
#: STATE_FLOW_STALLED event reach anyone off the box only through the very push that is stalled,
#: so a STALLED verdict would sit on the box's disk until the stall ended by itself. These two
#: verdicts are therefore also paged through the desk's existing sender,
#: `libs.ops.alert_channels.send_all` (the armed channels in data/secrets/alert_channels.json,
#: every attempt in data/alert_delivery.jsonl) -- a different route that needs no git.
ALERT_VERDICTS = ("STALLED", "SOURCE_STALE")
#: Box-local dedup state (desks/mt5/logs/ is gitignored): one page per verdict change, and a
#: reminder every REPAGE_H hours while the verdict stands.
ALERT_STATE_REL = "desks/mt5/logs/state_flow_alert.json"
REPAGE_H = 6.0

Sender = Callable[[str, str], dict[str, Any]]


def _default_sender(root: Path) -> Sender:
    def send(title: str, body: str) -> dict[str, Any]:
        from libs.ops import alert_channels
        # The sender reads its own config where it always has; anchored on the repo root so the
        # leg's working directory cannot make an armed box look unarmed. Nothing here reads or
        # records a channel's credentials.
        return alert_channels.send_all(
            title, body, config=root / "data/secrets/alert_channels.json",
            ledger=root / "data/alert_delivery.jsonl")
    return send


def page_flow(root: Path, doc: dict[str, Any], *, now: datetime | None = None,
              sender: Sender | None = None, repage_h: float = REPAGE_H) -> dict[str, Any]:
    """Page STALLED / SOURCE_STALE off the box, deduplicated. Returns what it did. Never raises.

    Sends on a change INTO an alert verdict, again every `repage_h` hours while it stands, and
    once on recovery to FLOWING. UNMEASURED neither pages nor clears: absence is not recovery.
    """
    now = now or datetime.now(UTC)
    verdict = str(doc.get("verdict") or "UNMEASURED")
    path = root / ALERT_STATE_REL
    try:
        prev = json.loads(path.read_text("utf-8"))
        prev = prev if isinstance(prev, dict) else {}
    except (OSError, ValueError):
        prev = {}
    prev_verdict = prev.get("verdict")
    last = None
    with contextlib.suppress(TypeError, ValueError):
        last = datetime.fromisoformat(str(prev.get("paged_at")))
    if verdict in ALERT_VERDICTS:
        if prev_verdict != verdict:
            reason = "verdict changed"
        elif last is None or (now - last).total_seconds() / 3600 >= repage_h:
            reason = f"still {verdict} after {repage_h:g}h"
        else:
            return {"sent": False, "reason": f"deduplicated: {verdict} paged at {last.isoformat()}"}
        title = f"BOX STATE {verdict}"
    elif verdict == "FLOWING" and prev_verdict in ALERT_VERDICTS:
        reason, title = f"recovered from {prev_verdict}", "BOX STATE FLOWING again"
    else:
        return {"sent": False, "reason": f"{verdict}: nothing to page"}
    log = doc.get("sync_log") if isinstance(doc.get("sync_log"), dict) else {}
    body = "\n".join(str(x) for x in (
        doc.get("why") or verdict,
        f"origin box-state age: {doc.get('published_age_h')}h; local state age: "
        f"{doc.get('local_state_age_h')}h; unpushed commits: "
        f"{doc.get('local_commits_not_on_origin')}",
        f"sync log last refusal: {log.get('last_refusal_line')}" if log else "",
        f"measured {doc.get('measured_at')} ({FLOW_REL})") if x)
    try:
        res = (sender or _default_sender(root))(title, body)
    except Exception as exc:  # the pager must never take down the leg
        res = {"armed": None, "delivered": 0, "error": f"{type(exc).__name__}: {exc}"}
    out = {"sent": True, "reason": reason, "title": title,
           "armed": res.get("armed"), "delivered": res.get("delivered")}
    if res.get("error"):
        out["error"] = res["error"]
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"verdict": verdict, "paged_at": now.isoformat(
            timespec="seconds"), **{k: out.get(k) for k in ("reason", "armed", "delivered")}},
            indent=2), "utf-8")
    except OSError as exc:
        out["state_write_error"] = f"{type(exc).__name__}: {exc}"
    return out


def publish_flow(root: Path = ROOT, *, doc: dict[str, Any] | None = None,
                 events_path: Path | None = None,
                 sender: Sender | None = None) -> dict[str, Any]:
    """Measure, page it off the box if it is STALLED/SOURCE_STALE (deduplicated), write
    BOX_STATE_FLOW.json, and emit STATE_FLOW_STALLED when it is. Never raises."""
    try:
        doc = doc or measure_flow(root)
    except Exception as exc:  # a meter must not take down the leg it rides
        doc = {"schema": "box_state_flow/1", "verdict": "UNMEASURED",
               "why": f"{type(exc).__name__}: {exc}",
               "measured_at": datetime.now(UTC).isoformat(timespec="seconds")}
    try:
        doc["page"] = page_flow(root, doc, sender=sender)
    except Exception as exc:
        doc["page"] = {"sent": False, "error": f"{type(exc).__name__}: {exc}"}
    out = root / FLOW_REL
    try:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(doc, indent=2, default=str), "utf-8")
    except OSError as exc:
        doc["write_error"] = f"{type(exc).__name__}: {exc}"
    if doc.get("verdict") == "STALLED":
        print(f"STATE FLOW STALLED: {doc.get('why')}", flush=True)
        try:
            from libs.ops import events
            events.emit("STATE_FLOW_STALLED", path=events_path, producer="publish_state",
                        priority=2, why=doc.get("why"),
                        published_age_h=doc.get("published_age_h"),
                        local_commits_not_on_origin=doc.get("local_commits_not_on_origin"))
        except Exception as exc:
            print(f"STATE_FLOW_STALLED event not written: {exc}", flush=True)
    return doc

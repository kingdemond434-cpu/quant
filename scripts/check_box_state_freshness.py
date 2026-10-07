"""FENCE: the box's state on the live branch may not be more than SIX HOURS old.

THE DEFECT IT EXISTS FOR (measured 2026-09-30 from git alone). The last "mt5 shadow state sync"
commit on any branch is 2026-09-12 13:04 +0200; every box-written state file committed since
carries times that stop on 2026-09-16 (shadow_health.updated_at 16:37Z, stall_watch 16:30Z); and
RELEASE.json on the live branch dates from 2026-09-15. For two weeks every reader off the box --
the CRO cycle, the audits, the dashboard, the six-event trace -- measured a frozen copy, and no
fence anywhere was red about it. The box went on computing; only delivery had stopped.

WHAT IT MEASURES, AT A GIT REF (default: the live branch's remote-tracking ref, else HEAD):

  1. the newest commit on that ref, by a box identity (author matching --box-author, default
     "Contabo"), that touched any path the box publisher carries (`$relPaths` in
     sync_shadow_to_git.ps1, parsed by libs.ops.state_publication -- one list, never restated);
  2. the newest time stamp written INSIDE those files as they sit at that ref (`updated_at`,
     `generated_at`, `measured_at`, `checked_at`, `generated_utc`, `last_cycle`) -- because a
     re-root or a merge can re-commit old content under a new date, and a commit date alone
     would then read fresh while the evidence is a fortnight old.

  The STAMPS decide when any file carries one; the commit date is the fallback only. Measured on
  this branch today the two disagree by eight days: the orphan re-root bcbec41f0 (Contabo MT5
  Desk, 2026-09-24) re-committed the box's files, while the newest stamp inside them is
  2026-09-16T16:37:33Z. A commit-date fence would have read that re-root as a delivery.

THE THRESHOLD IS 6 HOURS, and it is stated rather than tuned. The publisher runs every fifteen
minutes (MT5-ShadowSync) and again at the end of every hourly cycle (publish_state); the box-side
meter (BOX_STATE_FLOW.json, libs/ops/state_publication.STALL_H) names a stall at 3h. Six hours is
twenty-four missed sync slots and six missed hourly publications -- well past a slow adoption
(MT5-AdoptRelease holds the git-writer lock at most PT2H) and still the same working session.

ABSENCE IS NOT FRESHNESS (L1.28a). No ref, no allowlist, no box commit and no parseable stamp is
UNMEASURED and exits 1: a fence that passed on "found nothing" is the silence it replaces.

A STATE FENCE, NOT A COMMIT GATE. It rides `_STATE_FENCES` in run_law_gate.py (the box's
MT5-LawGate rotation) and never `--laws-only` pre-push/CI: a red here must not wedge the very push
that would heal it. The rotation spreads the battery over a 48h window, so it ALSO runs as the
core-plan hourly leg `box_state_freshness`, just before `publish_state` -- every hour, and the
report it writes rides that hour's publication.

THE REPORT IS PUBLISHED (2026-09-30). desks/mt5/reports/BOX_STATE_FRESHNESS.json is allowlisted in
.gitignore, carried by sync_shadow_to_git.ps1's $relPaths and declared NON_CODE, so the CRO cycle
(D17 reads `box_state_age_hours`) sees it off the box. `box_state_age_hours` is ALWAYS a key: null
with `box_state_age_reason` when unmeasured, never absent.

WHAT ELSE IT CARRIES, IN BOTH OUTPUT MODES (--json included): the published BOX_STATE_FLOW.json
meter's verdict and NOT-ARMED line (`box_state_flow`, `alerts_line`), the box's own local meter
when this runs on the box (`box_state_flow_local`), and stall_watch.json's `alerts_armed` /
`alerts_line` (`stall_watch_alerts`) -- the watcher's ten-minute reading of whether any page
reaches anyone, which had no reader before this.

Exit 0 FRESH, 1 STALE or UNMEASURED.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.ops.state_publication import FLOW_REL, published_paths  # noqa: E402

LIVE_BRANCH = "claude/llm-auto-upgrade-verify-gcjac3"
THRESHOLD_H = 6.0
BOX_AUTHOR = "Contabo"
OUT_REL = "desks/mt5/reports/BOX_STATE_FRESHNESS.json"
OUT = ROOT / OUT_REL
#: stall_watch.ps1's own state file (box-local, written every ten minutes by MT5-StallWatch).
STALL_WATCH_REL = "desks/mt5/data/stall_watch.json"
STAMP_KEYS = ("updated_at", "generated_at", "measured_at", "checked_at", "generated_utc",
              "last_cycle")


def _git(root: Path, *args: str) -> tuple[int, str]:
    try:
        r = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=120, check=False)
    except (OSError, subprocess.SubprocessError) as exc:
        return 127, f"{type(exc).__name__}: {exc}"
    return r.returncode, r.stdout


def is_box(name: str, box_author: str = BOX_AUTHOR) -> bool:
    """THE ONE BOX-IDENTITY PREDICATE (audit should-fix, 2026-10-06). It used to be two: the
    commit search used git's `--author` (a case-sensitive substring of "name <email>") and the
    per-file check a case-insensitive substring of %an, so "Not Contabo" passed one and a
    lower-cased name only the other. Now: the author NAME begins with the box identity as a whole
    word, case-insensitive ("Contabo MT5 Desk" yes; "Contabot", "ex-Contabo" no)."""
    return re.match(rf"\s*{re.escape(box_author)}(?![\w-])", name or "", re.I) is not None


#: How far down a merge's parents the writer search goes before calling the file unattributed.
MERGE_DEPTH = 8


def file_writer(root: Path, rev: str, rel: str, box_author: str = BOX_AUTHOR,
                depth: int = 0) -> tuple[str, bool]:
    """(writer name, box-written?) of `rel` as it stands at `rev`.

    A MERGE IS NOT AUTHORSHIP (audit should-fix, 2026-10-06). `git log -1 -- rel` lands on a merge
    whenever the merge is not TREESAME to any parent for that file (a conflict resolution, a JSON
    union), and the merger's name then hid the box's write. When the newest commit touching the
    file is a merge, the content came from its parents: it is box-written when every parent side
    that carries the file was box-written, and named after the first one that was not."""
    rc, out = _git(root, "log", "-1", "--format=%P%x09%an", rev, "--", rel)
    if rc != 0 or not out.strip():
        return "", False
    parents, name = [*out.strip("\n").split("\t"), ""][:2]
    plist = parents.split()
    if len(plist) < 2 or depth >= MERGE_DEPTH:
        return name, is_box(name, box_author)
    sides = []
    for par in plist:
        rc_p, _ = _git(root, "cat-file", "-e", f"{par}:{rel}")
        if rc_p == 0:
            sides.append(file_writer(root, par, rel, box_author, depth + 1))
    if sides and all(ok for _, ok in sides):
        return sides[0][0], True
    bad = next((w for w, ok in sides if not ok), name)
    return bad or name, False


def _parse(v: Any) -> datetime | None:
    if not isinstance(v, str) or not v:
        return None
    try:
        at = datetime.fromisoformat(v.replace("Z", "+00:00"))
    except ValueError:
        return None
    return at if at.tzinfo else at.replace(tzinfo=UTC)


def _read_local(path: Path) -> dict[str, Any] | None:
    try:
        # utf-8-sig: PowerShell 5's Set-Content writes a BOM on the box.
        data = json.loads(path.read_text("utf-8-sig"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _flow_view(data: dict[str, Any]) -> dict[str, Any]:
    raw = data.get("alerts")
    alerts: dict[str, Any] = raw if isinstance(raw, dict) else {}
    return {"verdict": data.get("verdict"), "why": data.get("why"),
            "measured_at": data.get("measured_at"),
            "published_age_h": data.get("published_age_h"),
            "alerts_armed": alerts.get("armed"), "alerts_line": alerts.get("line")}


def stall_watch_alerts(root: Path = ROOT) -> dict[str, Any]:
    """THE READER stall_watch.json's alerts_* keys never had (2026-09-30).

    MT5-StallWatch writes `alerts_armed` / `alerts_line` every ten minutes from the independent
    watcher (libs.ops.state_publication.watch); nothing read them, so NOT-ARMED sat in a box file
    no one opened. Absent file or absent keys is UNMEASURED, never "armed".
    """
    doc = _read_local(root / STALL_WATCH_REL)
    if doc is None:
        return {"status": "UNMEASURED", "why": f"{STALL_WATCH_REL} absent or unreadable here",
                "alerts_armed": None, "alerts_line": None}
    if "alerts_armed" not in doc and "alerts_line" not in doc:
        return {"status": "UNMEASURED", "checked_at": doc.get("checked_at"),
                "why": "stall_watch.json predates the alerts_* keys (stall_watch.ps1 not adopted)",
                "alerts_armed": None, "alerts_line": None}
    return {"status": "MEASURED", "checked_at": doc.get("checked_at"),
            "state_flow": doc.get("state_flow"), "state_flow_watch": doc.get("state_flow_watch"),
            "alerts_armed": doc.get("alerts_armed"), "alerts_line": doc.get("alerts_line")}


def resolve_ref(root: Path, ref: str | None) -> str | None:
    for cand in ([ref] if ref else [f"refs/remotes/origin/{LIVE_BRANCH}", "HEAD"]):
        if _git(root, "rev-parse", "--verify", "-q", f"{cand}^{{commit}}")[0] == 0:
            return cand
    return None


def measure(root: Path = ROOT, *, ref: str | None = None, threshold_h: float = THRESHOLD_H,
            box_author: str = BOX_AUTHOR, now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    doc: dict[str, Any] = {"schema": "box_state_freshness/1",
                           "measured_at": now.isoformat(timespec="seconds"),
                           "threshold_h": threshold_h, "box_author": box_author,
                           # ALWAYS PRESENT (CRO D17): null + a reason when unmeasured, never absent.
                           "age_h": None, "box_state_age_hours": None,
                           "box_state_flow": None, "alerts": None}
    local = _read_local(root / FLOW_REL)
    doc["box_state_flow_local"] = _flow_view(local) if local else None
    doc["stall_watch_alerts"] = stall_watch_alerts(root)
    try:
        return _measure(root, doc, ref=ref, threshold_h=threshold_h, box_author=box_author,
                        now=now)
    finally:
        if doc.get("box_state_age_hours") is None:
            doc["box_state_age_reason"] = f"{doc.get('verdict', 'UNMEASURED')}: {doc.get('why')}"
        doc["alerts_line"] = alerts_line(doc)


def _measure(root: Path, doc: dict[str, Any], *, ref: str | None, threshold_h: float,
             box_author: str, now: datetime) -> dict[str, Any]:
    use = resolve_ref(root, ref)
    doc["ref"] = use
    paths = published_paths(root, rev=use) if use else []
    doc["published_paths"] = len(paths)
    if not use or not paths:
        doc.update(verdict="UNMEASURED",
                   why="no git ref to read" if not use else "no publisher allowlist at the ref")
        return doc
    rc_s, shallow = _git(root, "rev-parse", "--is-shallow-repository")
    doc["shallow"] = rc_s == 0 and shallow.strip() == "true"
    # The newest box commit, by the same predicate the per-file check uses (`is_box`).
    rc, out = _git(root, "log", "-n", "20000", "--format=%ct%x09%h%x09%an", use, "--", *paths)
    commit_at = None
    for line in out.splitlines() if rc == 0 else []:
        ct, sha, who = [*line.split("\t"), "", ""][:3]
        if ct.isdigit() and is_box(who, box_author):
            commit_at = datetime.fromtimestamp(int(ct), UTC)
            doc["newest_box_commit"] = {"sha": sha, "author": who,
                                        "at": commit_at.isoformat(timespec="seconds")}
            break
    stamps: dict[str, str] = {}
    not_box_written: dict[str, str] = {}
    newest_stamp = None
    for rel in paths:
        if not rel.endswith(".json"):
            continue
        # ONLY THE BOX'S OWN WRITE COUNTS (2026-10-06). RELEASE.json is on the publisher's list,
        # but since release promotion (#90) CI's "seal release" commit rewrites it with a fresh
        # `generated_utc` every release -- measured on 2d61e69a1, that stamp (11:11Z) read the
        # fence FRESH at 4.3h while the newest box-authored commit on any published path was
        # bcbec41f0 of 2026-09-24. A stamp counts only when the newest commit touching its file
        # at the ref is a box identity's; anyone else's write is listed, never believed.
        writer, boxed = file_writer(root, use, rel, box_author)
        if not boxed:
            if writer:
                not_box_written[rel] = writer
            continue
        rc, text = _git(root, "show", f"{use}:{rel}")
        if rc != 0:
            continue
        try:
            data = json.loads(text)
        except ValueError:
            continue
        if not isinstance(data, dict):
            continue
        if rel == FLOW_REL:
            # NOT-ARMED, carried off the box: the meter records whether any alert channel is
            # armed, and this fence (CRO D17) is where a reader off the box sees it.
            doc["alerts"] = data.get("alerts") if isinstance(data.get("alerts"), dict) else None
            doc["box_state_flow"] = _flow_view(data)
        best = max((t for t in (_parse(data.get(k)) for k in STAMP_KEYS) if t), default=None)
        if best:
            stamps[rel] = best.isoformat(timespec="seconds")
            newest_stamp = best if newest_stamp is None or best > newest_stamp else newest_stamp
    doc["stamps_inside_state"] = stamps
    doc["stamps_ignored_not_box_written"] = not_box_written
    doc["newest_stamp_inside_state"] = newest_stamp.isoformat(timespec="seconds") \
        if newest_stamp else None
    freshest = newest_stamp or commit_at
    doc["basis"] = "stamp_inside_state" if newest_stamp else "box_commit_date"
    if freshest is None and doc["shallow"]:
        # A shallow clone ends at its graft: "no box commit" may only mean the box's commits are
        # below the cut (audit should-fix, 2026-10-06). Name THAT, not an absent box.
        doc.update(verdict="UNMEASURED",
                   why=f"shallow clone: authorship history at {use} is truncated at the graft, so "
                       "the box's commits may lie below it (fetch with --unshallow to measure)")
        return doc
    if freshest is None:
        doc.update(verdict="UNMEASURED",
                   why=f"no commit by a '{box_author}' identity touches the published paths at "
                       f"{use}, and no published file carries a parseable stamp")
        return doc
    age_h = (now - freshest).total_seconds() / 3600
    doc["age_h"] = round(age_h, 2)
    doc["box_state_age_hours"] = doc["age_h"]   # the metric name CRO duty D17 reads
    if age_h > threshold_h:
        doc.update(verdict="STALE",
                   why=(f"the box's newest state on {use} is {age_h:.1f}h old (threshold "
                        f"{threshold_h:.0f}h): every reader off the box is measuring a frozen "
                        "copy. On the box: BOX_STATE_FLOW.json and "
                        "desks\\mt5\\logs\\sync_shadow_to_git.log name why."))
    else:
        doc.update(verdict="FRESH", why=f"box state on {use} is {age_h:.1f}h old")
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--ref", default=None, help="git ref to judge (default: the live branch)")
    ap.add_argument("--threshold-h", type=float, default=THRESHOLD_H)
    ap.add_argument("--box-author", default=BOX_AUTHOR)
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    doc = measure(ROOT, ref=args.ref, threshold_h=args.threshold_h, box_author=args.box_author)
    try:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(doc, indent=2), "utf-8")
    except OSError as exc:
        print(f"box state freshness: artifact not written ({exc})", file=sys.stderr)
    print(json.dumps(doc, indent=2) if args.json else
          f"box state freshness: {doc['verdict']} -- {doc['why']}")
    line = doc.get("alerts_line")
    if line:
        # Loud, never a verdict: arming is a human step, and a fence that failed on it would
        # wedge nothing and heal nothing. The line is what a reader of this fence must not miss.
        # Under --json it is IN the document (`alerts_line`) and repeated on stderr, so stdout
        # stays one parseable document and the line is still seen.
        print(line, file=sys.stderr if args.json else sys.stdout)
    return 0 if doc["verdict"] == "FRESH" else 1


def alerts_line(doc: dict[str, Any]) -> str | None:
    """The loud NOT-ARMED line, or None when armed or when nothing recorded arming.

    The FRESHEST reading that recorded arming decides: the box's own meter on disk, then
    stall_watch.json's ten-minute reading, then the meter as published at the ref (which may be
    the stale copy this fence exists to catch)."""
    sources = (doc.get("box_state_flow_local"), doc.get("stall_watch_alerts"), doc.get("alerts"))
    for src in sources:
        if not isinstance(src, dict):
            continue
        armed = src.get("armed", src.get("alerts_armed"))
        line = src.get("line", src.get("alerts_line"))
        if armed is None and not line:
            continue   # this source recorded nothing about arming; ask the next one
        return str(line) if line else None
    return None

if __name__ == "__main__":
    raise SystemExit(main())

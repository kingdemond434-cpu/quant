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

A STATE FENCE, NOT A COMMIT GATE. It rides `_STATE_FENCES` in run_law_gate.py, so it runs on a
clock in the box's hourly MT5-LawGate rotation and never in `--laws-only` pre-push/CI: a red here
must not wedge the very push that would heal it. Writes desks/mt5/reports/BOX_STATE_FRESHNESS.json.
Exit 0 FRESH, 1 STALE or UNMEASURED.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.ops.state_publication import published_paths  # noqa: E402

LIVE_BRANCH = "claude/llm-auto-upgrade-verify-gcjac3"
THRESHOLD_H = 6.0
BOX_AUTHOR = "Contabo"
OUT = ROOT / "desks" / "mt5" / "reports" / "BOX_STATE_FRESHNESS.json"
STAMP_KEYS = ("updated_at", "generated_at", "measured_at", "checked_at", "generated_utc",
              "last_cycle")


def _git(root: Path, *args: str) -> tuple[int, str]:
    try:
        r = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=120, check=False)
    except (OSError, subprocess.SubprocessError) as exc:
        return 127, f"{type(exc).__name__}: {exc}"
    return r.returncode, r.stdout


def _parse(v: Any) -> datetime | None:
    if not isinstance(v, str) or not v:
        return None
    try:
        at = datetime.fromisoformat(v.replace("Z", "+00:00"))
    except ValueError:
        return None
    return at if at.tzinfo else at.replace(tzinfo=UTC)


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
                           "threshold_h": threshold_h, "box_author": box_author}
    use = resolve_ref(root, ref)
    doc["ref"] = use
    paths = published_paths(root, rev=use) if use else []
    doc["published_paths"] = len(paths)
    if not use or not paths:
        doc.update(verdict="UNMEASURED",
                   why="no git ref to read" if not use else "no publisher allowlist at the ref")
        return doc
    rc, out = _git(root, "log", "-1", "-F", f"--author={box_author}", "--format=%ct %h %an",
                   use, "--", *paths)
    commit_at = None
    if rc == 0 and out.strip():
        ct, sha, *who = out.split()
        commit_at = datetime.fromtimestamp(int(ct), UTC)
        doc["newest_box_commit"] = {"sha": sha, "author": " ".join(who),
                                    "at": commit_at.isoformat(timespec="seconds")}
    stamps: dict[str, str] = {}
    newest_stamp = None
    for rel in paths:
        if not rel.endswith(".json"):
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
        best = max((t for t in (_parse(data.get(k)) for k in STAMP_KEYS) if t), default=None)
        if best:
            stamps[rel] = best.isoformat(timespec="seconds")
            newest_stamp = best if newest_stamp is None or best > newest_stamp else newest_stamp
    doc["stamps_inside_state"] = stamps
    doc["newest_stamp_inside_state"] = newest_stamp.isoformat(timespec="seconds") \
        if newest_stamp else None
    freshest = newest_stamp or commit_at
    doc["basis"] = "stamp_inside_state" if newest_stamp else "box_commit_date"
    if freshest is None:
        doc.update(verdict="UNMEASURED",
                   why=f"no commit by a '{box_author}' identity touches the published paths at "
                       f"{use}, and no published file carries a parseable stamp")
        return doc
    age_h = (now - freshest).total_seconds() / 3600
    doc["age_h"] = round(age_h, 2)
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
    return 0 if doc["verdict"] == "FRESH" else 1


if __name__ == "__main__":
    raise SystemExit(main())

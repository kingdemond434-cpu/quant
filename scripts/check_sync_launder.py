#!/usr/bin/env python3
"""LAUNDER RESIDUE -- the code a one-way sync reverted and nobody ever put back.

THE MECHANISM, measured rather than theorised. `desks/mt5/scripts/sync_to_vps.ps1` runs on the
Dell every hour: it scp's `C:\\Users\\dell\\mt5-research` over `desks/mt5/` on this box and then
runs `git add desks/mt5 && git commit && git push` here over ssh. It is a ONE-WAY push with no
ancestry check, so any file edited on the VPS between two syncs is overwritten by the Dell's older
copy and that copy is committed as a "sync". The desk has two defences and BOTH are list-shaped:

  * `scripts/moneypath_precommit_guard.py` (landed 41602946, 2026-08-26) refuses staged
    `desks/mt5/**/*.py` in ssh context. It works -- measured: no mt5 sync commit has carried a .py
    change since 7cb174af, 02:02 on 2026-08-26. It is a FUTURE-tense guard.
  * `scripts/check_moneypath_fence.py` restores canon by marker, but only for the files in its
    hand-maintained PROTECTED map.

WHAT NEITHER OF THEM DOES, AND WHY THIS EXISTS. Twenty-two sync commits carried .py changes BEFORE
the guard existed. Whatever they reverted is still reverted unless a human happened to notice.
Measured 2026-08-28: `desks/mt5/research/regime_monitor.py` lost 122 of its 149 lines to
45153948 -- the GAP 130 shadow-replay wake, shipped two hours earlier -- and sat dead in HEAD for
two days. It was invisible to the marker fence for one reason only: nobody had added it to the
map. A registry of files that have already been damaged cannot name the file about to be damaged,
and the desk paid for that entry with the loss it was meant to prevent.

So this check DERIVES its scope instead of listing it (LAWS section 1, anti-hardcode): every
tracked `.py` a sync commit ever touched is a candidate, and the verdict comes from the history
itself. There is no list to keep current and no file that can fall through by omission.

THE TEST, stated precisely, because a loose one would trample legitimate Dell-authored work --
the guard's own quarantine comment records a sync shipping a LEGITIMATELY NEWER families.py
through the same pipe an hour after it trampled gateway.py. All three must hold:

  1. a SYNC commit removed substantive lines from the file (its parent had them, it does not);
  2. that parent was authored by a NON-SYNC commit -- desk work, not a previous sync's bytes;
  3. the lines are STILL absent at HEAD -- nobody restored them in the meantime.

Anything else is a legitimate refactor, a Dell-authored change, or damage already repaired.

    python3 scripts/check_sync_launder.py            # report; exit 1 if residue
    python3 scripts/check_sync_launder.py --heal     # restore only the CLEAN reverts

TWO VERDICTS, AND THE SPLIT IS THE WHOLE POINT. A line missing since a sync has two possible
causes and they demand opposite actions:

  CLEAN-REVERT -- HEAD's substantive lines are a SUBSET of the pre-sync parent's. Nothing has been
  authored on top; the file simply is the older copy. Restoring the parent blob loses nothing and
  is what `--heal` does. regime_monitor.py was exactly this shape.

  REVIEW -- HEAD carries lines the parent never had, so the file was rewritten after the sync. The
  missing lines may be genuinely superseded work or may be a real loss buried under a later
  refactor, and NOTHING MECHANICAL CAN TELL THOSE APART. Restoring the parent blob here would
  overwrite newer work: a second launder wearing a badge. So these are reported line-by-line and
  never auto-healed. A tool that healed them anyway would be the failure it exists to catch.

`--heal` quarantines the current bytes under data/sync_refused/ before restoring, for the same
reason the pre-commit guard does: a refusal that destroys the only local copy of the other side's
work is not defensible, and a restore that cannot be undone is a second launder wearing a badge.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

#: Resolved from __file__ so a cron line with no cwd still inspects the right checkout -- but
#: OVERRIDABLE, because a root that only ever means "my own directory" cannot be pointed at a
#: worktree and cannot be tested against a scratch repo. `cwd=` does NOT redirect a __file__
#: -resolved script, which is the exact trap this desk has already paid for twice.
ROOT = Path(__file__).resolve().parent.parent

#: A commit whose subject marks it as machine-produced tree-sweep rather than authored work.
SYNC_MARKERS = ("hourly sync", "desk sync", "tree sweep")

#: Below this many still-missing substantive lines the finding is noise -- a moved import, a
#: reflowed docstring. The measured launders are 122, 148 and 204 lines; the floor is nowhere
#: near them and exists only to keep the report readable.
MIN_LINES = 12


def git(*args: str) -> str:
    r = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True,
                       timeout=300, check=False)
    return r.stdout if r.returncode == 0 else ""


def is_sync(subject: str) -> bool:
    s = subject.lower()
    return any(m in s for m in SYNC_MARKERS)


def substantive(text: str) -> set[str]:
    """Lines that carry meaning. Blank lines, lone delimiters and bare comment markers are
    excluded so that reformatting cannot masquerade as a deletion."""
    out = set()
    for raw in text.splitlines():
        line = raw.strip()
        if len(line) > 3 and line not in ("):", "]:", "})", "}", "]", ")", "\"\"\"", "#"):
            out.add(line)
    return out


def subjects() -> dict[str, str]:
    out = {}
    for line in git("log", "--format=%H %s").splitlines():
        h, _, s = line.partition(" ")
        out[h] = s
    return out


def candidates(subs: dict[str, str]) -> set[str]:
    """Every tracked .py a sync commit ever touched. Derived, never listed."""
    files: set[str] = set()
    for h, s in subs.items():
        if not is_sync(s):
            continue
        for f in git("show", "--name-only", "--format=", h).splitlines():
            f = f.strip()
            if f.endswith(".py"):
                files.add(f)
    tracked = set(git("ls-files").splitlines())
    return {f for f in files if f in tracked}


Row = dict[str, Any]


def scan() -> list[Row]:
    subs = subjects()
    found: list[Row] = []
    for rel in sorted(candidates(subs)):
        head = substantive(git("show", f"HEAD:{rel}"))
        # Commits touching this file, newest first, as (sha, subject).
        hist = [(h, subs.get(h, "")) for h in git("log", "--format=%H", "--", rel).splitlines()]
        for i, (sha, subj) in enumerate(hist):
            if not is_sync(subj) or i + 1 >= len(hist):
                continue
            parent, parent_subj = hist[i + 1]
            if is_sync(parent_subj):
                continue                      # condition 2: the loss must be of authored work
            before = substantive(git("show", f"{parent}:{rel}"))
            after = substantive(git("show", f"{sha}:{rel}"))
            removed = before - after          # condition 1
            missing = removed - head          # condition 3
            if len(missing) >= MIN_LINES:
                # CLEAN-REVERT vs REVIEW: has anything been authored on top SINCE THE SYNC?
                # Measured against the SYNC's own content, never the parent's -- the sync's stale
                # bytes are not "work authored on top", and comparing to the parent counts them
                # as such, which mis-files every real launder as unhealable REVIEW.
                added_since = head - after
                found.append({
                    "file": rel,
                    "verdict": "CLEAN-REVERT" if not added_since else "REVIEW",
                    "lines_lost": len(missing),
                    "lines_added_since": len(added_since),
                    "sync_commit": sha[:8],
                    "sync_subject": subj[:70],
                    "authored_by": parent[:8],
                    "authored_subject": parent_subj[:70],
                    "sample": sorted(missing)[:8],
                })
                break                          # oldest surviving loss per file is the one to heal
    return found


def heal(rows: list[Row]) -> list[str]:
    """Restore ONLY the clean reverts. A REVIEW row is left exactly as it is, on purpose."""
    healed = []
    stamp = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%S")
    for row in rows:
        if row.get("verdict") != "CLEAN-REVERT":
            continue
        rel = str(row["file"])
        src = ROOT / rel
        if src.is_file():
            dest = ROOT / "data" / "sync_refused" / stamp / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(src.read_bytes())
        blob = git("show", f"{row['authored_by']}:{rel}")
        if blob:
            src.write_text(blob, "utf-8")
            healed.append(rel)
    return healed


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--heal", action="store_true",
                    help="restore each residue file from its pre-sync authored parent")
    ap.add_argument("--root", default=None,
                    help="repository to inspect (default: this script's own checkout)")
    args = ap.parse_args()

    if args.root:
        global ROOT
        ROOT = Path(args.root).resolve()

    out_path = ROOT / "data" / "sync_launder.json"
    rows = scan()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps({
        "checked": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "residue": rows,
    }, indent=1) + "\n", "utf-8")

    if not rows:
        print("no launder residue: every sync-removed line of authored code is back at HEAD")
        return 0

    for row in rows:
        print(f"[{row['verdict']:12s}] {row['file']}: {row['lines_lost']} authored line(s) "
              f"removed by {row['sync_commit']} ({row['sync_subject']}) and never restored -- "
              f"written by {row['authored_by']} ({row['authored_subject']})")
        if row["verdict"] == "REVIEW":
            print(f"               {row['lines_added_since']} line(s) authored on top since, so "
                  "the parent blob may NOT be restored wholesale. Missing lines, e.g.:")
            for line in row["sample"][:4]:
                print(f"                 - {line[:100]}")
    clean = [r for r in rows if r["verdict"] == "CLEAN-REVERT"]
    if args.heal:
        for rel in heal(rows):
            print(f"  healed {rel} (previous bytes quarantined under data/sync_refused/)")
        if len(clean) < len(rows):
            print(f"  {len(rows) - len(clean)} REVIEW row(s) left untouched -- restoring them "
                  "would overwrite work authored after the sync")
    elif clean:
        print(f"re-run with --heal to restore the {len(clean)} CLEAN-REVERT row(s); the REVIEW "
              "rows need a judgement, not a blob copy")
    else:
        print("every row needs a judgement -- a deliberate revert of desk work belongs in a "
              "commit that says so, not inside a sync")

    # ONLY A CLEAN REVERT FAILS THE GATE, and that asymmetry is deliberate. A REVIEW row cannot be
    # closed by this script -- it needs a human to read two versions of a rewritten file -- so
    # failing on it would leave the gate permanently red. max_audit's own ci-gate-red comment
    # records what that costs: a red nobody can act on recurs, gets skimmed, and BURIES a real one.
    # REVIEW rows are reported every run and routed to the gap register once; CLEAN-REVERT is the
    # actionable half and is the only thing that stops the line.
    return 1 if clean else 0


if __name__ == "__main__":
    sys.exit(main())

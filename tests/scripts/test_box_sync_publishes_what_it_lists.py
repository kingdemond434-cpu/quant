"""A PATH THE SYNC LISTS BUT GIT IGNORES PUBLISHES NOTHING, AND REPORTS SUCCESS DOING IT.

`git add` on an ignored path is not an error. It is a no-op with exit 0. So a sync can list a
file, add it, commit, push, log "synced 5 file(s)", and have carried four -- and every log line,
every exit code and every dashboard tile agrees it worked.

MEASURED 2026-09-06. `sync_shadow_to_git.ps1` listed `desks/mt5/data/sleeves.json` in $relPaths
while `.gitignore` carried `**/sleeves.json`, so that file had never once crossed the wire. The
three shadow LANE state files -- the ones holding every sleeve's status, forward n, expectancy and
day count -- were not listed at all, and were ignored by `**/reports/shadow/*` into the bargain.
The only artifact that actually reached the branch was a 424-byte health summary saying
`status: OPERATING`.

THE COST. "Are the two gold scalp sleeves ready for live capital?" was asked repeatedly over days
and could not be answered from the branch, because the branch contained no sleeve. Answers got
assembled from historical selection-era rows instead, which is how a forward count of zero was
once described as fifty-plus trades. A wire that carries a summary and calls itself a sync invites
exactly that substitution.

The script's OWN HEADER documents this failure mode, in the file where it was live. Documenting a
trap is not the same as fencing it, which is the general lesson and the reason this file exists.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent.parent
_SYNC = _ROOT / "desks" / "mt5" / "scripts" / "sync_shadow_to_git.ps1"


def _rel_paths() -> list[str]:
    """The $relPaths array, read from the script itself.

    Parsed rather than restated. A hardcoded copy in this test would pass forever after someone
    adds a sixth path to the script -- which is precisely how the fifth one got in unfenced.
    """
    src = _SYNC.read_text("utf-8", errors="ignore")
    start = src.index("$relPaths = @(")
    block = src[start:src.index("\n)", start)]
    quoted = re.findall(r'"([^"]+\.json)"', block)
    return [p for p in quoted if "/" in p]


def test_the_list_is_found_and_is_not_empty() -> None:
    """Without this, every assertion below passes vacuously on a parse miss (L1.63)."""
    paths = _rel_paths()
    assert len(paths) >= 5, (
        f"parsed only {paths} from $relPaths -- the array moved or its shape changed, and a "
        "fence that cannot find its subject is not fencing anything")


@pytest.mark.parametrize("rel", _rel_paths())
def test_every_synced_path_is_addable(rel: str) -> None:
    """THE DEFECT. Each listed path must survive .gitignore, or the sync silently drops it.

    The verdict comes from bare `check-ignore` -- exit 0 means IGNORED. Not from `-v`, which
    exits 0 whenever the path matches any rule INCLUDING a `!` allowlist, so a `-v`-based fence
    reports every correctly-allowlisted file as ignored. `-v` is used only to quote the rule in
    the failure message, which is what it is actually for.
    """
    ignored = subprocess.run(["git", "check-ignore", "-q", "--", rel],
                             cwd=_ROOT, capture_output=True, text=True, check=False)
    why = subprocess.run(["git", "check-ignore", "-v", "--", rel],
                         cwd=_ROOT, capture_output=True, text=True, check=False).stdout.strip()
    assert ignored.returncode != 0, (
        f"{rel} is listed in $relPaths but .gitignore excludes it:\n    {why}\n"
        "`git add` on an ignored path exits 0 and stages nothing, so the sync will report success "
        "and publish nothing. Add a `!` allowlist line at the END of .gitignore -- last match "
        "wins -- or drop the path from $relPaths. Do not leave it listed and ignored.")


def test_the_lane_state_files_are_carried_not_just_the_summary() -> None:
    """A heartbeat is not a report.

    `shadow_health.json` says OPERATING and gives counts. It contains no sleeve. Answering any
    question about a specific sleeve from a branch carrying only the summary means answering it
    from something else -- and the something else was historical rows.
    """
    listed = set(_rel_paths())
    for lane in ("scalp_shadow_state.json", "qquant_shadow_state.json", "shadow_state.json"):
        assert any(p.endswith(lane) for p in listed), (
            f"{lane} is not synced, so no reader off the box can see the sleeves in that lane -- "
            "their status, forward n, expectancy and day count all stay on one Windows machine")


def test_the_allowlist_sits_after_the_rules_it_overrides() -> None:
    """Gitignore is last-match-wins, so an allowlist above its exclusion does nothing.

    This is not hypothetical here: `**/sleeves.json` and `**/reports/shadow/*` both live in the
    middle of the file. A `!` line placed before them would read as a fix, pass review, and change
    nothing at all -- the same silent-success shape as the bug it was meant to fix.
    """
    lines = (_ROOT / ".gitignore").read_text("utf-8").splitlines()
    for allow, blocked in (("!desks/mt5/data/sleeves.json", "**/sleeves.json"),
                           ("!desks/mt5/reports/shadow/scalp_shadow_state.json",
                            "**/reports/shadow/*")):
        assert allow in lines, f"{allow} is gone; the sync goes back to publishing nothing for it"
        assert lines.index(allow) > lines.index(blocked), (
            f"{allow} appears BEFORE {blocked}; gitignore takes the last match, so the exclusion "
            "still wins and this allowlist is decorative")

#!/usr/bin/env python3
"""THE BOX STATE PUBLISHER (Level 2, ops/release/authority/LEVEL2.md step 2).

Once the LIVE ruleset requires the release authority's status, nothing may push LIVE directly,
except the identities on its bypass list. The box's state still has to reach origin every few
minutes, so this service is the ONLY box identity on that list. It runs as its own Windows account
(`quant-publisher`), the only account that can read the state App's key. It can push nothing but
state BY CONSTRUCTION:

  1. It fetches the box checkout's HEAD (read-only access to its .git, never its worktree, so it
     never sees data/secrets/**) and origin/LIVE into its own clone.
  2. It takes the paths the BOX changed since the two diverged (merge-base..box HEAD, which is
     today's Adopt-Release rule: the box's state is the box's, origin's edits elsewhere stand).
  3. It keeps only publishable paths (`publishable()`): a fixed subset of release.py's state,
     minus docs/ and minus the behaviour switches (*_ENABLED*, *_DISABLED*,
     the governed-state files), which change what code does and so travel by PR.
  4. It overlays exactly those paths onto a fresh checkout of origin/LIVE, commits, re-checks
     that the commit's diff against origin/LIVE is publishable paths only, and pushes it as a
     fast-forward (never a force). A race loses and is retried on the next pass.

Code, workflows, tests and the gate itself are never in a commit THIS PROGRAM makes. That
constrains the program, not the key: the state App bypasses the LIVE ruleset outright, so anyone
holding its key could push any tree. The control is confinement of the key to the
quant-publisher account, and the detector: every authority pass checks each LIVE commit the state
App authored, and on any non-publishable path it raises the DEACTIVATE kill file (authority.py
`state_app_violations`). Exit 0: published or nothing to publish; 1: failed; 2: refused.

    python publish.py --src C:\\opt\\quant --work C:\\opt\\publisher\\repo [--dry-run]
"""

from __future__ import annotations

import argparse
import fnmatch
import subprocess
import sys
from pathlib import Path

LIVE = "claude/llm-auto-upgrade-verify-gcjac3"

# WHAT MAY BE PUBLISHED, FIXED HERE (root, pinned) rather than imported from libs/ops/release.py,
# which is not root: a PR widening STATE_PREFIXES must never widen what this key can push. A
# SUBSET of release.py's state (tests/ops/test_state_publisher.py pins that), so a new state file
# is withheld until it is named here -- the safe direction.
PUBLISH_PREFIXES: tuple[str, ...] = (
    "desks/mt5/data/", "desks/mt5/reports/", "desks/mt5/logs/",
    "desks/mt5/frontier_intel/data/", "desks/mt5/side_channels/data/",
    "data/", "reports/", "logs/",
)  # fmt: skip
PUBLISH_FILES: frozenset[str] = frozenset({
    "context/decision_journal.jsonl", "desks/mt5/docs/TRADE_PATH_REPORT.md",
    "desks/mt5/gateway_state.json", "desks/mt5/hunt11.json", "desks/mt5/mech_battery.json",
    "desks/mt5/mech_split.json", "desks/mt5/portfolio_projection.json",
    "desks/mt5/regime_state.json", "desks/mt5/swap_exposure.json", "desks/mt5/sync_marker.json",
})  # fmt: skip
# State that GOVERNS what code may do (release.GOVERNED_STATE_FILES) plus the rows that authorise
# a seal or an adoption: box-written, but a change to one is a change to the rules, so it goes by
# PR through the authority, never by this key.
WITHHELD_FILES: frozenset[str] = frozenset({
    "desks/mt5/data/ALLOCATOR_SOVEREIGN.json", "desks/mt5/data/IMMUTABLE_MANIFEST.json",
    "desks/mt5/data/LIVE_MANIFEST.jsonl", "desks/mt5/data/UNIVERSAL_SURVIVORS.canon.json",
    "desks/mt5/reports/ALLOCATOR_PROOF.json", "desks/mt5/data/SEAL_CLEARS.jsonl",
    "desks/mt5/data/ADOPT_CLEARS.jsonl",
})  # fmt: skip
# Curated: a file whose presence or contents switches behaviour (#650 audit SF3).
SWITCH_GLOBS = ("*_ENABLED*", "*_DISABLED*", "*_ARMED*", "*_ENFORCE*", "*_OFF", "*_OFF.*",
                "DEACTIVATE*", "PRINCIPAL_*", "*KILL*", "*_HALT*", "*_STOP", "*_STOP.*",
                "*OVERRIDE*")  # fmt: skip
NEVER_NAMES = frozenset({".gitattributes", ".gitmodules", ".gitignore", ".mailmap"})
REGULAR_MODES = frozenset({"100644", "100755"})
CODE_SUFFIXES = (".py", ".pyw", ".ps1", ".psm1", ".sh", ".cmd", ".bat", ".exe", ".dll",
                 ".yml", ".yaml", ".toml", ".cfg", ".ini", ".js", ".html", ".pth")  # fmt: skip


def publishable(rel: str) -> bool:
    p = str(rel).replace("\\", "/")
    if not p or p.startswith(("/", "./")) or ".." in p.split("/") or "/secrets/" in f"/{p}":
        return False
    if p.lower().endswith(CODE_SUFFIXES) or p in WITHHELD_FILES:
        return False
    name = p.rsplit("/", 1)[-1]
    if name in NEVER_NAMES:
        return False
    if any(fnmatch.fnmatchcase(name, g) for g in SWITCH_GLOBS):
        return False
    return p in PUBLISH_FILES or any(p.startswith(x) for x in PUBLISH_PREFIXES)


def git(work: Path, *args: str, check: bool = True, stdin: str | None = None) -> str:
    p = subprocess.run(["git", "-c", "safe.directory=*", "-C", str(work), *args], input=stdin,
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       check=False)  # fmt: skip
    if check and p.returncode != 0:
        raise RuntimeError(f"git {' '.join(args[:3])}: {p.stderr.strip()[:300]}")
    return p.stdout


def plan(box_changed: list[str]) -> tuple[list[str], list[str]]:
    keep = sorted({p for p in box_changed if publishable(p)})
    withheld = sorted({p for p in box_changed if p and not publishable(p)})
    return keep, withheld


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--src", required=True, help="the box checkout (only its .git is read)")
    ap.add_argument("--work", required=True, help="the publisher's own clone")
    ap.add_argument("--branch", default=LIVE)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    work, br = Path(a.work), a.branch
    try:
        live = f"origin/{br}"
        git(work, "fetch", "-q", "--no-tags", "origin", f"+refs/heads/{br}:refs/remotes/{live}")
        git(work, "checkout", "-q", "-f", "--detach", live)
        git(work, "clean", "-q", "-fdx")
        git(work, "fetch", "-q", "--no-tags", str(Path(a.src)), "+HEAD:refs/box/head")
        box = "refs/box/head"
        base = git(work, "merge-base", box, live).strip()

        def names(*rev: str) -> set[str]:
            out = git(work, "diff", "--name-only", "--no-renames", "-z", *rev)
            return {n for n in out.split("\0") if n}

        keep, withheld = plan(sorted(names(base, box)))
        if withheld:
            print(f"withheld (not state, goes by PR): {len(withheld)}: {', '.join(withheld[:8])}")
        todo = sorted(set(keep) & names(live, box))
        modes: dict[str, str] = {}
        for entry in git(work, "ls-tree", "-r", "-z", box).split("\0"):
            if "\t" in entry:
                meta, path = entry.split("\t", 1)
                modes[path] = meta.split(" ", 1)[0]
        odd = [p for p in todo if p in modes and modes[p] not in REGULAR_MODES]
        if odd:  # symlinks and gitlinks never travel (#650 audit SF2)
            print(f"withheld (not a regular file): {', '.join(odd[:8])}")
            todo = [p for p in todo if p not in odd]
        present = set(modes)
        if not todo:
            print("nothing to publish")
            return 0
        there = [p for p in todo if p in present]
        gone = [p for p in todo if p not in present]
        if there:
            git(work, "checkout", box, "--pathspec-from-file=-", "--pathspec-file-nul",
                stdin="\0".join(there))  # fmt: skip
        if gone:
            git(work, "rm", "-q", "--ignore-unmatch", "--pathspec-from-file=-",
                "--pathspec-file-nul", stdin="\0".join(gone))  # fmt: skip
        staged = [n for n in git(work, "diff", "--cached", "--name-only", "-z", live).split("\0")
                  if n]  # fmt: skip
        bad = [p for p in staged if not publishable(p)]
        if bad:  # cannot happen by construction; refuse loudly if it ever does
            print(f"REFUSED: non-state paths staged: {bad[:8]}")
            return 2
        if not staged:
            print("nothing to publish")
            return 0
        if a.dry_run:
            print(f"would publish {len(staged)} state path(s)")
            return 0
        git(work, "-c", "user.name=quant-publisher", "-c", "user.email=publisher@quant.invalid",
            "commit", "-q", "--no-verify", "-m",
            f"box state publication: {len(staged)} path(s)")  # fmt: skip
        out = subprocess.run(["git", "-c", "safe.directory=*", "-C", str(work), "push", "-q",
                              "--no-verify", "origin", f"HEAD:refs/heads/{br}"],
                             capture_output=True, text=True, check=False)  # fmt: skip
        if out.returncode != 0:
            print(f"push lost a race or was refused; next pass retries: {out.stderr.strip()[:200]}")
            return 1
        print(f"published {len(staged)} state path(s)")
        return 0
    except RuntimeError as exc:
        print(f"failed: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())

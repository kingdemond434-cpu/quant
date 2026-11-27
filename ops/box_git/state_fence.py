"""The box-state fence: what the forge loop may publish from MT5-ShadowSync's bundle outbox.

Audit route C (2026-11-26). ShadowSync no longer pushes anything. It hands its fenced state
commit over as a bundle; the loop's `state` stage checks it HERE and publishes it to the work
branch claude/box-state as the `claude` thread account. LIVE is never touched, so the gate's
CLEAR plus box CI stay the second fence for anything that could ever reach LIVE.

This file is pinned by the trust set T (ops/box_git/TRUST_SET.json `files`; zuck 2026-11-26
09:11Z, Audit ruling C): once LIVE contains the boot, run_loop.cmd runs the loop from LIVE's tip,
so a change to what the fence allows needs the owner's AUTHORIZE TRUST, never a quiet edit.

THE FENCE, all of it, or nothing is published:
  * the commit has exactly ONE parent, and that parent is the forge LIVE tip right now (a stale
    parent is refused: ShadowSync rebuilds on the new tip next slot);
  * every changed path is publishable() (state prefixes and files only; never code, never a
    switch file, never a governed or authorising file, never .gitignore and friends);
  * no deletion, no rename away, no symlink, no submodule: added or modified regular files only.

publishable() is a FIXED COPY of ops/release/publisher/publish.py's root-pinned fence. It is
copied rather than imported so the boot code never runs LIVE's (unreviewed for this purpose)
version; tests/ops/test_box_git_state_fence.py pins the copy's verdicts on known paths.
"""
from __future__ import annotations

import fnmatch
from collections.abc import Callable, Sequence

Git = Callable[[Sequence[str]], tuple[int, str]]   # git(args) -> (rc, stdout)

PUBLISH_PREFIXES: tuple[str, ...] = (
    "desks/mt5/data/", "desks/mt5/reports/", "desks/mt5/logs/",
    "desks/mt5/frontier_intel/data/", "desks/mt5/side_channels/data/",
    "data/", "reports/", "logs/",
)
PUBLISH_FILES: frozenset[str] = frozenset({
    "context/decision_journal.jsonl", "desks/mt5/docs/TRADE_PATH_REPORT.md",
    "desks/mt5/gateway_state.json", "desks/mt5/hunt11.json", "desks/mt5/mech_battery.json",
    "desks/mt5/mech_split.json", "desks/mt5/portfolio_projection.json",
    "desks/mt5/regime_state.json", "desks/mt5/swap_exposure.json", "desks/mt5/sync_marker.json",
})
WITHHELD_FILES: frozenset[str] = frozenset({
    "desks/mt5/data/ALLOCATOR_SOVEREIGN.json", "desks/mt5/data/IMMUTABLE_MANIFEST.json",
    "desks/mt5/data/LIVE_MANIFEST.jsonl", "desks/mt5/data/UNIVERSAL_SURVIVORS.canon.json",
    "desks/mt5/reports/ALLOCATOR_PROOF.json", "desks/mt5/data/SEAL_CLEARS.jsonl",
    "desks/mt5/data/ADOPT_CLEARS.jsonl",
})
SWITCH_GLOBS = ("*_ENABLED*", "*_DISABLED*", "*_ARMED*", "*_ENFORCE*", "*_OFF", "*_OFF.*",
                "DEACTIVATE*", "PRINCIPAL_*", "*KILL*", "*_HALT*", "*_STOP", "*_STOP.*",
                "*OVERRIDE*")
NEVER_NAMES = frozenset({".gitattributes", ".gitmodules", ".gitignore", ".mailmap"})
REGULAR_MODES = frozenset({"100644", "100755"})
CODE_SUFFIXES = (".py", ".pyw", ".ps1", ".psm1", ".sh", ".cmd", ".bat", ".exe", ".dll",
                 ".yml", ".yaml", ".toml", ".cfg", ".ini", ".js", ".html", ".pth")


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


def refusals(git: Git, commit: str, live_tip: str) -> list[str]:
    """Why `commit` may not be published (empty list: it may). Fails closed on any git error."""
    rc, out = git(["rev-list", "--parents", "-n", "1", commit])
    if rc != 0 or not out.strip():
        return [f"commit {commit[:12]} unreadable"]
    parents = out.split()[1:]
    if len(parents) != 1:
        return [f"{len(parents)} parents: exactly one is allowed"]
    if parents[0] != live_tip:
        return [f"stale parent {parents[0][:12]}: the forge LIVE tip is {live_tip[:12]}"]
    rc, raw = git(["diff-tree", "-r", "-z", "--no-renames", "--no-commit-id", parents[0],
                   commit])
    if rc != 0:
        return ["diff unreadable"]
    fields = raw.split("\0")
    out_: list[str] = []
    n = 0
    i = 0
    while i + 1 < len(fields) and fields[i].startswith(":"):
        meta, path = fields[i][1:].split(" "), fields[i + 1]
        i += 2
        n += 1
        new_mode, status = meta[1], meta[4]
        if status not in ("A", "M"):
            out_.append(f"{path}: status {status} (only added or modified files publish)")
        elif new_mode not in REGULAR_MODES:
            out_.append(f"{path}: mode {new_mode} is not a regular file")
        elif not publishable(path):
            out_.append(f"{path}: not a publishable state path")
    if n == 0:
        out_.append("no change against the LIVE tip")
    return out_

#!/usr/bin/env python3
"""Pre-commit guard for the money path (GAP 134) -- the trample dies at the commit boundary.

MEASURED ATTACK, 2026-08-26 02:02 UTC: the Dell-side hourly sync (sync_to_vps.ps1) scp'd a stale
copy of `C:\\Users\\dell\\mt5-research` over desks/mt5 and then ran `git add desks/mt5 && git
commit` on this box over ssh -- commit 7cb174af removed ~1078 lines from gateway.py, 207 from
engine.py, 264 from shadow_forward.py and stripped every fence marker. The content fence
(check_moneypath_fence.py) healed the tree 3 minutes later, but the stale code sat in HEAD and
the flip-flop repeats hourly. The Dell script cannot be edited from this box (no inbound route);
its git commands CAN be governed here, because they run in this repo and hooks apply.

Two layers, both restore-and-continue (never abort the whole commit -- the same sync commit
carries legitimate state JSONs that must land):

1. SSH context (`SSH_CONNECTION` set, as it is for the Dell's ssh-run git): code never travels
   Dell -> VPS. Every staged change to desks/mt5/**/*.py or scripts/build_zentech_state.py is
   unstaged and the worktree copy restored from HEAD; a staged NEW .py is unstaged but left in
   the worktree untracked (nothing is destroyed, nothing enters history unreviewed).
   Escape hatch for a deliberate principal act: QUANT_ALLOW_SSH_PY=1.

2. Every context: a staged change may never STRIP a fence marker that HEAD still carries.
   Markers are read live from check_moneypath_fence.py's PROTECTED map, so a deliberate marker
   retirement is done by changing that map in the same commit -- which changes what this guard
   enforces. This layer also stops the measured 2026-08-25 local-sibling overwrite class.

The fence's own repair commits use --no-verify and bypass this guard by design.
"""
from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOG = ROOT / "data" / "moneypath_fence.log"


def log(msg: str) -> None:
    line = f"{datetime.now(tz=UTC).isoformat(timespec='seconds')} {msg}"
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with LOG.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass
    print(line, file=sys.stderr)


def git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True,
                          timeout=120, check=False)


def staged_files() -> dict[str, str]:
    """path -> one-letter status (A/M/D/R...) for everything staged."""
    r = git("diff", "--cached", "--name-status", "-z")
    out: dict[str, str] = {}
    if r.returncode != 0:
        return out
    parts = r.stdout.split("\0")
    i = 0
    while i < len(parts) - 1:
        status = parts[i][:1]
        if status in ("R", "C"):  # rename/copy: old path, new path
            out[parts[i + 2]] = status
            i += 3
        else:
            out[parts[i + 1]] = status
            i += 2
    return out


def unstage_and_restore(path: str, status: str) -> None:
    if status == "A":
        # New file from the sync: keep it out of history, keep the bytes on disk for review.
        git("rm", "--cached", "-q", "--", path)
        return
    # QUARANTINE BEFORE RESTORE. The refused copy is not always stale garbage: measured
    # 2026-08-26 03:00Z, the Dell shipped a LEGITIMATELY NEWER families.py (the 14-family
    # zero-hardcode registry) through the same pipe that trampled gateway.py an hour earlier.
    # Restoring from HEAD without saving the bytes would make this box destroy the only local
    # copy of C:-authored work; the quarantine keeps refusal reversible, which is what makes a
    # hard refusal defensible at all.
    src = ROOT / path
    if src.is_file():
        stamp = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%S")
        dest = ROOT / "data" / "sync_refused" / stamp / path
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(src.read_bytes())
        except OSError:
            pass
    git("checkout", "-q", "HEAD", "--", path)


def load_protected() -> dict[str, str | tuple[str, ...]]:
    spec = importlib.util.spec_from_file_location(
        "check_moneypath_fence", ROOT / "scripts" / "check_moneypath_fence.py")
    if spec is None or spec.loader is None:
        return {}
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except Exception:
        return {}
    return getattr(mod, "PROTECTED", {})


def markers(spec: str | tuple[str, ...]) -> tuple[str, ...]:
    return (spec,) if isinstance(spec, str) else spec


def blob(rev_path: str) -> str | None:
    r = git("show", rev_path)
    return r.stdout if r.returncode == 0 else None


def main() -> int:
    staged = staged_files()
    if not staged:
        return 0
    refused: list[str] = []

    # Layer 1: code never travels Dell -> VPS (ssh-context .py freeze).
    ssh_ctx = bool(os.environ.get("SSH_CONNECTION")) and not os.environ.get("QUANT_ALLOW_SSH_PY")
    if ssh_ctx:
        for path, status in list(staged.items()):
            is_desk_py = path.startswith("desks/mt5/") and path.endswith(".py")
            if is_desk_py or path == "scripts/build_zentech_state.py":
                unstage_and_restore(path, status)
                refused.append(path)
                del staged[path]
        if refused:
            log(f"PRECOMMIT-GUARD ssh-context: refused {len(refused)} staged .py change(s) "
                f"(code never travels Dell->VPS; QUANT_ALLOW_SSH_PY=1 overrides): "
                f"{', '.join(sorted(refused))}")

    # Layer 2: a staged change may never strip a marker HEAD still carries.
    protected = load_protected()
    stripped: list[str] = []
    for path, spec in protected.items():
        if path not in staged or staged[path] == "A":
            continue
        head = blob(f"HEAD:{path}")
        if head is None or not all(m in head for m in markers(spec)):
            continue  # HEAD itself is not canon here; that is the content fence's job
        idx = blob(f":{path}") or ""
        missing = [m for m in markers(spec) if m not in idx]
        if missing:
            unstage_and_restore(path, staged[path])
            stripped.append(path)
    if stripped:
        log(f"PRECOMMIT-GUARD marker-strip: restored {len(stripped)} file(s) whose staged copy "
            f"lost a canon marker HEAD carries: {', '.join(sorted(stripped))}")

    # Restore-and-continue: the rest of the commit (state JSONs, reports) proceeds. If nothing
    # is left staged, git itself fails the commit with 'nothing to commit' -- the truthful
    # outcome for an all-trample commit.
    return 0


if __name__ == "__main__":
    sys.exit(main())

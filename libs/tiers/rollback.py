"""ONE-OPERATION ROLLBACK for the Tier S digital twin (layer 28).

`plan()` names the current code and the previous sealed release (LIVE_MANIFEST `code` SHAs) and
the CODE paths between them; state paths (`libs.ops.release.is_state_path`) are left as the box
has them, because the box's state is the box's. `apply()` makes ONE commit on the current branch
whose code equals the target's. It never rewrites history and never pushes: MT5-AdoptRelease
adopts the commit once a human pushes it. The hourly `tier_s` organ publishes the plan; the
command is `python desks/mt5/research/tier_s.py --rollback-to <sha> --apply-rollback`.

AN UNSEALED TARGET IS REFUSED HERE, not only by the command line. A rollback exists to return the
box to code that was sealed and ran; a commit that was never sealed is an untested tree wearing a
rollback's name, so `apply()` raises `RollbackRefused` before touching a file.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from libs.ops.release import is_state_path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST_REL = Path("desks") / "mt5" / "data" / "LIVE_MANIFEST.jsonl"
MANIFEST = ROOT / MANIFEST_REL


class RollbackRefused(RuntimeError):
    """The plan is not one this module will carry out (unavailable, or an unsealed target)."""


def _root(root: Path | None) -> Path:
    return Path(root) if root is not None else ROOT


def _git(*args: str, root: Path | None = None) -> str:
    return subprocess.run(["git", *args], cwd=_root(root), check=True, capture_output=True,
                          text=True).stdout.strip()


def sealed_releases(root: Path | None = None) -> list[str]:
    manifest = MANIFEST if root is None else Path(root) / MANIFEST_REL
    out: list[str] = []
    if manifest.exists():
        for line in manifest.read_text("utf-8", errors="replace").splitlines():
            try:
                sha = str(json.loads(line).get("code") or "")
            except (ValueError, AttributeError):
                continue
            if sha and (not out or out[-1] != sha):
                out.append(sha)
    return out


def _full(sha: str, root: Path | None) -> str | None:
    try:
        return _git("rev-parse", "--verify", f"{sha}^{{commit}}", root=root)
    except subprocess.CalledProcessError:
        return None


def plan(target: str | None, root: Path | None = None) -> dict[str, object]:
    head = _git("rev-parse", "HEAD", root=root)
    seals = sealed_releases(root)
    if target is None:
        prior = [s for s in seals if s != head]
        if not prior:
            return {"available": False, "why": "no earlier sealed release in LIVE_MANIFEST"}
        target = prior[-1]
    full = _full(target, root)
    if full is None:
        return {"available": False, "why": f"{target} is not a commit in this clone"}
    sealed_full = {f for f in (_full(s, root) for s in seals) if f}
    changed = [p for p in _git("diff", "--name-only", full, "HEAD", root=root).splitlines() if p]
    code = [p for p in changed if not is_state_path(p)]
    return {"available": True, "head": head, "target": full,
            "sealed": full in sealed_full, "code_paths": code,
            "state_paths_kept": len(changed) - len(code)}


def apply(p: dict[str, object], root: Path | None = None) -> str:
    """ONE commit whose code equals the target's; returns its SHA (or a nothing-to-do line).

    Raises `RollbackRefused` for an unavailable plan or an unsealed target, before any write."""
    if not p.get("available"):
        raise RollbackRefused(f"no rollback available: {p.get('why')}")
    if not p.get("sealed"):
        raise RollbackRefused(f"refusing: {p.get('target')} is not a sealed release in "
                              "LIVE_MANIFEST")
    target = str(p["target"])
    code = [str(x) for x in p["code_paths"]]  # type: ignore[attr-defined]
    if not code:
        return "nothing to roll back: code already equals the target"
    present = set(_git("ls-tree", "-r", "--name-only", target, root=root).splitlines())
    restore = [c for c in code if c in present]
    remove = [c for c in code if c not in present]
    if restore:
        _git("checkout", target, "--", *restore, root=root)
    if remove:
        _git("rm", "-q", "--", *remove, root=root)
    _git("commit", "-m", f"tier_s rollback: code to sealed release {target[:12]}",
         "--", *code, root=root)
    return _git("rev-parse", "HEAD", root=root)

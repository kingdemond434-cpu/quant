"""ONE-OPERATION ROLLBACK for the Tier S digital twin (layer 28).

`plan()` names the current code and the previous sealed release (LIVE_MANIFEST `code` SHAs) and
the CODE paths between them; state paths (`libs.ops.release.is_state_path`) are left as the box
has them, because the box's state is the box's. `apply()` makes ONE commit on the current branch
whose code equals the target's. It never rewrites history and never pushes: MT5-AdoptRelease
adopts the commit once a human pushes it. The hourly `tier_s` organ publishes the plan; the
command is `python desks/mt5/research/tier_s.py --rollback-to <sha> --apply-rollback`.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from libs.ops.release import is_state_path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "desks" / "mt5" / "data" / "LIVE_MANIFEST.jsonl"


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True,
                          text=True).stdout.strip()


def sealed_releases() -> list[str]:
    out: list[str] = []
    if MANIFEST.exists():
        for line in MANIFEST.read_text("utf-8", errors="replace").splitlines():
            try:
                sha = str(json.loads(line).get("code") or "")
            except ValueError:
                continue
            if sha and (not out or out[-1] != sha):
                out.append(sha)
    return out


def plan(target: str | None) -> dict[str, object]:
    head = _git("rev-parse", "HEAD")
    seals = sealed_releases()
    if target is None:
        prior = [s for s in seals if s != head]
        if not prior:
            return {"available": False, "why": "no earlier sealed release in LIVE_MANIFEST"}
        target = prior[-1]
    try:
        _git("cat-file", "-e", f"{target}^{{commit}}")
    except subprocess.CalledProcessError:
        return {"available": False, "why": f"{target} is not a commit in this clone"}
    changed = [p for p in _git("diff", "--name-only", target, "HEAD").splitlines() if p]
    code = [p for p in changed if not is_state_path(p)]
    return {"available": True, "head": head, "target": target,
            "sealed": target in seals, "code_paths": code,
            "state_paths_kept": len(changed) - len(code)}


def apply(p: dict[str, object]) -> str:
    target = str(p["target"])
    code = [str(x) for x in p["code_paths"]]  # type: ignore[attr-defined]
    if not code:
        return "nothing to roll back: code already equals the target"
    present = set(_git("ls-tree", "-r", "--name-only", target).splitlines())
    restore = [c for c in code if c in present]
    remove = [c for c in code if c not in present]
    if restore:
        _git("checkout", target, "--", *restore)
    if remove:
        _git("rm", "-q", "--", *remove)
    _git("commit", "-m", f"tier_s rollback: code to sealed release {target[:12]}",
         "--", *code)
    return _git("rev-parse", "HEAD")

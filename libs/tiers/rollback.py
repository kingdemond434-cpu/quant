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


def drill() -> dict[str, object]:
    """Roll back a failed release IN A THROWAWAY REPOSITORY and check what came back.

    The box's rollback is one operator command; whether that command does what it says is a
    property this drill measures every pass instead of on the day it is needed. A temp repo gets
    a sealed release A (code + box state + manifest), then a bad release B that changes the code
    and the state. `plan(None)` must pick A, `apply` must make ONE new commit whose code equals
    A's while the state stays B's (the box's state is the box's), history must not be rewritten
    (B stays an ancestor: no second authority over what ran), and an unsealed target must be
    refused before any write. Never touches this clone.
    """
    import tempfile
    import time
    t0 = time.monotonic()
    code_rel, state_rel = "desks/mt5/research/organ.py", "desks/mt5/data/sleeves.json"
    # Windows marks git's object files read-only, which a plain cleanup raises on.
    with tempfile.TemporaryDirectory(prefix="rollback_drill_", ignore_cleanup_errors=True) as tmp:
        r = Path(tmp)

        def put(rel: str | Path, text: str) -> None:
            p = r / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text, "utf-8")

        def g(*a: str) -> str:
            return _git(*a, root=r)
        g("init", "-q")
        g("config", "user.email", "drill@sandbox")
        g("config", "user.name", "rollback drill")
        g("config", "commit.gpgsign", "false")
        g("config", "core.hooksPath", str(r / ".git" / "no-hooks"))   # the drill's own commits
        put(code_rel, "GOOD = 1\n")
        put(state_rel, '{"v": "A"}\n')
        g("add", "-A")
        g("commit", "-q", "--no-verify", "-m", "release A")
        a = g("rev-parse", "HEAD")
        put(MANIFEST_REL, json.dumps({"code": a}) + "\n")
        g("add", "-A")
        g("commit", "-q", "--no-verify", "-m", "seal A")
        put(code_rel, "GOOD = 0  # the failed release\n")
        put(state_rel, '{"v": "B"}\n')
        g("add", "-A")
        g("commit", "-q", "--no-verify", "-m", "release B (fails its smoke test)")
        b = g("rev-parse", "HEAD")
        checks: dict[str, bool] = {}
        try:
            apply({"available": True, "sealed": False, "target": b, "code_paths": [code_rel]},
                  root=r)
            checks["unsealed_refused"] = False
        except RollbackRefused:
            checks["unsealed_refused"] = g("rev-parse", "HEAD") == b
        p = plan(None, root=r)
        checks["picked_last_sealed"] = p.get("target") == a and bool(p.get("sealed"))
        head = apply(p, root=r)
        checks["one_new_commit"] = g("rev-parse", "HEAD~1") == b and head != b
        checks["code_restored"] = (r / code_rel).read_text("utf-8") == "GOOD = 1\n"
        checks["state_kept"] = (r / state_rel).read_text("utf-8") == '{"v": "B"}\n'
        checks["history_kept"] = subprocess.run(
            ["git", "merge-base", "--is-ancestor", b, "HEAD"], cwd=r).returncode == 0
        checks["tree_clean"] = g("status", "--porcelain") == ""
    ok = all(checks.values())
    return {"status": "PASS" if ok else "FAIL", "checks": checks,
            "failed": [k for k, v in checks.items() if not v],
            "wall_s": round(time.monotonic() - t0, 2),
            "sandbox": "temporary git repository; this clone is never touched"}

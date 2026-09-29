#!/usr/bin/env python3
"""ONE-OPERATION ROLLBACK for the Tier S digital twin (layer 28).

    python scripts/tier_s_rollback.py                  # print the plan: current -> previous seal
    python scripts/tier_s_rollback.py --to <sha>       # print the plan to a named sealed release
    python scripts/tier_s_rollback.py --to <sha> --apply

`--apply` makes ONE commit on the current branch whose tree equals `<sha>`'s tree for every CODE
path (state paths, as `libs.ops.release.is_state_path` defines them, are left as the box has them,
because the box's state is the box's). It never rewrites history, never force-pushes and never
pushes at all: MT5-AdoptRelease adopts the commit once a human pushes it. Dry run is the default.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from libs.ops.release import is_state_path  # noqa: E402

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


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--to", default=None)
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args(argv)
    p = plan(a.to)
    print(json.dumps({k: (v if k != "code_paths" else len(v))  # type: ignore[arg-type]
                      for k, v in p.items()}, indent=1))
    if not p.get("available"):
        return 1
    if a.apply:
        if not p.get("sealed"):
            print("refusing: the target is not a sealed release in LIVE_MANIFEST")
            return 1
        print(f"rolled back in one commit: {apply(p)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

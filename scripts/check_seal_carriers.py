#!/usr/bin/env python3
"""A SEAL CARRIER IS JUDGED ON EVERY PUSH, AND NONE EVER MERGES (Auditor ruling 2026-11-11 13:12Z).

    python scripts/check_seal_carriers.py [--json]

The pre-push law gate refuses unsigned sealed bytes, so a head H the audit cleared can never sit
on a branch for the sign train to find. A carrier branch commits it as data instead:
`desks/mt5/data/seal_carriers/<H>.bundle` (a git bundle whose one tip is H) and `<H>.patch`
(`git format-patch` of H). This fence judges every carrier in the tree with the train's own
check (scripts/sign_train.py `carrier_problems`):

  - the bundle has exactly one tip, H, whose one parent is an ancestor of LIVE;
  - SEAL_CLEARS rows on LIVE name head H, and the sealed paths H changes are exactly those rows,
    each blob's full sha256 equal to its row; the train's own files are untouched;
  - the patch is byte-identical to `git format-patch` of H.

LIVE here is this clone's `origin/<LIVE>` ref. With no such ref a carrier cannot be judged, and
an unjudged carrier is refused (BREACH), never passed.

A CARRIER NEVER MERGES. Under CI (CI=true), whose run gates every merge into LIVE, any carrier in
the tree is a BREACH whatever its contents: the carrier PR stays red, the sign train opens the
signed head's own PR and closes the carrier. With no carrier in the tree the fence passes.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from libs.ops.fence_exit import fence_exit  # noqa: E402

SPEC = importlib.util.spec_from_file_location("sign_train", ROOT / "scripts" / "sign_train.py")
assert SPEC and SPEC.loader
sign_train = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sign_train)

LIVE = "claude/llm-auto-upgrade-verify-gcjac3"


def _live_ref(root: Path) -> str | None:
    r = subprocess.run(
        ("git", "rev-parse", "--verify", "-q", f"refs/remotes/origin/{LIVE}^{{commit}}"),
        cwd=root, capture_output=True, text=True, check=False,
    )  # fmt: skip
    return r.stdout.strip() if r.returncode == 0 and r.stdout.strip() else None


def judge(root: Path = ROOT, ci: bool | None = None) -> dict[str, object]:
    folder = root / sign_train.CARRIERS
    names = sorted(p.name for p in folder.iterdir()) if folder.is_dir() else []
    if not names:
        return {"verdict": "PASS", "carriers": 0, "why": "no seal carrier in the tree"}
    if ci if ci is not None else os.environ.get("CI") == "true":
        return {
            "verdict": "BREACH",
            "carriers": len(names),
            "why": f"{sign_train.CARRIERS} is in the tree: a seal carrier never merges",
        }
    heads, problems = sign_train.carrier_heads(names)
    live = _live_ref(root)
    if live is None:
        problems.append(f"no origin/{LIVE} ref in this clone: the carrier cannot be judged")
    else:
        try:
            clears = subprocess.run(
                ("git", "show", f"{live}:{sign_train.SEAL_CLEARS}"),
                cwd=root, capture_output=True, text=True, check=True,
            ).stdout  # fmt: skip
        except subprocess.CalledProcessError:
            clears = ""
        for h in heads:
            bad = sign_train.carrier_problems(
                root,
                (folder / f"{h}.bundle").read_bytes(),
                (folder / f"{h}.patch").read_bytes(),
                h,
                live,
                clears,
            )
            problems += [f"{h[:12]}: {b}" for b in bad]
    return {
        "verdict": "BREACH" if problems else "PASS",
        "carriers": len(heads),
        "why": "; ".join(problems) if problems else f"{len(heads)} carrier(s) hold",
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    doc = judge()
    print(
        json.dumps(doc, indent=1) if a.json else f"seal carriers: {doc['verdict']} -- {doc['why']}"
    )
    return fence_exit(doc["verdict"], {"PASS"}, fail=1)


if __name__ == "__main__":
    sys.exit(main())

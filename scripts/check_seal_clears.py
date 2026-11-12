#!/usr/bin/env python3
"""THE CLEAR RECORD THE AUTO-SIGN TRUSTS MUST BE WELL-FORMED AND ONLY EVER GROW (D-20261027-003).

    python scripts/check_seal_clears.py [--json]

With the principal sign removed, `scripts/sign_train.py` re-signs a sealed judge file only when a
CLEAR row for its exact sha256 sits in `desks/mt5/data/SEAL_CLEARS.jsonl`. The train checks the
record when it runs; this fence checks it on every push and every law-gate hour, so a garbled
row, a dropped HOLD or a rewritten history is named the moment it is committed rather than the
next time someone tries to sign. It calls the train's own parser and append-only check -- one
judgement, two clocks.

VERDICTS. PASS (the record parses and every committed version is kept at HEAD), BREACH (exit 1),
UNMEASURED in a shallow clone, which cannot see the history: a real answer about the host, and
exit 0, as for the other portable fences (L1.28a, L1.43) -- EXCEPT under CI (CI=true), whose
checkout is full by design: there UNMEASURED means the gating run lost its history, and fails.

SEAL CARRIERS (Auditor ruling 2026-11-11 13:12Z), judged here as the record's other half. The
pre-push gate refuses unsigned sealed bytes, so a head H the audit cleared can never sit on a
branch for the sign train to find. A carrier branch commits it as data instead:
`desks/mt5/data/seal_carriers/<H>.bundle` (a git bundle whose one tip is H) and `<H>.patch`
(`git format-patch` of H). Every carrier in the tree is judged with the train's own check
(scripts/sign_train.py `carrier_problems`): exactly one tip H whose one parent is an ancestor of
this clone's origin/<LIVE>; SEAL_CLEARS rows on LIVE naming head H; the sealed paths H changes
exactly those rows, blob sha256 equal; the train's own files untouched; the patch byte-identical.
No origin/<LIVE> ref means the carrier cannot be judged, and is refused. A CARRIER NEVER MERGES:
under CI (CI=true), which gates every merge into LIVE, any carrier in the tree is a BREACH.
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


def judge() -> dict[str, object]:
    try:
        head = sign_train._git("rev-parse", "HEAD")
        text = sign_train._committed_clears(head)
        cleared = sign_train.parse_clears(text)
    except ValueError as exc:
        if "shallow clone" in str(exc):
            return {"verdict": "UNMEASURED", "why": str(exc)}
        return {"verdict": "BREACH", "why": str(exc)}
    return {
        "verdict": "PASS",
        "rows": len([ln for ln in text.splitlines() if ln.strip()]),
        "cleared_paths": sorted(cleared),
    }


LIVE = "claude/llm-auto-upgrade-verify-gcjac3"


def _live_ref(root: Path) -> str | None:
    r = subprocess.run(
        ("git", "rev-parse", "--verify", "-q", f"refs/remotes/origin/{LIVE}^{{commit}}"),
        cwd=root, capture_output=True, text=True, check=False,
    )  # fmt: skip
    return r.stdout.strip() if r.returncode == 0 and r.stdout.strip() else None


def judge_carriers(root: Path = ROOT, ci: bool | None = None) -> dict[str, object]:
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
    carriers = judge_carriers()
    print(
        json.dumps({**doc, "carriers": carriers}, indent=1)
        if a.json
        else f"seal clears: {doc['verdict']} -- "
        f"{doc.get('why') or str(doc.get('rows')) + ' row(s)'}; "
        f"seal carriers: {carriers['verdict']} -- {carriers['why']}"
    )
    # Name the passing set (R0237); UNMEASURED passes only off CI, whose checkout is full.
    passing = {"PASS"} if os.environ.get("CI") == "true" else {"PASS", "UNMEASURED"}
    if carriers["verdict"] != "PASS":
        return fence_exit(carriers["verdict"], {"PASS"}, fail=1)
    return fence_exit(doc["verdict"], passing, fail=1)


if __name__ == "__main__":
    sys.exit(main())

"""Record WHICH COMMIT the gates were green on, so a release can cite it.

WHY THIS EXISTS. `release_identity` sealed a `release_sha` and nothing else. Asked what had been
TESTED against that seal it had no answer -- not "null", but no field at all -- so "the box runs
the sealed code" and "the sealed code passed its gates" were two claims with only the first
measured. A seal without an attestation is provenance for the bytes and none for the judgement.

WHAT IT DOES AND DOES NOT CLAIM. It records the HEAD sha at the moment a gate run finished, which
gates ran, and whether they passed. It does NOT claim the working tree equalled that commit: a
gate run over a dirty tree tested something no commit contains, so `tree_clean` is recorded and a
consumer that needs a hard guarantee must require it. Saying so is the point -- an attestation
that overstates itself is worse than none, because it is believed.

    python scripts/gate_attestation.py --gates fast --result pass
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "gate_attestation.json"


def _git(*args: str) -> str:
    """UTF-8 explicitly: `text=True` alone decodes with the locale and dies in a reader thread."""
    r = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=60, check=False)
    return r.stdout.strip() if r.returncode == 0 else ""


#: Paths whose dirtiness says nothing about what CODE was tested. Mirrors
#: `libs/ops/release.py:STATE_PREFIXES`, duplicated so this script runs on a bare checkout.
_STATE_PREFIXES = ("desks/mt5/data/", "desks/mt5/reports/", "desks/mt5/logs/",
                   "data/", "reports/", "logs/", "web/", "docs/")


def _is_state(rel: str) -> bool:
    return any(rel.startswith(pre) for pre in _STATE_PREFIXES)


def attest(gates: str, result: str) -> dict[str, object]:
    sha = _git("rev-parse", "HEAD")
    # CLEAN MEANS CLEAN ON CODE, NOT ON EVERYTHING (fixed 2026-09-14).
    #
    # This counted any dirty path, so `tree_clean` was false on every run of this desk and
    # `tested_sha` was therefore dropped every time -- the release artifact reported UNMEASURED
    # forever while the gates were green on a known commit. The mirror carries thousands of
    # modified state files at all times because the trading box owns them and pushes them up;
    # that is the normal condition here, not a dirty worktree.
    #
    # A modified ledger, report or log cannot change what the interpreter executed. A modified
    # .py can, and still voids the claim. Narrowing the test to code paths is what makes the
    # attestation able to say anything at all, and it gives up nothing it was actually checking.
    # UNTRACKED FILES ARE NOT PART OF ANY COMMIT, so an untracked .ps1 scratch file cannot change
    # what the gates executed on a given sha. An untracked .py can -- it could shadow an import --
    # so that one still voids the claim. The repo root carries a pile of stray scripts from past
    # sessions; treating those as "the tree is dirty" would make this field permanently useless,
    # which is how a check ends up being ignored rather than fixed.
    dirty = []
    for ln in _git("status", "--porcelain").splitlines():
        if not ln.strip():
            continue
        code, rel = ln[:2], ln[3:].strip().strip('"')
        if _is_state(rel):
            continue
        if code.strip() == "??" and not rel.endswith(".py"):
            continue
        dirty.append(ln)
    return {
        "at": datetime.now(UTC).isoformat(timespec="seconds"),
        "tested_sha": sha or None,
        "gates": gates,
        "result": result,
        "tree_clean": not dirty,
        "dirty_paths": len(dirty),
        "note": ("tested_sha is HEAD when the run finished. tree_clean considers CODE paths "
                 "only -- a modified ledger cannot change what the interpreter executed, while a "
                 "modified .py voids the claim and still sets this false"),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--gates", default="fast", help="which gate set ran (fast|full)")
    ap.add_argument("--result", default="pass", choices=("pass", "fail"))
    args = ap.parse_args(argv)
    doc = attest(args.gates, args.result)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1), encoding="utf-8")
    print(f"gate attestation: {args.gates} {args.result} on "
          f"{str(doc['tested_sha'])[:12]} (tree_clean={doc['tree_clean']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())

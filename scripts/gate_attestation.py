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
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "gate_attestation.json"


def _git(*args: str) -> str:
    """UTF-8 explicitly: `text=True` alone decodes with the locale and dies in a reader thread.

    AND ONLY THE TRAILING NEWLINE IS STRIPPED, because `.strip()` ATE A LEADING SPACE AND THAT IS
    WHY `tested_sha` HAS ALWAYS BEEN UNMEASURED.

    `git status --porcelain` emits a TWO-CHARACTER status field, and a worktree-only change has a
    SPACE in the first column: " M desks/mt5/data/compute_ledger.jsonl". Stripping the whole
    output removes that leading space from the FIRST line only, so `ln[3:]` then skips one
    character too many and the path arrives as "esks/mt5/data/compute_ledger.jsonl". `_is_state`
    cannot match a path with its first letter missing, so a STATE file was counted as dirty CODE
    on every run -- `tree_clean` false, `tested_sha` dropped, and the release artifact reporting
    UNMEASURED forever while the gates were green on a known commit.

    One character, in a helper, silently converting "the desk's ledgers moved" into "the code
    under test is unknown". Columns are data here; only the trailing newline may go.
    """
    r = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=60, check=False)
    return r.stdout.rstrip("\n") if r.returncode == 0 else ""


#: Paths whose dirtiness says nothing about what CODE was tested. Mirrors
#: `libs/ops/release.py:STATE_PREFIXES`, duplicated so this script runs on a bare checkout.
_STATE_PREFIXES = ("desks/mt5/data/", "desks/mt5/reports/", "desks/mt5/logs/",
                   "data/", "reports/", "logs/", "web/", "docs/")


def _is_state(rel: str) -> bool:
    return any(rel.startswith(pre) for pre in _STATE_PREFIXES)


def _tracked_py() -> set[str]:
    """Every .py git actually tracks, as posix paths -- the set an untracked file could shadow."""
    return {ln.strip() for ln in _git("ls-files", "*.py").splitlines() if ln.strip()}


def _shadows_a_real_module(rel: str, tracked: set[str]) -> bool:
    """Could this UNTRACKED .py change what an import resolves to?

    THE ORIGINAL RULE WAS SOUND AND TOO BROAD, AND IT COST THE FIELD ENTIRELY. Any untracked .py
    voided `tree_clean`, so `tested_sha` was dropped on every run this desk has ever made -- the
    release reported UNMEASURED forever while the gates were green on a known commit. The repo
    root and desks/mt5 carry two dozen stray diagnostics from past sessions (annual.py, boxid.py,
    clockdiag.py, famcount.py, ...) and none of them is ever imported by anything.

    A .py FILE CHANGES AN IMPORT ONLY BY NAME COLLISION. `import clockdiag` appears nowhere, so
    clockdiag.py cannot alter what the interpreter executed no matter how dirty it makes the
    status output. What CAN alter it is an untracked file whose module name matches a TRACKED
    module reachable on the same path -- that one genuinely shadows, and still voids the claim.

    So the test is the actual property rather than a proxy for it: does this file's importable
    name collide with a tracked module in the same package directory? Deleting the operator's
    scratch files to satisfy a proxy would have been the wrong fix, and weakening the check to
    "ignore all untracked" would have been worse -- it would have given up the guarantee the
    field exists to make.
    """
    p = PurePosixPath(rel)
    stem = p.stem
    if stem in ("__init__", "conftest"):
        return True                       # these change package behaviour wherever they sit
    parent = str(p.parent)
    for t in tracked:
        tp = PurePosixPath(t)
        if tp.suffix != ".py" or str(tp) == rel:
            continue
        # A collision only matters within the same directory -- that is where an import of this
        # name would resolve to the untracked file instead of the tracked one.
        if tp.stem == stem and str(tp.parent) == parent:
            return True
    return False


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
        if code.strip() == "??":
            # An untracked file is in no commit. It can only change what the gates executed by
            # SHADOWING a tracked module of the same name in the same package -- see
            # `_shadows_a_real_module`. Anything else is a scratch file nothing imports.
            if not rel.endswith(".py"):
                continue
            if not _shadows_a_real_module(rel, _tracked_py()):
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

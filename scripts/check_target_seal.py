#!/usr/bin/env python3
"""Is a COMMIT's judge sealed? The adopter asks this before it lands a tree on the trading box.

`check_immutable_evaluator.py` answers for the working tree: it hashes the frozen judge files on
disk against `IMMUTABLE_MANIFEST.json`. The adopter needs the same answer about a commit it has
only FETCHED, before a single byte of it reaches the tree the gateway runs. Measured 2026-09-30:
origin carried a broken seal for about two minutes (4678fe4f at 515d665e, until fc6c34e5
re-signed it), and MT5-AdoptRelease checks neither CI nor the seal -- an adoption at :12 inside
that window would have landed an unsigned judge on the box that trades.

    python scripts/check_target_seal.py <rev>          # rc 0 sealed, 1 breach, 2 unmeasurable

Only the frozen FILES are judged. The record wall (ledgers, forward clocks, cost surface) is the
box's own state and is not in a fetched commit's gift, so it stays with the working-tree fence.

The frozen list is the UNION of the one this checkout declares and the one the target declares,
so a target cannot leave the fence by deleting a name from the list in the same commit that
edits the file. Hashes are over CRLF->LF normalised bytes, exactly as the evaluator signs them.
"""
from __future__ import annotations

import ast
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVALUATOR = "scripts/check_immutable_evaluator.py"
MANIFEST = "desks/mt5/data/IMMUTABLE_MANIFEST.json"


def _show(rev: str, rel: str) -> bytes | None:
    r = subprocess.run(["git", "-C", str(ROOT), "show", f"{rev}:{rel}"],
                       capture_output=True, timeout=120, check=False)
    return r.stdout if r.returncode == 0 else None


def immutable_list(source: bytes | str) -> tuple[str, ...]:
    """The `IMMUTABLE` tuple a copy of the evaluator declares, read without importing it."""
    tree = ast.parse(source)
    for node in tree.body:
        targets: list[ast.expr] = []
        value_node: ast.expr | None = None
        if isinstance(node, ast.Assign):
            targets, value_node = list(node.targets), node.value
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            targets, value_node = [node.target], node.value
        if value_node is not None and any(isinstance(t, ast.Name) and t.id == "IMMUTABLE"
                                          for t in targets):
            return tuple(str(v) for v in ast.literal_eval(value_node))
    return ()


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()[:16]


def judge(rev: str) -> tuple[int, list[str]]:
    """(rc, reasons): 0 sealed, 1 a frozen file differs from the signed manifest, 2 unmeasurable."""
    here = ROOT / EVALUATOR
    names: set[str] = set()
    if here.exists():
        names.update(immutable_list(here.read_bytes()))
    theirs = _show(rev, EVALUATOR)
    if theirs is None:
        return 2, [f"{EVALUATOR} is unreadable at {rev[:12]}"]
    names.update(immutable_list(theirs))
    if not names:
        return 2, ["no IMMUTABLE list could be read from either copy of the evaluator"]
    blob = _show(rev, MANIFEST)
    if blob is None:
        return 2, [f"{MANIFEST} is unreadable at {rev[:12]}"]
    try:
        signed = json.loads(blob.decode("utf-8")).get("files") or {}
    except (ValueError, UnicodeDecodeError, AttributeError):
        return 2, [f"{MANIFEST} at {rev[:12]} is not a readable manifest"]
    out: list[str] = []
    for rel in sorted(names):
        raw = _show(rev, rel)
        now = "<absent>" if raw is None else digest(raw)
        if rel not in signed:
            out.append(f"{rel}: frozen but not in the signed manifest")
        elif signed[rel] != now:
            out.append(f"{rel}: changed since signing ({signed[rel]} -> {now})")
    return (1 if out else 0), out


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print("usage: check_target_seal.py <rev>", file=sys.stderr)
        return 2
    rev = argv[0]
    rc, reasons = judge(rev)
    verdict = {0: "SEALED", 1: "BREACH", 2: "UNMEASURED"}[rc]
    print(f"target seal {rev[:12]}: {verdict}")
    for why in reasons:
        print(f"  {why}")
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

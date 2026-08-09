#!/usr/bin/env python3
"""A DUPLICATE LAW KEY IN _MAP LOSES A LAW SILENTLY, AND THE MATRIX STILL REPORTS 0 ORPHANS.

Desk lesson L0069, paid for 2026-08-05. Two sessions numbered a new law L1.54 concurrently --
one on `origin/claude/wonderful-darwin-7uiobi`, one locally -- and the merge produced a dict
literal in `build_enforcement_matrix._MAP` with the same key twice. Python keeps the LAST literal
and discards the first without a word, so one law's fence list vanished while the matrix went on
reporting zero orphans: the law looked enforced, by a mapping that no longer mentioned it.

WHY A TEST AND NOT A CODE FIX. There is nothing to fix in the current file -- the duplicate was
resolved by hand and `_MAP` is clean today. What was missing is anything that would NOTICE the
next one, and the next one arrives the same way this one did: two agents picking the same L1.x
number against different branch tips. A dict literal cannot express "these keys must be unique",
so the check has to read the SOURCE, not the built dict -- by the time Python has parsed it the
evidence is gone. That is the whole point: `len(_MAP)` can never reveal this.
"""
from __future__ import annotations

import ast
import sys
from collections import Counter
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

_SRC = _ROOT / "scripts/build_enforcement_matrix.py"


def _literal_keys() -> list[str]:
    """Keys as WRITTEN in the _MAP dict literal, duplicates included.

    Read from the AST, because the parsed dict has already collapsed them.
    """
    tree = ast.parse(_SRC.read_text("utf-8"))
    for node in ast.walk(tree):
        targets = (node.targets if isinstance(node, ast.Assign) else
                   [node.target] if isinstance(node, ast.AnnAssign) else [])
        for t in targets:
            if isinstance(t, ast.Name) and t.id == "_MAP" and isinstance(node.value, ast.Dict):
                return [k.value for k in node.value.keys
                        if isinstance(k, ast.Constant) and isinstance(k.value, str)]
    raise AssertionError("_MAP dict literal not found in scripts/build_enforcement_matrix.py")


def test_map_has_no_duplicate_law_keys() -> None:
    """The second literal silently wins and the first law's fences are lost."""
    dupes = [k for k, n in Counter(_literal_keys()).items() if n > 1]
    assert not dupes, (
        f"duplicate law id(s) in _MAP: {dupes}. Python keeps only the last literal, so the "
        f"earlier entry's fence list is discarded silently and the enforcement matrix still "
        f"reports 0 orphans -- the law reads ENFORCED by a mapping that no longer names it. "
        f"This is how a concurrently-numbered law disappears (desk lesson L0069).")


def test_map_is_not_empty() -> None:
    """Guards the guard: an AST walk that silently found nothing would pass the test above."""
    assert len(_literal_keys()) > 20, "refusing to certify _MAP from a suspiciously small parse"

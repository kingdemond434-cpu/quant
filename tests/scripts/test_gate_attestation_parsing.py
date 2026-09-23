"""`tested_sha` was UNMEASURED forever because a helper stripped a leading space.

`git status --porcelain` emits a TWO-CHARACTER status field, and a worktree-only change puts a
SPACE in the first column:

    " M desks/mt5/data/compute_ledger.jsonl"

`_git()` returned `r.stdout.strip()`, which removes that leading space from the FIRST line only.
`ln[3:]` then skips one character too many and the path arrives as
"esks/mt5/data/compute_ledger.jsonl". `_is_state` cannot match a path missing its first letter, so
a STATE file was counted as dirty CODE on every run -- `tree_clean` false, `tested_sha` dropped,
and the release artifact reporting UNMEASURED while the gates were green on a known commit.

One character, in a helper, silently converting "the desk's ledgers moved" into "the code under
test is unknown".
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

ga = pytest.importorskip("gate_attestation")


def test_the_status_columns_survive(monkeypatch):
    """A worktree-only change starts with a space. Losing it shifts every path by one."""
    raw = " M desks/mt5/data/compute_ledger.jsonl\n"
    monkeypatch.setattr(ga, "_git", lambda *a: raw.rstrip("\n"))
    line = ga._git("status", "--porcelain")
    assert line.startswith(" M "), f"leading status column was eaten: {line!r}"
    assert line[3:] == "desks/mt5/data/compute_ledger.jsonl"


def test_a_state_path_is_recognised_after_parsing():
    assert ga._is_state("desks/mt5/data/compute_ledger.jsonl") is True
    # The mis-parsed form is what the bug produced, and it must NOT look like state -- that is
    # exactly why the file was counted as dirty code.
    assert ga._is_state("esks/mt5/data/compute_ledger.jsonl") is False


def test_an_untracked_scratch_script_does_not_void_the_claim():
    """A .py changes an import only by NAME COLLISION. Two dozen stray diagnostics sat in the
    repo and voided tested_sha on every run while being imported by nothing."""
    tracked = {"desks/mt5/research/promoter.py", "scripts/gate_attestation.py"}
    assert ga._shadows_a_real_module("desks/mt5/clockdiag.py", tracked) is False
    assert ga._shadows_a_real_module("boxid.py", tracked) is False


def test_a_real_shadow_still_voids_it():
    """An untracked file that would win an import against a tracked module of the same name."""
    tracked = {"desks/mt5/research/promoter.py"}
    assert ga._shadows_a_real_module("desks/mt5/research/promoter.py", tracked) is False
    assert ga._shadows_a_real_module("desks/mt5/research/__init__.py", tracked) is True


def test_a_modified_tracked_py_always_voids_it(monkeypatch):
    """The guarantee the field exists to make: changed code means the sha was not what ran."""
    monkeypatch.setattr(ga, "_git", lambda *a: (
        "abc123" if a[0] == "rev-parse" else " M desks/mt5/mt5desk/gateway.py"))
    monkeypatch.setattr(ga, "_tracked_py", lambda: {"desks/mt5/mt5desk/gateway.py"})
    doc = ga.attest("fast", "pass")
    assert doc["tree_clean"] is False
    assert doc["dirty_paths"] == 1

"""A comment is not a strategy change, and a strategy change is not a comment.

WHY THIS TEST EXISTS. `code_hash` hashes `inspect.getsource`, which includes the docstring and
every comment, so editing PROSE in families.py marked live clocks IDENTITY_BROKEN -- terminally,
against a code state that then existed nowhere and that `reconcile()` could never see return.
Measured 2026-09-03: 15 of 52 sleeves (29% of the forward book) were frozen on
`code_hash changed after the clock froze`, holding 32b3bc38d228df35 while the VPS and the desk
box both computed 38d9ca40fbd659c6. They accrued nothing for hours while their day counter kept
running, which the same-day fence correctly calls the worst combination: the clock matures on
stale data.

`behaviour_hash` records what the function DOES -- bytecode, constants (minus the docstring),
names -- so prose cannot break a clock and logic still can. These tests pin both halves, because
a hash that ignored too much would be a genuine loosening of the two-stage law.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "research"))

from sleeve_registry import IDENTITY_FIELDS, behaviour_hash, code_hash, identity


def _documented(x: int, k: int = 2) -> int:
    """One docstring."""
    # one comment
    return x * k + 1


def _reworded(x: int, k: int = 2) -> int:
    """A COMPLETELY different docstring, several words longer than the original."""
    # an entirely different comment, longer than the one it replaces
    return x * k + 1


def _relogicked(x: int, k: int = 2) -> int:
    """One docstring."""
    # one comment
    return x * k + 2          # <-- the only change that matters


def test_editing_prose_does_not_change_the_behaviour_hash() -> None:
    assert behaviour_hash(_documented) == behaviour_hash(_reworded), (
        "a docstring and comment edit must not read as a strategy change")


def test_editing_prose_DOES_change_the_source_hash() -> None:
    """The premise of the whole fix: this is why clocks were dying."""
    assert code_hash(_documented) != code_hash(_reworded)


def test_changing_the_logic_changes_the_behaviour_hash() -> None:
    assert behaviour_hash(_documented) != behaviour_hash(_relogicked), (
        "a real logic change MUST still break the clock -- that is the law this protects")


def test_behaviour_hash_is_not_part_of_the_sleeve_id() -> None:
    """Introducing the field must re-bless nothing that was already frozen."""
    assert "behaviour_hash" not in IDENTITY_FIELDS
    a = identity(family="f", symbol="EURUSD", code="c", cost="k", data_venue="v")
    b = identity(family="f", symbol="EURUSD", code="c", cost="k", data_venue="v",
                 behaviour="anything-at-all")
    assert a["sleeve_id"] == b["sleeve_id"]
    assert "behaviour_hash" not in a and b["behaviour_hash"] == "anything-at-all"


def test_a_function_without_bytecode_is_named_not_guessed() -> None:
    """UNMEASURED is a real answer (L1.28a): never emit a hash we did not compute."""
    assert behaviour_hash(len).startswith("nocode:")

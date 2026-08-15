"""The ruin rails, pinned on the failure that made this module necessary.

THE DEFECT THIS GUARDS AGAINST is a freeze that only some order paths honour. `CASHCARRY_KILL` sat
latched on the box while a newly built second order path read only its own arming contract --
keyfile, LIVE_ENABLE, VPS_VERIFIED -- none of which answer "is the book frozen right now". The
preflight printed BLOCKED and the executor would have spent the capital, in the same minute, on the
same machine.

So the tests that matter here are the ones about ABSENCE and UNREADABILITY resolving the wrong way:
a rail file that exists but is empty, or cannot be read, must still freeze. A rail whose reason
cannot be parsed is a rail that FIRED, not a rail that did not.
"""

from __future__ import annotations

from pathlib import Path

from libs.execution.ruin_rail import RAILS, frozen, latched


def test_A_CLEAN_TREE_IS_NOT_FROZEN_AND_SAYS_WHAT_IT_CHECKED(tmp_path: Path) -> None:
    """'No rail latched' and 'no rail consulted' read identically unless the clear answer names
    the files it looked at. Only one of them is evidence."""
    is_frozen, why = frozen(tmp_path)
    assert is_frozen is False
    for rel, _ in RAILS:
        assert rel in why, f"the clear verdict must name {rel} as checked, else it is not evidence"


def test_EVERY_DECLARED_RAIL_FREEZES_ON_ITS_OWN(tmp_path: Path) -> None:
    """Each rail is independently sufficient. A rail that only counts alongside another is not a
    rail, and this is the loop that catches a future entry added to RAILS but never honoured."""
    for rel, _ in RAILS:
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("fired at 2026-08-01", "utf-8")
        is_frozen, why = frozen(tmp_path)
        assert is_frozen is True, f"{rel} present must freeze the book on its own"
        assert rel in why
        p.unlink()


def test_AN_EMPTY_RAIL_FILE_STILL_FREEZES(tmp_path: Path) -> None:
    """PRESENCE is the latch; the contents are only the explanation. `touch CASHCARRY_KILL` is a
    real way a freeze gets set, and treating a blank file as 'no reason, therefore no freeze' would
    invert the whole rail."""
    (tmp_path / "data").mkdir()
    (tmp_path / "data/CASHCARRY_KILL").write_text("", "utf-8")
    is_frozen, why = frozen(tmp_path)
    assert is_frozen is True
    assert "no reason recorded" in why, "a blank reason must render as words, not as `frozen ()`"


def test_AN_UNREADABLE_RAIL_STILL_FREEZES(tmp_path: Path) -> None:
    """A directory where a file is expected makes read_text raise. WS-005 says absence of a
    readable reason must not resolve to the clean verdict."""
    (tmp_path / "data/CASHCARRY_KILL").mkdir(parents=True)
    is_frozen, why = frozen(tmp_path)
    assert is_frozen is True
    assert "the latch still counts" in why


def test_ALL_LATCHED_RAILS_ARE_REPORTED_NOT_JUST_THE_FIRST(tmp_path: Path) -> None:
    """An operator who clears one rail and is refused again by a second, unnamed one has no way to
    find out why. Short-circuiting on the first hit produces exactly that."""
    (tmp_path / "data").mkdir()
    for rel, _ in RAILS:
        (tmp_path / rel).write_text("x", "utf-8")
    hits = latched(tmp_path)
    assert len(hits) == len(RAILS)
    _, why = frozen(tmp_path)
    for rel, _ in RAILS:
        assert rel in why


def test_THE_REASON_IS_BOUNDED(tmp_path: Path) -> None:
    """A rail file somebody pasted a stack trace into must not flood every journal line."""
    (tmp_path / "data").mkdir()
    (tmp_path / "data/FREEZE").write_text("y" * 50_000, "utf-8")
    _, why = frozen(tmp_path)
    assert len(why) < 1_000


def test_NOTHING_IN_THIS_MODULE_CLEARS_A_RAIL(tmp_path: Path) -> None:
    """Clearing a fired rail is a Tier-3 act reserved to the principal. Reading must never be a
    write, and a module that can clear a rail is one autonomous bug away from clearing it."""
    (tmp_path / "data").mkdir()
    p = tmp_path / "data/CASHCARRY_KILL"
    p.write_text("fired", "utf-8")
    for _ in range(3):
        assert frozen(tmp_path)[0] is True
        assert latched(tmp_path)
    assert p.exists() and p.read_text("utf-8") == "fired"

    src = Path("libs/execution/ruin_rail.py").read_text("utf-8")
    for forbidden in ("unlink(", "rmtree", "write_text(", "os.remove", "rename("):
        assert forbidden not in src, (
            f"ruin_rail.py contains {forbidden!r} -- this module reads rails and never mutates "
            "them; clearing a fired rail is the principal's act")

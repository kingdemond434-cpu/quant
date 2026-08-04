"""The disk-headroom module -- the resource whose exhaustion is silent AND irreversible.

Every test here is about the same asymmetry: running out of disk does not cost money, it costs a
permanent hole in the only asset the desk cannot re-buy. So the module's job is to turn a
percentage (a status line) into a date (an action), and to refuse to guess when it cannot.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from libs.ops.disk import PAUSE_FRAC, WARN_DAYS, days_to_pause, headroom, tape_bytes, usage


def test_headroom_is_measured_to_the_pause_line_not_to_a_full_disk() -> None:
    """The recorders stop at 80%, so free space overstates what the tape may actually have. A
    guard computed against 100% would report headroom that does not exist."""
    h = headroom("/")
    assert h["pause_at_bytes"] < h["total_bytes"]
    assert h["pause_at_bytes"] == int(h["total_bytes"] * PAUSE_FRAC)
    assert h["headroom_bytes"] <= h["free_bytes"] or h["paused"]


#: A pause threshold no real filesystem can be over, so these tests exercise the branch they
#: name rather than whichever branch the HOST's fill level happens to select. Every test below
#: used to read the machine's real disk: on a roomy dev box they took the intended path, and on a
#: GitHub runner -- whose image fills most of the root volume -- `days_to_pause` returned PAUSED
#: and one of them failed while two others silently returned early and asserted NOTHING. A test
#: that quietly no-ops on a full disk is worse than one that fails: it reports success for work
#: it did not do. The PAUSED branch is pinned deliberately in its own test.
_NEVER_PAUSED = 1.01


def test_an_unmeasured_growth_rate_is_UNKNOWN_never_a_comfortable_number() -> None:
    """Inventing 'never' from a rate nobody measured is how a two-week problem gets filed as a
    non-problem."""
    d = days_to_pause(0.0, pause_frac=_NEVER_PAUSED)
    assert d["state"] == "UNKNOWN" and d["days"] is None
    assert "cannot be acted on" in d["note"]


def test_a_fast_growth_rate_produces_a_date_and_escalates() -> None:
    """A percentage is a status line; a date is an action. This is the whole point of the module."""
    h = headroom("/", _NEVER_PAUSED)
    per_day = max(1.0, h["headroom_bytes"] / 3.0)      # three days of headroom by construction
    d = days_to_pause(per_day, pause_frac=_NEVER_PAUSED)
    assert d["state"] == "URGENT"
    assert 0 < d["days"] < WARN_DAYS
    assert "Deleting mined tape is NOT an option" in d["note"]


def test_the_urgent_note_refuses_deletion_as_a_remedy() -> None:
    """P20: the seven reconstructions are the FIRST seven, not the last. Deleting mined tape
    assumes today's mechanisms are the final ones, and it destroys ground that cannot be re-bought
    at any price. The guidance has to say so where somebody under pressure will read it."""
    h = headroom("/", _NEVER_PAUSED)
    d = days_to_pause(max(1.0, h["headroom_bytes"] / 2.0), pause_frac=_NEVER_PAUSED)
    assert "re-readable" in d["note"] and "Buy storage" in d["note"]


def test_a_paused_disk_says_the_coverage_number_has_stopped_meaning_anything() -> None:
    """The failure mode this module exists for: a frozen denominator makes coverage rise on its
    own, so the paused verdict must name that explicitly rather than just reporting fullness."""
    d = days_to_pause(1e9, pause_frac=0.0)             # forces the paused branch deterministically
    # (the complement of _NEVER_PAUSED above: between them the two branches are pinned to the
    # code under test rather than to how full the machine running the suite happens to be)
    assert d["state"] == "PAUSED" and d["days"] == 0.0
    assert "frozen denominator" in d["note"]


def test_tape_bytes_on_an_absent_root_is_zero_not_an_error(tmp_path) -> None:
    """A fresh checkout has no data/moat. Zero is the correct measurement; raising would take the
    miner down on the machine where it has the least to do."""
    assert tape_bytes(tmp_path / "nope") == (0, 0)


def test_tape_bytes_counts_what_is_actually_on_disk(tmp_path) -> None:
    """Measured directly rather than trusted from a counter -- a counter that stops being updated
    looks exactly like a tape that stopped growing, which is the case it must distinguish."""
    (tmp_path / "fut" / "BTCUSDT").mkdir(parents=True)
    (tmp_path / "fut" / "BTCUSDT" / "a.jsonl.gz").write_bytes(b"x" * 500)
    (tmp_path / "fut" / "BTCUSDT" / "b.jsonl.gz").write_bytes(b"y" * 300)
    assert tape_bytes(tmp_path) == (800, 2)


def test_usage_fractions_are_coherent() -> None:
    u = usage("/")
    assert 0.0 <= u["used_frac"] <= 1.0
    assert u["used_bytes"] + u["free_bytes"] <= u["total_bytes"]


def test_headroom_never_exceeds_what_the_filesystem_can_actually_write() -> None:
    """CAUGHT BY THIS TEST, NOT BY REVIEW. used + free does not equal total on real filesystems --
    reserved blocks, overlay layers and journal space live in the gap -- so `limit - used`
    overstates writable bytes. The unclamped version promised headroom that does not exist, which
    would let the tape hit ENOSPC BEFORE the 80% guard fired: a silent stop, which is the entire
    failure this module was written to prevent."""
    h = headroom("/")
    assert h["headroom_bytes"] <= h["free_bytes"]


def test_zero_free_bytes_counts_as_paused_even_below_the_percentage_bar() -> None:
    """A filesystem with no writable bytes IS stopped, whatever the percentage says. Deciding on
    the ratio alone would report healthy while every write failed."""
    import libs.ops.disk as D
    real = D.usage
    try:
        D.usage = lambda path="/": {"total_bytes": 1000, "used_bytes": 100,
                                    "free_bytes": 0, "used_frac": 0.1}
        assert D.headroom("/")["paused"] is True
    finally:
        D.usage = real

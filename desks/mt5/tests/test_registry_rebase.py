"""AN UNREADABLE REGISTRY MUST NEVER READ AS AN EMPTY ONE (regression, 2026-08-27).

THE ORIGINAL FAILURE, from the committed history of `desks/mt5/data/sleeve_registry.json`:

    08-26 02:02  n=15  every row frozen_at 2026-08-26T01:42
    08-26 08:50  n=15  every row frozen_at 2026-08-26T08:49
    08-27 02:10  n=15  every row frozen_at 2026-08-27T01:13
    08-27 09:25  n=17  every row frozen_at 2026-08-27T03:31-03:34

Three complete re-bases of the desk's entire forward book in 32 hours, none of them archived
anywhere -- against a promotion law (L1.58) that requires `days >= 14`. No forward clock had ever
survived a single day, so the desk could not promote anything to live capital, and
`live_readiness.json` reported the cause as "the market has not yet supplied the unseen
observations": a desk defect attributed to the world.

THE MECHANISM. `_read()` returned `{}` for BOTH "no registry yet" and "registry unreadable".
`freeze()` reads that `{}`, finds no row for the key, and takes its create branch -- minting
`frozen_at = now` and a fresh `forward_start`, then writing a registry containing only the rows
frozen in that pass. One failed read therefore re-based every clock. The read fails for entirely
ordinary reasons: the authoritative copy lives on the Windows trading box while
`ops/pull_desk_state.sh` scp's this exact path every ~2 minutes and `freeze()` wrote it
non-atomically, so a concurrent reader saw a truncated file (ValueError) or an open handle
(PermissionError -- an OSError). Both were swallowed into a clean empty verdict: WS-005.

These tests fail on the pre-fix module in the one direction that matters -- a corrupt registry
silently re-basing a live clock -- and pin the two properties that close it: unreadable raises,
and writes are atomic so the corrupt state is not generated in the first place.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE / "research"))

import sleeve_registry as R  # noqa: E402

IDENT = R.identity(family="session_range_breakout", symbol="XAUUSD", selector="asia",
                   params={"rr": 2.0}, code="c0de", cost="c057",
                   data_venue="MT5:FusionMarkets-Live")
EARLY = "2026-08-13T00:00:00+00:00"


def _isolate(tmp_path, monkeypatch) -> Path:
    """Point the module at a scratch registry. The real path resolves from `__file__`, so a
    `cwd` change does NOT redirect it and a careless test would re-base the live book."""
    reg = tmp_path / "sleeve_registry.json"
    monkeypatch.setattr(R, "REGISTRY", reg)
    return reg


@pytest.mark.parametrize(
    ("corruption", "why"),
    [("{\"sleeves\": {\"XAUUSD.asia\": {\"identity\": {\"fam", "truncated mid-write by a "
      "concurrent reader -- what a non-atomic write exposes"),
     ("[]", "parsed but not an object -- a wrong shape is not an empty book"),
     ("", "zero bytes -- the state a truncate-then-write leaves for as long as the write takes")],
)
def test_a_corrupt_registry_never_re_bases_a_live_clock(tmp_path, monkeypatch, corruption, why):
    """THE REGRESSION. A live 14-day-old clock, a corrupt read, and `freeze()` called again.

    Pre-fix this returned normally and left a registry holding ONE row stamped `frozen_at = now`
    -- the whole forward book gone, silently. Post-fix it raises and the bytes on disk are
    untouched, so the corruption stays diagnosable instead of being overwritten by its own damage.
    """
    reg = _isolate(tmp_path, monkeypatch)
    R.freeze("XAUUSD.asia", IDENT, forward_start=EARLY)
    assert json.loads(reg.read_text())["sleeves"]["XAUUSD.asia"]["forward_start"] == EARLY

    reg.write_text(corruption, "utf-8")
    with pytest.raises(R.RegistryUnreadable):
        R.freeze("XAUUSD.asia", IDENT, forward_start="2026-08-27T03:34:49+00:00")

    assert reg.read_text("utf-8") == corruption, (
        f"an unreadable registry ({why}) must not be overwritten -- overwriting it is exactly "
        f"how the forward book was re-based, and it destroys the evidence of the corruption too")


def test_a_corrupt_registry_also_blocks_mark(tmp_path, monkeypatch):
    """`mark()` reads-modifies-writes the same file, so it re-bases the book by the same route.

    Worse than `freeze()`: on `{}` it writes a registry whose single row has no `identity` at all,
    so every sleeve loses its frozen identity as well as its clock.
    """
    reg = _isolate(tmp_path, monkeypatch)
    R.freeze("XAUUSD.asia", IDENT, forward_start=EARLY)
    reg.write_text("{not json", "utf-8")

    with pytest.raises(R.RegistryUnreadable):
        R.mark("XAUUSD.asia", "IDENTITY_BROKEN", "cost_hash changed")
    assert reg.read_text("utf-8") == "{not json"


def test_a_missing_registry_is_still_legitimately_empty(tmp_path, monkeypatch):
    """The one case that MUST stay a clean `{}`: a desk that has never frozen anything.

    Absence and unreadability are different answers; this pins that the fix distinguishes them
    rather than simply refusing to ever create a registry.
    """
    reg = _isolate(tmp_path, monkeypatch)
    assert not reg.exists()

    R.freeze("XAUUSD.asia", IDENT, forward_start=EARLY)
    assert json.loads(reg.read_text())["sleeves"]["XAUUSD.asia"]["forward_start"] == EARLY


def test_every_write_is_atomic_and_leaves_no_temp_behind(tmp_path, monkeypatch):
    """Removes the CAUSE, not only the response to it.

    A reader can only observe a truncated registry if a writer truncates in place. After each of
    the three writing paths (create, backfill, mark) the directory must hold exactly the registry
    -- no leftover scratch file, and every intermediate state a reader could catch is valid JSON
    because `os.replace` is atomic.
    """
    reg = _isolate(tmp_path, monkeypatch)

    R.freeze("XAUUSD.asia", IDENT, forward_start=None)     # create, clock unstamped
    R.freeze("XAUUSD.asia", IDENT, forward_start=EARLY)    # backfill path
    R.mark("XAUUSD.asia", "LIVE", "still running")         # mark path

    assert sorted(p.name for p in tmp_path.iterdir()) == ["sleeve_registry.json"], (
        "a scratch file left in the registry directory is a second thing readers can trip over")
    assert json.loads(reg.read_text())["sleeves"]["XAUUSD.asia"]["forward_start"] == EARLY

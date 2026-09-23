"""THE FORWARD-CLOCK FENCE, PROVEN BOTH WAYS on the re-base it was built to catch.

A fence that has only ever been observed returning green has not been validated -- only its
silence has. These tests replay the ACTUAL event from the committed history of
`desks/mt5/data/sleeve_registry.json` (all 15 rows frozen 2026-08-26T01:42, then all 15 refrozen
2026-08-27T01:13, with nothing archived anywhere) and assert the fence names it, then pin the
three ways it must NOT fire: an earlier boundary, a recorded restart, and an empty book.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check_forward_clock_ratchet.py"

WIPED = "2026-08-26T01:42:00+00:00"
REBASED = "2026-08-27T01:13:00+00:00"


@pytest.fixture
def fence(tmp_path, monkeypatch):
    """Load the script under test against a scratch desk. It resolves every path from `__file__`,
    so patching the module attributes is the only isolation that works -- a `cwd` change would
    leave it measuring (and re-flooring) the live book."""
    spec = importlib.util.spec_from_file_location("forward_clock_ratchet_under_test", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    shadow = tmp_path / "shadow"
    shadow.mkdir()
    data = tmp_path / "data"
    data.mkdir()
    monkeypatch.setattr(mod, "SHADOW", shadow)
    monkeypatch.setattr(mod, "REGISTRY", data / "sleeve_registry.json")
    monkeypatch.setattr(mod, "RECONCILE", data / "forward_reconcile.json")
    monkeypatch.setattr(mod, "DESK", tmp_path)
    monkeypatch.setattr(mod, "FLOOR", data / "forward_clock_floor.json")
    monkeypatch.setattr(mod, "OUT", data / "forward_clock_ratchet.json")
    mod._shadow, mod._data = shadow, data
    return mod


def _state(mod, **rows) -> None:
    (mod._shadow / "shadow_state.json").write_text(json.dumps({
        key: {"status": "ACTIVE", "n": 8, "forward_start": start} for key, start in rows.items()
    }), "utf-8")


def _report(mod) -> dict:
    return json.loads(mod.OUT.read_text("utf-8"))


def test_it_fires_on_the_real_re_base(fence):
    """THE POSITIVE CONTROL. Day-14 was 9 days away; the wipe put it back to 14 and said nothing."""
    _state(fence, **{"XAUUSD.asia": WIPED, "USDJPY.asia": WIPED})
    assert fence.main() == 0, "first pass establishes the floor; there is nothing to compare yet"

    _state(fence, **{"XAUUSD.asia": REBASED, "USDJPY.asia": REBASED})
    assert fence.main() == 1, "an unexplained later boundary must exit non-zero"

    report = _report(fence)
    assert report["status"] == "BREACH"
    keys = {row["key"] for row in report["silent_rebases"]}
    assert keys == {"XAUUSD.asia", "USDJPY.asia"}
    assert report["silent_rebases"][0]["forward_days_destroyed"] == pytest.approx(0.98, abs=0.01)


def test_a_breach_is_not_laundered_into_the_new_floor(fence):
    """The floor must keep the EARLIEST boundary through a breach.

    Absorbing the re-based stamp would make the second run green -- the defect would announce
    itself once and then become the new normal, which is how a ratchet stops ratcheting (L1.50).
    """
    _state(fence, **{"XAUUSD.asia": WIPED})
    fence.main()
    _state(fence, **{"XAUUSD.asia": REBASED})
    assert fence.main() == 1
    assert fence.main() == 1, "the breach must still be visible on the next run"
    floor = json.loads(fence.FLOOR.read_text("utf-8"))
    assert floor["earliest_forward_start"]["XAUUSD.asia"].startswith("2026-08-26")


def test_an_earlier_boundary_is_never_a_breach(fence):
    """`freeze()`'s backfill can only move a boundary earlier, and that cannot buy an unserved
    window -- so it must not be reported as one."""
    _state(fence, **{"XAUUSD.asia": REBASED})
    fence.main()
    _state(fence, **{"XAUUSD.asia": WIPED})
    assert fence.main() == 0
    assert _report(fence)["silent_rebases"] == []


def test_a_recorded_restart_is_reported_but_allowed(fence):
    """The distinction the fence exists to draw: a restart somebody WROTE DOWN is legitimate, and
    is still surfaced with the window it discarded so the cost is never invisible."""
    _state(fence, **{"XAUUSD.asia": WIPED})
    fence.main()
    fence.RECONCILE.write_text(json.dumps({
        "checked_at": "2026-08-27T01:00:00+00:00",
        "actions": [{"key": "XAUUSD.asia", "action": "REVIVED_CERTIFIED", "why": "certified"}],
    }), "utf-8")
    _state(fence, **{"XAUUSD.asia": REBASED})

    assert fence.main() == 0
    report = _report(fence)
    assert report["silent_rebases"] == []
    assert report["recorded_restarts"][0]["key"] == "XAUUSD.asia"
    assert report["recorded_restarts"][0]["window_days_restarted"] > 0


def test_no_clocks_is_UNMEASURED_and_never_a_pass(fence):
    """A total wipe leaves exactly this shape. Reporting it as "no regressions" is the WS-005
    failure the fence exists to prevent, so absence gets its own status and its own exit code."""
    assert fence.main() == 2
    assert _report(fence)["status"] == "UNMEASURED"


def test_terminal_clocks_are_not_measured(fence):
    """A retired clock's boundary is frozen by design; holding it to the ratchet would report a
    breach every time a sleeve is legitimately retired and drown the real signal."""
    (fence._shadow / "shadow_state.json").write_text(json.dumps({
        "XAUUSD.london_am": {"status": "RETIRED_ORPHAN", "n": 8, "forward_start": WIPED},
    }), "utf-8")
    assert fence.main() == 2, "a book of only-retired clocks is UNMEASURED, not OK"


def test_a_retired_pass_does_not_release_the_floor(fence):
    """THE LAUNDERING ROUTE, replayed. USDJPY.asia's floor moved 11.6h LATER on 2026-08-30 and
    the fence reported OK, because the row read `RETIRED_ORPHAN` on an intervening pass.

    `RETIRED_ORPHAN` is terminal, so that pass measured no clock for the key -- and the floor was
    rebuilt from the measured clocks alone, which DELETED the key. `forward_reconcile` revives
    orphan rows routinely, and the revived row arrived with `prior is None`, so its boundary was
    re-minted at the new stamp and the re-base was invisible. Three passes are the minimum that
    can show it: establish, disappear, come back later. The middle pass is the entire defect."""
    _state(fence, **{"USDJPY.asia": WIPED, "GBPJPY.asia": WIPED})
    assert fence.main() == 0, "pass 1 establishes the floor"
    floor = json.loads(fence.FLOOR.read_text("utf-8"))["earliest_forward_start"]
    assert floor["USDJPY.asia"] == WIPED

    # GBPJPY stays live through the middle pass ON PURPOSE. With every row retired the book is
    # UNMEASURED and returns before rewriting the floor, so the bug cannot show -- and the live
    # desk is never in that shape. One surviving clock is what makes the pass write.
    (fence._shadow / "shadow_state.json").write_text(json.dumps({
        "USDJPY.asia": {"status": "RETIRED_ORPHAN", "n": 8, "forward_start": WIPED},
        "GBPJPY.asia": {"status": "ACTIVE", "n": 8, "forward_start": WIPED},
    }), "utf-8")
    assert fence.main() == 0, "the surviving clock is fine; the retired one is simply unmeasured"
    floor = json.loads(fence.FLOOR.read_text("utf-8"))["earliest_forward_start"]
    assert floor.get("USDJPY.asia") == WIPED, (
        "the floor was RELEASED by a pass that merely could not see the key -- the next revival "
        "re-mints the boundary and the re-base becomes undetectable")

    _state(fence, **{"USDJPY.asia": REBASED, "GBPJPY.asia": WIPED})
    assert fence.main() == 1, ("the revived row's later boundary is a silent re-base, "
                               "not a new floor")
    report = _report(fence)
    assert report["status"] == "BREACH"
    assert [row["key"] for row in report["silent_rebases"]] == ["USDJPY.asia"]


def test_the_floor_is_monotone_in_key_count(fence):
    """The floor may never shrink. Measured on the live artifact, it oscillated 37 -> 19 -> 37
    keys within hours; a set that can shrink cannot carry a ratchet, whatever it holds."""
    _state(fence, **{"XAUUSD.asia": WIPED, "USDJPY.asia": WIPED, "GBPJPY.asia": WIPED})
    fence.main()
    first = set(json.loads(fence.FLOOR.read_text("utf-8"))["earliest_forward_start"])

    _state(fence, **{"XAUUSD.asia": WIPED})           # the other two simply were not reached
    fence.main()
    second = set(json.loads(fence.FLOOR.read_text("utf-8"))["earliest_forward_start"])
    assert first <= second, f"the floor forgot {sorted(first - second)}"

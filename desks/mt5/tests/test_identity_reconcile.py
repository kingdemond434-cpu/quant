"""A clock stopped by an infrastructure transient stayed dead against code that no longer exists.

MEASURED 2026-08-28. Six clocks (CADJPY.asia x3, EURJPY.asia x3) carried
`status_why: code_hash changed after the clock froze`, stamped 2026-08-27T15:31:54. All twelve
`session_range_breakout` clocks had frozen the SAME `code_hash` -- one family, one function, one
source -- so it is arithmetically impossible for six to have drifted while six did not in any one
pass. The desk sync had pushed a stale `families.py` (kept at
`data/sync_refused/20260827T113220/`) whose only difference from the live file was a 20-line
DOCSTRING; the pass that ran under it marked rows in registry order and died before reaching the
rest. The file was restored, every one of the seventeen rows recomputed to exactly the hash it
had frozen -- and `check_live_readiness` still blocked rung 0 on "6 sleeve(s) drifted after
freezing", because `mark()` is write-once and nothing had ever cleared IDENTITY_BROKEN.

These pin the four properties that make resumption a repair rather than a laundering step:
  1. an intact identity RESUMES, keeping its original `forward_start` -- the window is not reset;
  2. a still-drifted identity does NOT resume, on any field;
  3. a clock with real order authority NEVER resumes -- its fills are historical facts of
     whatever code produced them and cannot be recomputed away;
  4. the frozen identity itself is never rewritten, so resumption cannot re-base a clock.

Paths are monkeypatched on the module (this desk's `cwd=tmp` lesson): `sleeve_registry` resolves
REGISTRY from `__file__`, so a temporary working directory does NOT redirect it.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
MODULE = ROOT / "desks" / "mt5" / "research" / "sleeve_registry.py"

FROZEN = {
    "family": "session_range_breakout", "symbol": "CADJPY", "direction": "LONG",
    "timeframe": "H1", "selector": "asia", "condition": None,
    "params": {"range_start": 7, "rr": 2.0, "ttl_bars": 12, "wait_bars": 12},
    "code_hash": "32b3bc38d228df35", "cost_hash": "3f42e7c4405da529",
    "data_venue": "MT5:FusionMarkets-Live",
}
BROKEN_ROW = {
    "identity": dict(FROZEN),
    "identity_schema": "venue-2026-08-26",
    "frozen_at": "2026-08-27T03:34:48+00:00",
    "forward_start": "2026-08-27T03:34:48.144018+00:00",
    "status": "IDENTITY_BROKEN",
    "status_why": "code_hash changed after the clock froze",
    "status_at": "2026-08-27T15:31:54+00:00",
}


@pytest.fixture()
def reg(tmp_path: Path):
    """The registry module with REGISTRY pointed at a throwaway file. Live state is unreachable."""
    spec = importlib.util.spec_from_file_location("sleeve_registry_under_test", MODULE)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    module.REGISTRY = tmp_path / "sleeve_registry.json"
    module.REGISTRY.write_text(
        json.dumps({"sleeves": {"CADJPY.asia": dict(BROKEN_ROW)}}, indent=1), encoding="utf-8")
    yield module
    sys.modules.pop(spec.name, None)


def _row(reg) -> dict:
    return json.loads(reg.REGISTRY.read_text(encoding="utf-8"))["sleeves"]["CADJPY.asia"]


def test_intact_identity_resumes_without_resetting_the_window(reg) -> None:
    """The bug: the identity is back, every field matches, and the clock stayed dead anyway."""
    assert "CADJPY.asia" not in reg.live_keys(), "precondition: the clock starts stopped"

    why = reg.reconcile("CADJPY.asia", dict(FROZEN), replayed=True)

    assert why, "an identity that matches on every field must clear the stop"
    row = _row(reg)
    assert row["status"] == "LIVE"
    assert "CADJPY.asia" in reg.live_keys()
    assert row["identity_restore_count"] == 1, "flapping must stay countable, not invisible"
    # THE WINDOW IS NOT RESET. Resumption clears a flag; it never re-bases the clock, or the
    # 14-day forward requirement would restart every time infrastructure hiccuped.
    assert row["forward_start"] == BROKEN_ROW["forward_start"]
    assert row["frozen_at"] == BROKEN_ROW["frozen_at"]
    assert row["identity"] == FROZEN, "the frozen identity is never rewritten by a resume"


@pytest.mark.parametrize("field,value", [
    ("code_hash", "deadbeefdeadbeef"),
    ("cost_hash", "0000000000000000"),
    ("data_venue", "MT5:SomeOtherBroker"),
    ("params", {"range_start": 7, "rr": 3.0, "ttl_bars": 12, "wait_bars": 12}),
    ("symbol", "EURJPY"),
])
def test_a_still_drifted_identity_never_resumes(reg, field: str, value: object) -> None:
    """Drift on ANY identity field keeps the clock terminal -- this is not a loosening."""
    candidate = dict(FROZEN)
    candidate[field] = value

    assert reg.reconcile("CADJPY.asia", candidate, replayed=True) is None
    assert _row(reg)["status"] == "IDENTITY_BROKEN"
    assert "CADJPY.asia" not in reg.live_keys()


def test_a_clock_with_real_fills_is_never_resumed(reg) -> None:
    """Replay is what makes resumption sound. Real fills are facts of the code that made them."""
    assert reg.reconcile("CADJPY.asia", dict(FROZEN), replayed=False) is None
    assert _row(reg)["status"] == "IDENTITY_BROKEN"


def test_a_healthy_clock_is_left_alone(reg) -> None:
    """Only IDENTITY_BROKEN is cleared; no other status is touched, terminal or otherwise."""
    for status in ("LIVE", "RETIRED", "PROMOTED", "KILLED"):
        reg.mark("CADJPY.asia", status, "set by the test")
        assert reg.reconcile("CADJPY.asia", dict(FROZEN), replayed=True) is None
        assert _row(reg)["status"] == status


def test_an_unknown_key_is_not_invented(reg) -> None:
    """`mark()` creates rows on demand; reconcile must never mint a LIVE sleeve from nothing."""
    assert reg.reconcile("NOSUCH.asia", dict(FROZEN), replayed=True) is None
    assert "NOSUCH.asia" not in json.loads(reg.REGISTRY.read_text(encoding="utf-8"))["sleeves"]

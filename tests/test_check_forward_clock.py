"""THE FORWARD-CLOCK CHURN REPORT MUST NOT WRITE, AND MUST NOT BACKDATE.

Until 2026-08-30 this script moved `forward_start` back to the row's first REPLAYED trade and
printed "REPAIRED" for each one -- 46 a night. Three things were wrong at once and each of them
is pinned below.

It backdated. `shadow_forward` replays from SHADOW_START every pass and keeps the pre-registration
trades as HISTORY on purpose; its own comment calls counting them "the precise leakage the
two-stage law exists to stop". L1.58 forbids a backdated forward window unconditionally.

It could not write anyway. `desks/mt5/reports/shadow/*.json` is a replica --
`ops/pull_desk_state.sh` re-copies all four ledgers from the trading box every ~2 minutes -- so a
repair written at
04:53:58 was gone by 04:55:29 and every "REPAIRED" line ever printed was false.

And the transient write poisoned `check_forward_clock_ratchet`, whose floor may only move EARLIER,
so a backdate sampled once is permanent. Three keys still carry exact-hour bar times as their
floor because of it.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check_forward_clock.py"

CLOCK = "2026-08-27T03:34:49.037701+00:00"   # the pre-registration stamp: microseconds, from now()
EARLIER_TRADE = "2026-08-26 09:00:00+00:00"  # a replayed H1 bar 18.6h before it


@pytest.fixture
def fence(tmp_path, monkeypatch):
    """The script resolves every path from `__file__`, so patching its module attributes is the
    only isolation that works -- a `cwd` change would leave it reading the live book."""
    spec = importlib.util.spec_from_file_location("check_forward_clock_under_test", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    shadow = tmp_path / "shadow"
    shadow.mkdir()
    monkeypatch.setattr(mod, "SHADOW", shadow)
    monkeypatch.setattr(mod, "OUT", tmp_path / "forward_clock_health.json")
    mod._shadow = shadow
    return mod


def _write(mod, **rows) -> Path:
    path = mod._shadow / "shadow_state.json"
    path.write_text(json.dumps({"sleeves": rows}, indent=1), "utf-8")
    return path


def _report(mod) -> dict:
    return json.loads(mod.OUT.read_text("utf-8"))


def test_it_never_writes_to_the_ledger(fence):
    """THE REGRESSION. The ledger is a replica; a write here is undone within two minutes and the
    claim that it happened outlives it. Byte-identical before and after is the only proof."""
    path = _write(fence, **{"XAUUSD.asia": {
        "status": "ACTIVE", "n": 3, "forward_start": CLOCK, "first_entry": EARLIER_TRADE}})
    before = path.read_bytes()

    assert fence.main() == 1, "a churned live clock is still a defect and must stay visible"

    assert path.read_bytes() == before, ("the ledger was modified; the repair cannot "
                                        "survive the sync")
    row = json.loads(path.read_text("utf-8"))["sleeves"]["XAUUSD.asia"]
    assert row["forward_start"] == CLOCK, "the pre-registration boundary was backdated (L1.58)"
    assert "forward_start_repaired_at" not in row


def test_the_report_claims_no_repair_authority(fence):
    """A report that lists repairs it did not make is worse than one that lists none."""
    _write(fence, **{"XAUUSD.asia": {
        "status": "ACTIVE", "n": 3, "forward_start": CLOCK, "first_entry": EARLIER_TRADE}})
    fence.main()
    report = _report(fence)
    assert report["repaired"] == []
    assert report["repair_authority"] is False
    assert len(report["churned"]) == 1, "the finding itself must survive; only the false claim goes"


def test_a_terminal_row_is_not_measured(fence):
    """31 of 46 hits were frozen rows whose `first_entry` predates the boundary filter that
    `shadow_forward` now applies. They drowned the 15 real ones."""
    _write(fence, **{"XAUUSD.london_am": {
        "status": "RETIRED_ORPHAN", "n": 8, "forward_start": CLOCK,
        "first_entry": "2026-08-17 16:00:00+00:00"}})
    assert fence.main() == 0, "a book of only-frozen clocks has no live churn to report"
    report = _report(fence)
    assert report["churned"] == []
    assert report["skipped_terminal"] == 1


def test_an_unreadable_ledger_is_unmeasured_never_clean(fence):
    """These files are scp'd in every two minutes, so a torn read is a live possibility. Reading
    it as "no churn found" is how a stopped book reports healthy (L1.28a)."""
    (fence._shadow / "shadow_state.json").write_text("{not json", "utf-8")
    assert fence.main() == 1
    why = _report(fence)["unrepairable"][0]["why"]
    assert "unreadable" in why and "was measured" in why


def test_a_clock_at_or_before_its_first_trade_is_healthy(fence):
    """The normal shape: the boundary is stamped first, the forward trade lands after it."""
    _write(fence, **{"XAUUSD.asia": {
        "status": "ACTIVE", "n": 3, "forward_start": CLOCK,
        "first_entry": "2026-08-27 06:00:00+00:00"}})
    assert fence.main() == 0
    assert _report(fence)["healthy"] == 1

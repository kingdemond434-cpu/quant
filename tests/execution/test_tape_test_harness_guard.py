"""The live moat tape must be unreachable from a test harness.

FOUND 2026-08-13. `tests/execution/test_carry_entry_gate.py` drives `run_trade_forensics.main()`,
which calls `execution_tape.backfill(trades)` with no `path=`. The test carefully monkeypatches the
forensics module's `_TRADES`/`_OUT`/`_TRACKED`/`_COST_MODEL`, but the tape's default target lives in
a DIFFERENT module, so nothing redirected it: 16 fixture rows reached the append-only tape. Because
the fixture stamps `opened` as `now - 1 day`, `_key()` differed on every run and dedupe could never
collapse them -- every CI run added two more, permanently.

The cost was not cosmetic. One fixture carries `closed: 2020-01-01`, so `coverage()["days"]` -- the
number Gate 0's ">=4 weeks of live fills" is measured against (`libs/risk/capital_events.py:12`) --
read 2415.15 days against a true 30.69, and `web/trade_forensics.json` published `tape_days:
2415.14`. The desk advertised 6.6 years of fill history it did not have.

These tests pin the GENERALISED rule rather than the one offending caller: patching that test would
fix one site and leave the next test author the same invisible trap.
"""
from __future__ import annotations

import importlib.util
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from libs.execution import execution_tape

_ROOT = Path(__file__).resolve().parents[2]


def _rec(sym: str = "BTCUSDT") -> dict:
    return {"event": "open", "symbol": sym, "opened": "2026-07-02T05:18:33+00:00",
            "notional": 100.0}


def test_append_to_the_live_default_raises_under_pytest():
    """No path= means the live tape, and that is refused here -- loudly, so it cannot pass green."""
    with pytest.raises(RuntimeError, match="refusing to write the LIVE moat tape"):
        execution_tape.append(_rec())


def test_backfill_to_the_live_default_raises_under_pytest():
    """`backfill` is the path the real leak took; `append` alone would not have caught it."""
    with pytest.raises(RuntimeError, match="refusing to write the LIVE moat tape"):
        execution_tape.backfill([_rec()])


def test_an_explicit_path_is_still_allowed(tmp_path, monkeypatch):
    """The guard must not cost the suite its ability to test the tape itself."""
    monkeypatch.setattr(execution_tape, "_DISK_MAX_FRAC", 1.01)
    p = tmp_path / "tape.jsonl"
    assert execution_tape.append(_rec(), path=p) is True
    assert execution_tape.backfill([_rec("ETHUSDT")], path=p) == 1
    assert len(execution_tape.read(path=p)) == 2


def test_the_guard_is_off_outside_a_test_harness(tmp_path, monkeypatch):
    """Production must be untouched: with no pytest marker present the default resolves normally.

    Asserts the RESOLVED TARGET rather than performing a write, because a write here would be the
    very contamination under test.
    """
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.setattr(execution_tape.sys, "modules",
                        {k: v for k, v in execution_tape.sys.modules.items() if k != "pytest"})
    assert execution_tape._writable(None) == execution_tape._TAPE


def test_driving_forensics_leaves_the_live_tape_untouched(tmp_path, monkeypatch):
    """The end-to-end regression: this is exactly what contaminated the tape, and it must not.

    Fails without the guard (16 rows landed this way), passes with it. The live tape is compared
    byte-for-byte, because a single appended line is permanent.
    """
    spec = importlib.util.spec_from_file_location(
        "forensics_guard_probe", _ROOT / "scripts/run_trade_forensics.py")
    assert spec and spec.loader
    forensics = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(forensics)

    live = _ROOT / "data/moat/execution_tape/cashcarry_trades.jsonl"
    before = live.read_bytes() if live.exists() else None

    recent = (datetime.now(tz=UTC) - timedelta(days=1)).isoformat()
    trades = [{"event": "open", "symbol": "THINUSDT", "opened": recent,
               "funding_rate": 3.0e-05, "notional": 47.36}]
    for attr, name in (("_TRADES", "t.json"), ("_OUT", "out.json"), ("_TRACKED", "tracked.json")):
        monkeypatch.setattr(forensics, attr, tmp_path / name, raising=False)
    forensics._TRADES.write_text(json.dumps(trades), "utf-8")

    forensics.main()

    after = live.read_bytes() if live.exists() else None
    assert after == before, (
        "run_trade_forensics wrote to the LIVE execution tape from a test -- the append-only moat "
        "has been contaminated with fixture rows"
    )

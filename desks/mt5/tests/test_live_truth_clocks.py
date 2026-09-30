"""The demotion walk and the fill join, fed honestly and on a clock that reaches them (2026-09-30).

The six-event trace found both organs dark: `decay_live.json` last read the roster on 2026-09-04
and `reports/markout.json` last joined a fill on 2026-09-08, because each had one clock -- the
daily chain -- behind research steps measured at 9,056 s under a 900 s hourly budget. The same
trace found the one decay retirement voided on a constant +0.000 R series, and a fill priced
against the exit instead of the entry. Each test pins one of those.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.execution import fill_corpus as fc  # noqa: E402
from libs.execution.digital_twin import join_cases  # noqa: E402
from research import decay_monitor as D  # noqa: E402

NAME = "gold_asia"
T = "2026-09-29T09:00:00+00:00"


def _ledger(tmp_path, monkeypatch, rows: list[dict]) -> None:
    led = tmp_path / "live_ledger.jsonl"
    led.write_text("".join(json.dumps(r) + "\n" for r in rows), "utf-8")
    monkeypatch.setattr(D, "LEDGER", led)


def _row(r: float, **extra) -> dict:
    return {"time": T, "sleeve": NAME, "r_multiple": r, "risk_quote": 12.5, **extra}


# ------------------------------------------------------------------ decay reads measured R only

def test_a_row_the_gateway_could_not_reconstruct_is_not_a_scratch_trade(tmp_path, monkeypatch):
    _ledger(tmp_path, monkeypatch, [
        _row(-1.0), _row(0.5),
        _row(0.0, r_unreconstructible=True, risk_quote=0.0)])
    assert [t["r_multiple"] for t in D.sleeve_trades(NAME)] == [-1.0, 0.5]


def test_the_pre_fix_zero_signature_is_unmeasured_too(tmp_path, monkeypatch):
    """Before the 2026-09-16 side fix every row read r 0.0 with risk 0 and carried no flag."""
    _ledger(tmp_path, monkeypatch, [_row(0.0, risk_quote=0.0) for _ in range(25)])
    assert D.sleeve_trades(NAME) == []


def test_a_real_scratch_trade_with_a_measured_risk_is_kept(tmp_path, monkeypatch):
    """The legitimate zero: entry and stop known, the trade closed flat."""
    _ledger(tmp_path, monkeypatch, [_row(0.0), _row(-1.0)])
    assert [t["r_multiple"] for t in D.sleeve_trades(NAME)] == [0.0, -1.0]


def test_a_legacy_row_with_no_risk_field_is_still_read(tmp_path, monkeypatch):
    row = {"time": T, "sleeve": NAME, "r_multiple": -0.7}
    _ledger(tmp_path, monkeypatch, [row])
    assert len(D.sleeve_trades(NAME)) == 1


# ------------------------------------------------------------------ both organs have a clock

def test_both_organs_are_hourly_legs_on_the_core_plan() -> None:
    import hourly_cycle as hc
    src = (_DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    for leg in ("decay_monitor", "fill_markout"):
        assert leg in hc.CORE_LEGS
        assert f'_costed("{leg}"' in src
    # the demotion walk runs after the promoter so the two roster writers never overlap
    assert src.index('_costed("promoter"') < src.index('_costed("decay_monitor"')


def test_one_daily_step_runs_alone_and_leaves_the_day_stamp(tmp_path, monkeypatch):
    import daily_cycle as dc
    ran: list[str] = []
    monkeypatch.setattr(dc, "STEPS", (("markout", lambda: ran.append("markout")),
                                      ("proposers", lambda: ran.append("proposers"))))
    monkeypatch.setattr(dc, "STAMP", tmp_path / "daily_cycle_state.json")
    monkeypatch.setattr(dc, "LOG", tmp_path / "daily_cycle.log")
    monkeypatch.setattr(dc, "_woe_before", lambda _n: {})
    monkeypatch.setattr(dc, "_woe_after", lambda *_a, **_k: None)
    assert dc.main(["--step", "markout"]) == 0
    assert ran == ["markout"]
    assert not (tmp_path / "daily_cycle_state.json").exists()
    assert dc.main(["--step", "no_such_step"]) == 2


# ------------------------------------------------------------------ the fill is the entry

def test_the_fill_record_prices_the_entry_not_the_exit() -> None:
    px = 4351.47
    intent = {"time": T, "sleeve": "xau_m15_anti_breakout", "symbol": "XAUUSD", "side": "buy",
              "lot": 0.01, "intended": px, "sl": px - 11.6, "tp": px + 17.4, "ticket": 221208826,
              "retcode": 10009}
    outcome = {"at": T, "algo": "market", "symbol": "XAUUSD", "side": "buy", "lots": 0.01,
               "filled_lots": 0.01, "filled_frac": 1.0, "expected_p_fill": 1.0}
    case = join_cases([intent], [outcome], [], asof=T)[0]
    # a CLOSING deal row: fill_price is where it exited, entry_price where it entered
    deal = {"order": 221208826, "deal": 198773659, "symbol": "XAUUSD", "entry_time": T,
            "fill_price": px - 11.6, "entry_price": 4351.57, "r_multiple": -1.0}
    rec = fc.build_records([case], deals=[deal])[0]
    assert rec.fill_price == pytest.approx(4351.57)

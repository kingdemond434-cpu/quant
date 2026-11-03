"""In-trade management as trials: the exit overlay on the live gold session breakout.

Three properties are fenced:
  * the engine's market-state exit decides on a CLOSED bar and fills at the NEXT open, and a
    signal that does not ask for it walks exactly as before;
  * every overlay policy keeps the parent's entries and rewrites only the exit;
  * EXIT_VARIANTS.json publishes each policy's state and growth deltas, and never raises.
"""
from __future__ import annotations

import json
import sys
from dataclasses import replace
from pathlib import Path

import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_DESK))

from mt5desk import families  # noqa: E402
from mt5desk.engine import Costs, Signal, run_backtest  # noqa: E402

COSTS = Costs(spread_per_lot=0.0, commission_per_lot=0.0, contract_oz=1.0)


def _path(closes: list[float]) -> pd.DataFrame:
    idx = pd.date_range("2026-01-05", periods=len(closes), freq="1h", tz="UTC")
    return pd.DataFrame({"open": closes, "high": [c + 0.2 for c in closes],
                         "low": [c - 0.2 for c in closes], "close": closes}, index=idx)


def test_a_failed_break_exits_at_the_next_open_not_the_close() -> None:
    # Long from 100 (next open after the signal bar), stop 95, target 110. Bars 3..4 hold; bar 5
    # CLOSES at 99, back below the 100 level; the exit is bar 6's open (98), not 99.
    df = _path([100, 100, 100.5, 101, 101, 99, 98, 97, 97, 97, 97, 97])
    sig = Signal(time=df.index[0], side=1, stop=95.0, target=110.0, ttl_bars=10, tag="t",
                 reversal_level=100.0, reversal_after=2)
    tr = run_backtest(df, [sig], COSTS).trades
    assert len(tr) == 1 and tr[0].reason == "reversal"
    assert tr[0].exit == pytest.approx(98.0) and tr[0].exit_time == df.index[6]
    plain = run_backtest(df, [replace(sig, reversal_level=None)], COSTS).trades
    assert plain[0].reason != "reversal", "a signal without the field must walk as before"


def test_the_reversal_waits_its_bars() -> None:
    # The close dips through the level on the first held bar only; with reversal_after=3 that
    # dip is ignored and the trade runs to its target.
    df = _path([100, 99.5, 101, 103, 106, 111, 111, 111, 111, 111])
    sig = Signal(time=df.index[0], side=1, stop=95.0, target=110.0, ttl_bars=9, tag="t",
                 reversal_level=100.0, reversal_after=3)
    assert run_backtest(df, [sig], COSTS).trades[0].reason == "target"


def test_a_spread_blowout_exits_at_the_next_open() -> None:
    df = _path([100, 100, 101, 102, 103, 104, 105, 105, 105, 105]).assign(
        spread=[10, 10, 10, 10, 90, 10, 10, 10, 10, 10],
        tick_volume=[500] * 10)
    sig = Signal(time=df.index[0], side=1, stop=95.0, target=120.0, ttl_bars=8, tag="t",
                 liquidity_spread_max=50.0, liquidity_ticks_min=100.0)
    tr = run_backtest(df, [sig], COSTS).trades
    assert tr[0].reason == "liquidity" and tr[0].exit == pytest.approx(104.0)
    thin = df.assign(spread=10, tick_volume=[500, 500, 500, 40, 500, 500, 500, 500, 500, 500])
    assert run_backtest(thin, [sig], COSTS).trades[0].exit == pytest.approx(103.0)


def _gold_like() -> pd.DataFrame:
    idx = pd.date_range("2026-01-01", periods=24 * 120, freq="1h", tz="UTC")
    base = [100 + ((i * 7) % 23) - 11 + (i // 24) * 0.05 for i in range(len(idx))]
    return pd.DataFrame({"open": base, "high": [v + 2 for v in base],
                         "low": [v - 2 for v in base], "close": [v + 0.5 for v in base]},
                        index=idx)


@pytest.mark.parametrize("policy", families.SESSION_EXIT_POLICIES)
def test_every_policy_keeps_the_parents_entries(policy: str) -> None:
    df = families._h1(_gold_like())
    parent = families.family_session_range_breakout(df)
    got = families.family_session_exit_overlay(df, exit_policy=policy)
    assert parent and len(got) == len(parent)
    for p, g in zip(parent, got, strict=True):
        assert (g.time, g.side, g.stop, g.trigger, g.wait_bars) == (
            p.time, p.side, p.stop, p.trigger, p.wait_bars), "an exit policy moved an entry"
        assert g.runner_trail_k > 0 and g.trail_stall_bars == 3


def test_the_overlay_is_registered_for_the_judge() -> None:
    row = families.FAMILY_REGISTRY["session_exit_overlay"]
    assert row["param_grid"] == {"exit_policy": list(families.SESSION_EXIT_POLICIES)}
    with pytest.raises(ValueError):
        families.family_session_exit_overlay(_gold_like(), exit_policy="hope")


def test_the_table_publishes_and_never_raises(tmp_path, monkeypatch) -> None:
    from research import exit_variants as ev
    monkeypatch.setattr(ev, "REPORT", tmp_path / "EXIT_VARIANTS.json")
    monkeypatch.setattr(ev, "GATE_LEDGER", tmp_path / "ledger.jsonl")
    monkeypatch.setattr(ev, "SURVIVORS", tmp_path / "survivors.json")
    (tmp_path / "ledger.jsonl").write_text(json.dumps(
        {"cell": "XAUUSD session_exit_overlay exit_policy=time_8", "terminal_gate": "pbo",
         "passed": False, "at": "2026-11-03T20:00:00+00:00"}) + "\n")
    (tmp_path / "survivors.json").write_text(json.dumps(
        {"survivors": {"XAUUSD session_exit_overlay exit_policy=regime": {}}}))
    monkeypatch.setattr(ev, "screen", lambda meta=None: {
        "parent": [1.0, -1.0], "variants": {p: [1.0, -0.5] for p in
                                            families.SESSION_EXIT_POLICIES}})
    doc = ev.publish()
    rows = {r["policy"]: r for r in doc["variants"]}
    assert rows["time_8"]["state"] == "JUDGED" and rows["regime"]["state"] == "PROMOTED"
    assert rows["ratchet"]["state"] == "BUILT" and rows["ratchet"]["dlogw_vs_static"] > 0
    assert json.loads((tmp_path / "EXIT_VARIANTS.json").read_text())["sleeve"] == "gold_asia"

    def boom(meta=None):
        raise RuntimeError("no data")
    monkeypatch.setattr(ev, "screen", boom)
    assert ev.publish()["screen_error"].startswith("RuntimeError")

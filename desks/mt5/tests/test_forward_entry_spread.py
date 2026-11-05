"""The forward replay charges the spread a trade actually crossed, keys say whose rows they are,
and keys that took identical entries are one effective trial (Auditor HOLD, 2026-11-05).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

DESK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DESK / "research"))
sys.path.insert(0, str(DESK))

import shadow_forward as sf  # noqa: E402
from mt5desk.engine import Costs, Trade  # noqa: E402

TICK = 1e-05


def _bars(spread_at_hour0: float = 80.0, quiet: float = 0.0, days: int = 3):
    idx = pd.date_range("2026-10-01", periods=24 * days, freq="h", tz="UTC")
    sp = [spread_at_hour0 if ts.hour == 0 else quiet for ts in idx]
    return pd.DataFrame({"open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "spread": sp},
                        index=idx)


def _costs(spread_pts: float = 2.0):
    return Costs(spread_per_lot=spread_pts * TICK * 100000.0, commission_per_lot=0.0,
                 contract_oz=100000.0, quote_per_account=1.0)


def _trade(side: int, entry_h: int, exit_h: int, r: float = 1.0, stop_pts: float = 100.0):
    e = pd.Timestamp("2026-10-02", tz="UTC") + pd.Timedelta(hours=entry_h)
    x = pd.Timestamp("2026-10-02", tz="UTC") + pd.Timedelta(hours=exit_h)
    return Trade(entry_time=e, exit_time=x, side=side, entry=1.0,
                 exit=1.0, stop=1.0 - side * stop_pts * TICK, target=1.1,
                 bars_held=1, r_multiple=r, reason="t")


def _surface_with(hour_pts: dict[int, float], sym: str = "GBPCHF"):
    return [{"source": "mt5 tick tape (recorders/tick_recorder)",
             "symbols": {sym: {"hours": {str(h): {"status": "MEASURED", "p50": v}
                                         for h, v in hour_pts.items()}}}}]


def _measured(monkeypatch, tape: dict | None = None, hours: dict | None = None):
    sf._reset_spread_caches()
    monkeypatch.setattr(sf, "_tape_minute_spreads", lambda sym, day, point: tape)
    monkeypatch.setattr(sf, "_tick_surfaces", lambda: _surface_with(hours or {}))


def _minute(ts: pd.Timestamp) -> int:
    return int(ts.value // 60_000_000_000)


def test_a_long_entering_at_rollover_pays_the_tape_minute(monkeypatch):
    t = _trade(1, 1, 3)
    _measured(monkeypatch, tape={_minute(t.entry_time): 80.0}, hours={1: 6.0})
    out, rep = sf.reprice_at_measured_spread([t], _bars(), _costs(2.0), {"tick_size": TICK},
                                             "GBPCHF")
    assert abs(out[0].r_multiple - (1.0 - 0.78)) < 1e-9      # 80 - 2 = 78 pts over 100
    assert rep["sources"] == {"tape_minute": 1} and rep["repriced"] == 1


def test_a_short_pays_at_its_exit_bar(monkeypatch):
    t = _trade(-1, 1, 3)
    _measured(monkeypatch, tape={_minute(t.exit_time): 2.0, _minute(t.entry_time): 80.0})
    out, _ = sf.reprice_at_measured_spread([t], _bars(), _costs(2.0), {"tick_size": TICK},
                                           "GBPCHF")
    assert out[0].r_multiple == 1.0


def test_it_is_two_sided_a_narrower_spread_gives_r_back(monkeypatch):
    t = _trade(1, 12, 13)
    _measured(monkeypatch, hours={12: 0.5})
    out, rep = sf.reprice_at_measured_spread([t], _bars(), _costs(2.0), {"tick_size": TICK},
                                             "GBPCHF")
    assert abs(out[0].r_multiple - (1.0 + 0.015)) < 1e-9     # 2 - 0.5 = 1.5 pts back
    assert rep["sources"] == {"tick_hour": 1} and rep["r_delta"] > 0


def test_with_no_measurement_the_frozen_basis_stands_and_is_named(monkeypatch):
    t = _trade(1, 5, 6)
    _measured(monkeypatch)
    out, rep = sf.reprice_at_measured_spread([t], _bars(), _costs(2.0), {"tick_size": TICK},
                                             "GBPCHF")
    assert out == [t] and rep["sources"] == {"frozen": 1} and rep["by_entry"] == {}


def test_the_bars_own_spread_column_is_never_a_source(monkeypatch):
    t = _trade(1, 0, 3)
    _measured(monkeypatch)
    out, _ = sf.reprice_at_measured_spread([t], _bars(spread_at_hour0=150.0), _costs(2.0),
                                           {"tick_size": TICK}, "GBPCHF")
    assert out == [t]


def test_no_tick_size_is_unmeasured_and_changes_nothing(monkeypatch):
    t = _trade(1, 0, 3)
    _measured(monkeypatch, hours={0: 80.0})
    out, rep = sf.reprice_at_measured_spread([t], _bars(), _costs(), {}, "GBPCHF")
    assert out == [t] and rep["status"] == "UNMEASURED" and rep["why"]


def test_the_bar_surface_tick_hours_block_is_read_when_the_tape_surface_is_absent(monkeypatch):
    sf._reset_spread_caches()
    monkeypatch.setattr(sf, "_tick_surfaces", lambda: [{"source": "desks\\mt5\\data\\universe",
        "symbols": {"GBPCHF": {"hours": {"1": {"status": "MEASURED", "p50": 6.0}},
                               "tick_hours": {"hours": {"1": {"status": "MEASURED",
                                                              "p50": 40.0}}}}}}])
    assert sf._tick_hour_spread("GBPCHF", 1) == 40.0
    assert sf._tick_hour_spread("GBPCHF", 2) is None


def test_the_tape_minute_reader_drops_unstamped_ticks(monkeypatch, tmp_path):
    import mt5desk.tape as tape
    d = tmp_path / "GBPCHF"
    d.mkdir()
    base = int(pd.Timestamp("2026-11-04 01:00", tz="UTC").value // 1_000_000)
    df = pd.DataFrame({"time_msc": pd.array([base, base + 1000, base + 2000, None],
                                            dtype="Int64"),
                       "bid": [1.0, 1.0, 1.0, 1.0], "ask": [1.0008, 1.0008, 1.0008, 1.5]})
    df.to_parquet(d / "2026-11-04.parquet")
    monkeypatch.setattr(tape, "TICKS", tmp_path)
    sf._reset_spread_caches()
    mins = sf._tape_minute_spreads("GBPCHF", "2026-11-04", TICK)
    assert mins == {base // 60_000: pytest.approx(80.0)}


def test_keys_on_identical_entries_are_one_stream():
    a = [_trade(1, 0, 3), _trade(1, 24, 27)]
    b = [_trade(1, 0, 4), _trade(1, 24, 28)]           # same entries, different exits
    c = [_trade(-1, 0, 3)]
    state = {"k1": {"entry_stream": sf.entry_stream_id("GBPCHF", a)},
             "k2": {"entry_stream": sf.entry_stream_id("GBPCHF", b)},
             "k3": {"entry_stream": sf.entry_stream_id("GBPCHF", c)},
             "k4": {"entry_stream": sf.entry_stream_id("GBPCHF", [])},
             "last_run": "2026-11-05"}
    rep = sf.entry_stream_report(state)
    assert rep["effective_streams"] == 2 and rep["shared_streams"] == 1
    assert list(rep["shared"].values()) == [["k1", "k2"]]
    assert sf.entry_stream_id("EURCHF", a)["id"] != state["k1"]["entry_stream"]["id"]


def test_key_ledgers_live_where_no_cell_ledger_glob_reads_them(tmp_path, monkeypatch):
    monkeypatch.setattr(sf, "KEY_LEDGER_DIR", tmp_path / "keys")
    sf._write_key_ledger("GBPCHF.formula.asia@M5|x", [_trade(1, 0, 3)], None, {})
    files = list((tmp_path / "keys").glob("*.json"))
    assert len(files) == 1 and not list(tmp_path.glob("ledger_*.json"))
    import json
    assert json.loads(files[0].read_text())[0]["key"] == "GBPCHF.formula.asia@M5|x"
    assert sf._key_ledger_path("a/b") != sf._key_ledger_path("a_b")


def test_the_replay_reprices_writes_the_key_and_publishes_the_streams():
    src = (DESK / "research" / "shadow_forward.py").read_text(encoding="utf-8")
    assert "reprice_at_measured_spread(\n                res.trades, h1, costs, meta.get(sym) or {}, sym)" in src
    assert '"spread_src":' in src and "_reset_spread_caches()" in src
    assert "all_trades = [t for t in _priced if t.entry_time >= SHADOW_START]" in src
    assert '"key": key,' in src and "_write_key_ledger(key, all_trades" in src
    assert "entry_stream_report(state)" in src


def test_the_reprice_report_ranks_rows_by_the_r_they_were_not_charged():
    state = {"a": {"status": "PROMOTION CANDIDATE",
                   "entry_spread": {"status": "MEASURED", "repriced": 3, "trades": 5,
                                    "r_delta": -2.5}},
             "b": {"status": "ACTIVE", "entry_spread": {"status": "MEASURED", "repriced": 1,
                                                        "trades": 9, "r_delta": 0.1}},
             "c": {"entry_spread": {"status": "UNMEASURED"}}, "last_run": "x"}
    rep = sf.spread_reprice_report(state)
    assert [r["key"] for r in rep["top"]] == ["a", "b"]
    assert rep["rows_by_status"] == {"MEASURED": 2, "UNMEASURED": 1}


def test_cost_surface_prefers_the_tick_hour_and_survives_unstamped_ticks(tmp_path, monkeypatch):
    import cost_surface as cs
    surf = {"symbols": {"GBPCHF": {
        "hours": {"1": {"status": "MEASURED", "p50": 6.0}, "2": {"status": "MEASURED",
                                                                  "p50": 4.0}},
        "tick_hours": {"hours": {"1": {"status": "MEASURED", "p50": 40.0},
                                 "2": {"status": "UNMEASURED"}}}}}}
    assert cs.spread_pts(surf, "GBPCHF", 1) == 40.0
    assert cs.spread_pts(surf, "GBPCHF", 2) == 4.0
    import mt5desk.tape as tape
    d = tmp_path / "GBPCHF"
    d.mkdir()
    base = int(pd.Timestamp("2026-11-04 01:00", tz="UTC").value // 1_000_000)
    n = 250
    pd.DataFrame({"time_msc": pd.array([base + i for i in range(n)] + [None], dtype="Int64"),
                  "bid": [1.0] * (n + 1), "ask": [1.0002] * (n + 1)}
                 ).to_parquet(d / "2026-11-04.parquet")
    monkeypatch.setattr(tape, "TICKS", tmp_path)
    prof = cs.tick_profile("GBPCHF", TICK, root=tmp_path)
    assert prof is not None and prof["hours"]["1"]["status"] == "MEASURED"
    assert prof["hours"]["1"]["p50"] == pytest.approx(20.0)

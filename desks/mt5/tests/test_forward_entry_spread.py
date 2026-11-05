"""The forward replay charges the spread a trade actually crossed, keys say whose rows they are,
and keys that took identical entries are one effective trial (Auditor HOLD, 2026-11-05).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

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


def test_a_long_entering_at_rollover_pays_the_rollover_spread():
    out, rep = sf.reprice_at_measured_spread([_trade(1, 0, 3)], _bars(), _costs(2.0),
                                             {"tick_size": TICK})
    # 80 measured - 2 charged = 78 pts over a 100-pt stop
    assert abs(out[0].r_multiple - (1.0 - 0.78)) < 1e-9
    assert rep["status"] == "MEASURED" and rep["repriced"] == 1


def test_a_short_pays_at_its_exit_bar_not_its_entry_bar():
    bars = _bars()
    out, _ = sf.reprice_at_measured_spread([_trade(-1, 0, 3)], bars, _costs(2.0),
                                           {"tick_size": TICK})
    assert out[0].r_multiple == 1.0                     # exit at 03:00, quiet hour
    out, _ = sf.reprice_at_measured_spread([_trade(-1, 21, 24)], bars, _costs(2.0),
                                           {"tick_size": TICK})
    assert out[0].r_multiple < 1.0                      # exit at 00:00 next day


def test_the_charge_is_one_sided_and_never_raises_r():
    out, rep = sf.reprice_at_measured_spread([_trade(1, 5, 6)], _bars(), _costs(2.0),
                                             {"tick_size": TICK})
    assert out[0].r_multiple == 1.0 and rep["repriced"] == 0


def test_the_hour_median_covers_a_bar_that_under_reads():
    bars = _bars()
    bars.loc[pd.Timestamp("2026-10-02 00:00", tz="UTC"), "spread"] = 0.0
    out, _ = sf.reprice_at_measured_spread([_trade(1, 0, 3)], bars, _costs(2.0),
                                           {"tick_size": TICK})
    assert out[0].r_multiple < 1.0


def test_no_spread_column_or_tick_is_unmeasured_and_changes_nothing():
    bars = _bars().drop(columns=["spread"])
    t = _trade(1, 0, 3)
    out, rep = sf.reprice_at_measured_spread([t], bars, _costs(), {"tick_size": TICK})
    assert out == [t] and rep["status"] == "UNMEASURED" and rep["why"]
    out, rep = sf.reprice_at_measured_spread([t], _bars(), _costs(), {})
    assert out == [t] and rep["status"] == "UNMEASURED"


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
    assert "reprice_at_measured_spread(\n                res.trades, h1, costs" in src
    assert "all_trades = [t for t in _priced if t.entry_time >= SHADOW_START]" in src
    assert '"key": key,' in src and "_write_key_ledger(key, all_trades" in src
    assert "entry_stream_report(state)" in src

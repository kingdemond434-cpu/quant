"""specialist_cell's Tier-1 idea cells (U1, U2, U4, U5, N1) and the report that says what holds
each one back."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

_DESK = Path(__file__).resolve().parents[1]
for p in (str(_DESK), str(_DESK / "research"), str(_DESK / "scripts"), str(_DESK.parents[1])):
    if p not in sys.path:
        sys.path.insert(0, p)

from research import specialist_cell as sc  # noqa: E402
from research.gauntlet_buildability import BUILDABLE, cell_verdict  # noqa: E402


def _cells(by_class):
    return sc.plan(by_class)


def test_u1_is_minted_on_indices_gold_and_oil_on_the_venue_clock():
    cells = _cells({"indices": ["US500", "GER40", "JPN225"], "metals": ["XAUUSD"],
                    "energy": ["XTIUSD"]})
    u1 = [c for c in cells if c["mechanism"] == "intraday_momentum"]
    assert {c["symbol"] for c in u1} == {"US500", "GER40", "JPN225", "XAUUSD", "XTIUSD"}
    for c in u1:
        p = c["params"]
        assert c["family"] == "session_handoff" and p["direction"] == 1
        assert p["source_tz"] == p["trade_tz"] and p["trade_align"] == "start"
        assert cell_verdict(c["family"], p)[0] == BUILDABLE, "U1 needs no new family"
    us = next(c for c in u1 if c["symbol"] == "US500")["params"]
    assert (us["source_tz"], us["source_at"], us["trade_at"]) == ("America/New_York", "09:30",
                                                                  "14:00")


def test_u1_fires_the_closing_hour_in_the_open_hours_direction():
    """The minted params, run through the family, decide at the bar starting 14:00 New York and
    take the sign of the bar containing 09:30 -- on the local clock whatever the DST state."""
    from mt5desk import local_clock as lc
    from mt5desk.families_edge_queue import family_session_handoff
    idx = pd.date_range("2024-01-02", periods=24 * 300, freq="1h", tz="UTC")
    idx = idx[idx.dayofweek < 5]
    r = np.random.default_rng(4).normal(0, 0.002, len(idx))
    close = 100 * np.exp(np.cumsum(r))
    df = pd.DataFrame({"open": np.r_[100.0, close[:-1]], "high": close * 1.001,
                       "low": close * 0.999, "close": close}, index=idx)
    p = next(c for c in _cells({"indices": ["US500"]})
             if c["mechanism"] == "intraday_momentum" and c["params"]["min_info_atr"] == 0.0
             )["params"]
    sigs = family_session_handoff(df, **p)
    assert sigs
    minute, ymd = lc.local_frame(df.index, "America/New_York")
    src = lc.window_mask(df.index, "America/New_York", "09:30", "contains")
    for s in sigs:
        i = df.index.get_loc(s.time)
        assert minute[i] == 14 * 60
        j = next(k for k in range(i, -1, -1) if src[k] and ymd[k] == ymd[i])
        assert s.side == int(np.sign(df["close"].iloc[j] - df["open"].iloc[j]))


def test_u2_u4_u5_n1_name_their_families_and_targets():
    cells = _cells({"indices": ["US500", "NAS100", "UK100", "JPN225"], "fx": ["USDJPY", "EURUSD"],
                    "metals": ["XAUUSD"]})
    by = {}
    for c in cells:
        by.setdefault(c["mechanism"], set()).add(c["symbol"])
    assert by["overnight_day_tug"] == {"US500", "NAS100", "UK100", "JPN225"}
    assert by["weekend_crypto_lead"] == {"NAS100", "USDJPY", "XAUUSD"}, "EURUSD not named"
    assert by["earnings_gap_breadth"] == {"US500", "NAS100"}
    assert by["pre_holiday_drift"] == {"US500", "NAS100", "UK100"}, "JPX is not generated"
    fams = {c["mechanism"]: c["family"] for c in cells}
    for key, spec in sc.TIER1_IDEAS.items():
        for _klass, mech in spec["units"]:
            if mech in fams:
                assert fams[mech] == spec["family"], key
    for c in cells:
        if c["mechanism"] == "weekend_crypto_lead":
            assert c["params"]["driver_symbol"] in sc.WEEKEND_DRIVERS
        if c["mechanism"] == "pre_holiday_drift":
            assert c["params"]["hold_bars"] == 23 * c["params"]["days_before"]


def test_report_names_the_stage_that_holds_each_idea_back(tmp_path, monkeypatch):
    monkeypatch.setattr(sc, "STATE", tmp_path / "state.json")
    monkeypatch.setattr(sc, "CANON", tmp_path / "absent.json")
    monkeypatch.setattr(sc, "_meta", lambda: {})
    monkeypatch.setattr(sc, "measure", lambda s, f, p, m: {"built": True, "signal_days": 40,
                                                            "trade_days_lb": 40})
    doc = sc.run(budget_s=120, dry_run=True, out=tmp_path / "SPECIALIST_CELLS.json",
                 symbols_by_class={"indices": ["US500"], "metals": ["XAUUSD"],
                                   "energy": ["XTIUSD"], "fx": ["USDJPY"]})
    ideas = doc["tier1_ideas"]
    assert set(ideas) == set(sc.TIER1_IDEAS)
    assert ideas["U1"]["holding_it_back"].startswith("built but under the")
    for key in ("U2", "U4", "U5", "N1"):
        row = ideas[key]
        if row["family_verdict"] == BUILDABLE:
            assert row["holding_it_back"].startswith("built but under the"), key
        else:
            assert row["holding_it_back"].startswith(f"family {row['family']} not buildable")
    assert ideas["N1"]["not_covered"] == {"JPN225": sc.TIER1_IDEAS["N1"]["not_covered"]["JPN225"]}

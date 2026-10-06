"""An evicted certificate re-enters the judge's docket first, never-judged, with its params written.

THE DEFECT THESE PIN (2026-09-30). `certificate_hygiene` evicted six certificates whose params
were never recorded (five `session_range_breakout` asia cells, one hunt16 `dav_range_filter_adx`
cell). Nothing ever put them back in front of the sealed gauntlet: `requeue_unrunnable` reads the
canon they had left, queued `params: {}` (a different strategy) and did not stamp the row, which
the gauntlet's point-in-time ratchet skips.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK.parents[1]), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import rejudge_evicted as rj  # noqa: E402
from frontier_identity import cell_id  # noqa: E402

from libs.data.pit import is_stamped  # noqa: E402

NOW = datetime(2026, 9, 30, 12, 0, tzinfo=UTC)


def _gates(days_sharpe: float, ev: float, x3: float) -> dict:
    return {"in_sample_screen": {"passed": True, "sharpe": days_sharpe},
            "cpcv": {"passed": True, "mean_oos_sharpe": days_sharpe},
            "walk_forward": {"passed": True, "oos_sharpe": days_sharpe + 0.01},
            "stress_costs": {"passed": True, "exp_x3": x3},
            "expected_value": {"passed": True, "ev": ev}}


def _srb(sym: str, params: dict | None, sharpe: float, ev: float, x3: float,
         days: int = 2101) -> dict:
    spec = {"symbol": sym, "selector": "asia", "family": "session_range_breakout",
            "is_universe": True, "hunt": "external_discoveries", "condition": None}
    if params is not None:
        spec["params"] = params
    return {"days": days, "gates": _gates(sharpe, ev, x3), "gated_at": "2026-08-25T22:00:00",
            "shadow_spec": spec}


@pytest.fixture
def desk(tmp_path, monkeypatch):
    rep, dat = tmp_path / "reports", tmp_path / "data" / "hypotheses"
    rep.mkdir(parents=True)
    dat.mkdir(parents=True)
    paths = {"EVICTED": rep / "UNIVERSAL_SURVIVORS_UNRUNNABLE.json",
             "SURVIVORS": rep / "UNIVERSAL_SURVIVORS.json",
             "CANON": tmp_path / "data" / "UNIVERSAL_SURVIVORS.canon.json",
             "DOCKET": dat / "external_survivors.json",
             "SEEN_CELLS": dat / "gauntlet_seen_cells.json",
             "PRIORITY": dat / "priority_rejudge.json",
             "OUT": rep / "REJUDGE_EVICTED.json"}
    for name, p in paths.items():
        monkeypatch.setattr(rj, name, p)
    monkeypatch.setattr(rj, "ROOT", tmp_path)
    twins = {
        "external.XAUUSD.session_range_breakout.rr=2.0_wb=12":
            _srb("XAUUSD", {"rr": 2.0, "wait_bars": 12}, 0.1845, 0.2132, 0.1928),
        "external.XAUUSD.session_range_breakout.rr=2.5_wb=12":
            _srb("XAUUSD", {"rr": 2.5, "wait_bars": 12}, 0.1914, 0.2371, 0.2166),
        "external.XAUUSD.session_range_breakout.rr=1.5_wb=8":
            _srb("XAUUSD", {"rr": 1.5, "wait_bars": 8}, 0.1914, 0.2371, 0.2166, days=2046),
    }
    paths["CANON"].write_text(json.dumps({"survivors": twins, "unrunnable_evicted": [
        "external.XAUUSD.session_range_breakout",
        "qquant.hunt16.json.AUDNZD dav_range_filter_adx SHORT afternoon NORMAL_DAY"]}))
    evicted = {
        "external.XAUUSD.session_range_breakout": _srb("XAUUSD", None, 0.1914, 0.2371, 0.2166),
        "qquant.hunt16.json.AUDNZD dav_range_filter_adx SHORT afternoon NORMAL_DAY": {
            "days": 179, "gates": _gates(0.3177, 0.3931, 0.1116),
            "gated_at": "2026-08-23T13:51:10",
            "shadow_spec": {"symbol": "AUDNZD", "family": "dav_range_filter_adx",
                            "side": "SHORT", "selector": "afternoon",
                            "condition": "NORMAL_DAY", "is_universe": True,
                            "hunt": "hunt16.json"}},
    }
    paths["EVICTED"].write_text(json.dumps({"survivors": evicted}))
    paths["SEEN_CELLS"].write_text(json.dumps(
        {"XAUUSD.session_range_breakout.rr=2.5_wb=12": "2026-08-26T01:44:33"}))
    other = {"symbol": "EURUSD", "family": "carry", "params": {"k": 1},
             "available_time": "x", "ingested_time": "x", "source_version": "x",
             "payload_hash": "x"}
    paths["DOCKET"].write_text(json.dumps([other]))
    return paths


def _cells(doc: dict) -> dict[str, dict]:
    return {c["symbol"]: c for c in doc["cells"]}


def test_bare_breakout_recovers_its_twins_params_and_the_window_hours(desk):
    doc = rj.build(NOW)
    xau = _cells(doc)["XAUUSD"]
    assert xau["params_source"] == "fingerprint"
    assert xau["twin"]["twin"] == "external.XAUUSD.session_range_breakout.rr=2.5_wb=12"
    # rr/wait_bars from the twin, session hours and ttl from the forward engine's own window.
    assert xau["params"] == {"range_start": 7, "wait_bars": 12, "rr": 2.5, "ttl_bars": 12}
    assert "shadow_forward.WINDOWS['asia']" in xau["provenance"]


def test_the_rejudged_cell_is_never_judged_although_its_legacy_twin_was(desk):
    xau = _cells(rj.build(NOW))["XAUUSD"]
    legacy = cell_id({"sym": "XAUUSD", "family": "session_range_breakout",
                      "params": {"rr": 2.5, "wait_bars": 12}})
    assert legacy == "XAUUSD.session_range_breakout.rr=2.5_wb=12"
    assert xau["cell_id"] != legacy
    assert xau["already_judged"] is False


def test_hunt16_cell_carries_side_hour_and_day_state_as_params(desk):
    aud = _cells(rj.build(NOW))["AUDNZD"]
    assert aud["family"] == "hunt16_cell"
    assert aud["params"] == {"base_family": "dav_range_filter_adx", "direction": "SHORT",
                             "signal_at": 17, "day_state": "NORMAL_DAY"}
    assert aud["params_source"] == "certificate_spec"


def test_ambiguous_fingerprint_falls_back_to_window_defaults_and_says_so(desk):
    canon = json.loads(desk["CANON"].read_text())
    # A second twin at the same distance: nothing may be claimed.
    canon["survivors"]["external.XAUUSD.session_range_breakout.p=dup"] = _srb(
        "XAUUSD", {"rr": 3.0, "wait_bars": 12}, 0.1914, 0.2371, 0.2166)
    desk["CANON"].write_text(json.dumps(canon))
    xau = _cells(rj.build(NOW))["XAUUSD"]
    assert xau["params_source"] == "window_default"
    assert "NOT recovered" in xau["provenance"]
    assert xau["params"] == {"range_start": 7, "wait_bars": 12, "rr": 2.0, "ttl_bars": 12}


def test_apply_puts_stamped_cells_at_the_docket_front_once(desk):
    doc = rj.run(apply_changes=True, now=NOW)
    assert doc["applied"]["queued"] == 2
    docket = json.loads(desk["DOCKET"].read_text())
    assert {r["symbol"] for r in docket[:2]} == {"XAUUSD", "AUDNZD"}
    assert docket[2]["symbol"] == "EURUSD"                        # nothing dropped
    for r in docket[:2]:
        assert is_stamped(r)                         # the gauntlet's PIT ratchet admits it
        assert r["judging_status"] == "NEVER_JUDGED"
        assert r["params"] and r["params_source"] and r["params_provenance"]
        # NO FREE TRIALS: nothing on the row asks the judge for an exemption or a trial count.
        assert not {"n_trials", "trial_exempt", "exempt", "verdict", "passed"} & set(r)
    assert json.loads(desk["PRIORITY"].read_text())["rows"]
    assert json.loads(desk["OUT"].read_text())["applied"]["queued"] == 2
    # Idempotent: a second pass finds both on the docket and does not rewrite or duplicate it.
    again = rj.run(apply_changes=True, now=NOW)
    assert again["applied"] == {"queued": 0, "already_on_docket": 2, "front_block": 0,
                                "docket": str(desk["DOCKET"].relative_to(rj.ROOT))}
    assert len(json.loads(desk["DOCKET"].read_text())) == 3


def test_hunt16_cell_family_reproduces_the_hunt_signals():
    from mt5desk import families_orthogonal as fo
    from research.run_hunt12 import day_states
    from research.run_hunt16 import dav_range_filter_adx

    rng = np.random.default_rng(7)
    idx = pd.date_range("2025-01-01", periods=24 * 120, freq="h", tz="UTC")
    close = 1.1 + np.cumsum(rng.normal(0, 0.0015, len(idx)))
    df = pd.DataFrame({"open": close, "close": close + rng.normal(0, 0.0005, len(idx))},
                      index=idx)
    df["high"] = df[["open", "close"]].max(axis=1) + 0.001
    df["low"] = df[["open", "close"]].min(axis=1) - 0.001
    h1 = fo._h1(df)
    states = day_states(h1)
    want = [s for s in dav_range_filter_adx(h1, -1)
            if s.time.hour == 17 and states.get(pd.Timestamp(s.time).date()) == "NORMAL_DAY"]
    # The sealed gauntlet always passes side=1; `direction` must win.
    got = fo.family_hunt16_cell(df, side=1, base_family="dav_range_filter_adx",
                                direction="SHORT", signal_at=17, day_state="NORMAL_DAY")
    assert got == want
    assert all(s.side == -1 for s in got)
    assert "hunt16_cell" in fo.ORTHOGONAL_FAMILIES

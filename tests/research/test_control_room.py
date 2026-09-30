"""The live control room: causal regime labels, the kernel's shape, the contract and bridge."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[2]
for _p in (str(ROOT), str(ROOT / "desks" / "mt5"), str(ROOT / "desks" / "mt5" / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.regime import control_room as cr  # noqa: E402


def _h1(days: int = 420, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2024-01-01", periods=days * 24, freq="h", tz="UTC")
    close = 100 * np.exp(np.cumsum(rng.normal(0, 0.002, idx.size)))
    df = pd.DataFrame({"open": close, "high": close * 1.001, "low": close * 0.999,
                       "close": close, "tick_volume": rng.integers(100, 1000, idx.size),
                       "spread": rng.integers(10, 14, idx.size)}, index=idx)
    return df[df.index.dayofweek < 5]


def test_labels_are_causal():
    """Appending future bars never changes a past day's label."""
    h1 = _h1()
    full = cr.label_days(cr.daily_frame(h1))
    cut = cr.label_days(cr.daily_frame(h1.iloc[: len(h1) - 24 * 30]))
    common = cut.index.intersection(full.index)[:-1]
    for a in cr.AXES:
        assert (full.loc[common, a] == cut.loc[common, a]).all(), a


def test_incomplete_last_day_is_dropped_and_zero_spread_is_missing():
    h1 = _h1(days=30)
    h1 = h1.iloc[:-10]                                   # last day holds 14 of 24 hours
    h1.loc[h1.index[-50:], "spread"] = 0
    d = cr.daily_frame(h1)
    assert str(h1.index[-1])[:10] not in d.index
    assert not (d["spread"] == 0).any()


def test_kernel_matches_score_one_and_mismatches_eps():
    hist = pd.DataFrame({"vol": ["low", "high", ""], "trend": ["trend", "trend", "range"],
                         "liq": ["normal", "normal", "thin"]})
    w = cr.kernel(hist, {"vol": "low", "trend": "trend", "liq": "normal"}, eps=0.5)
    assert w[0] == 1.0 and w[1] == 0.5 and np.isnan(w[2])


def test_sleeve_weights_lag_one_day_and_fail_closed():
    lab = cr.label_days(cr.daily_frame(_h1(days=700)))
    days = list(lab.index[-100:])
    w, meta = cr.sleeve_weights("X", days, labels=lab)
    assert meta["status"] == "MEASURED" and w.size == len(days)
    # the weight of day d is the state of day d-1 against now
    now = lab[lab["vol"] != ""].iloc[-1]
    prev = lab.loc[days[-2]]
    expect = np.prod([1.0 if prev[a] == now[a] else cr.EPS for a in cr.AXES])
    assert abs(w[-1] - expect) < 1e-12
    w2, meta2 = cr.sleeve_weights("NOSUCHSYMBOL", days)
    assert w2.size == 0 and meta2["status"] == "UNMEASURED"


def test_contract_runs_and_never_admits_off_the_desk(tmp_path, monkeypatch):
    import regime_allocation_contract as rac
    monkeypatch.setattr(rac, "DESK_MATRIX", tmp_path / "absent.parquet")
    doc = rac.run(step=21, train_n=300, n_worlds=32, n_rows=64,
                  assets=("EURUSD", "USDJPY", "XAUUSD"), with_hmm=False, max_steps=2)
    assert doc["design"]["universe"] == "bars"
    assert doc["admits"] is False
    assert {"equal", "geo", "geo_asset", "switch"} <= set(doc["arms"])
    assert doc["trials"] == len(doc["arms"])


def test_bench_bridge_scores_by_elog_and_lists_missed_growth(tmp_path):
    import bench_bridge as bb
    (tmp_path / "c.json").write_text(json.dumps({"n": 10, "survivors": {}}))
    (tmp_path / "f.json").write_text(json.dumps({"n_enrolled": 8, "n_missing": 2}))
    (tmp_path / "s.json").write_text(json.dumps({"sleeves": [
        {"name": "A", "status": "LIVE"}, {"name": "B", "status": "LIVE"},
        {"name": "C", "status": "STANDBY"}]}))
    (tmp_path / "a.json").write_text(json.dumps({"book": {"A": 0.1}, "admission": {
        "admitted": ["A"], "candidates": {
            "A": {"delta_elogw_per_day": 0.0002, "delta_elogw_per_year": 0.05},
            "C": {"delta_elogw_per_day": 0.0001, "delta_elogw_per_year": 0.025},
            "D": {"delta_elogw_per_day": -0.0001, "delta_elogw_per_year": -0.025}}}}))
    doc = bb.build({"certified": tmp_path / "c.json", "forward": tmp_path / "f.json",
                    "live": tmp_path / "s.json", "allocation": tmp_path / "a.json",
                    "regime_contract": tmp_path / "absent.json"})
    assert [r["candidate"] for r in doc["scored_candidates"]] == ["A", "C", "D"]
    assert [r["candidate"] for r in doc["missed_growth"]] == ["C"]
    assert doc["live_but_unfunded"] == ["B"]
    assert doc["conversion"]["bench_to_forward"] == 0.8
    assert doc["regime_contract"]["status"].startswith("UNMEASURED")


def test_daily_cycle_runs_the_control_room_after_the_portfolio():
    import daily_cycle
    names = [n for n, _ in daily_cycle.STEPS]
    assert "control_room" in names
    assert names.index("portfolio") < names.index("control_room")


def test_practitioner_processes_bind_every_stage_and_name_the_bottleneck(tmp_path, monkeypatch):
    import practitioner_processes as pp
    monkeypatch.setattr(pp, "R", tmp_path)
    monkeypatch.setattr(pp, "D", tmp_path)
    (tmp_path / "CONTROL_ROOM.json").write_text(json.dumps({"assets": {"EURUSD": {}},
                                                            "share_trending": 1.0}))
    (tmp_path / "REGIME_ALLOCATION_CONTRACT.json").write_text(json.dumps(
        {"verdict": "INCONCLUSIVE", "admits": False, "design": {"universe": "desk"}}))
    doc = pp.run()
    kw = doc["processes"]["korean_winner"]
    status = {s["stage"]: s["status"] for s in kw["stages"]}
    assert status["regime_detection"] == "RUNNING"
    assert status["regime_drives_weights"] == "NOT_ADMITTED"
    assert status["geometric_allocation"] == "UNMEASURED"
    assert kw["complete"] is False and kw["bottleneck"] == "geometric_allocation"
    for proc in doc["processes"].values():
        assert all(s["organ"] for s in proc["stages"]), "every stage names the organ doing it"


def test_daily_cycle_publishes_the_practitioner_processes():
    import inspect

    import daily_cycle
    assert "practitioner_processes" in inspect.getsource(daily_cycle._control_room)


def test_admitting_contract_is_not_running_until_the_allocator_reads_it(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    sys.path.insert(0, str(ROOT / "desks" / "mt5" / "research"))
    import practitioner_processes as pp
    monkeypatch.setattr(pp, "R", tmp_path)
    doc = {"admits": True, "verdict": "GAIN"}
    assert pp._contract(doc)[0] == "NOT_WIRED"
    (tmp_path / "pf_allocation.json").write_text(json.dumps({"control_room_kernel": {}}))
    assert pp._contract(doc)[0] == "RUNNING"
    assert pp._contract({"admits": False})[0] == "NOT_ADMITTED"

"""The ordered STANDBY hold and the replication LIVE door each have a producer (III.16): their
rails read the rows the hold keeps out of sleeves.json and price them by forward R, instead of
`measure_veto`'s FILTER_VALUE entry that no organ ever writes for them."""
from __future__ import annotations

import json
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(BASE / "research"), str(BASE), str(BASE.parent.parent)]
import missed_growth as mg  # noqa: E402

from libs.portfolio.rails import rail  # noqa: E402

ALLOC = {"book": {"a": 0.02, "b": 0.02}}


def _book(tmp_path, monkeypatch, rows):
    p = tmp_path / "sleeves.json"
    p.write_text(json.dumps({"sleeves": rows}), encoding="utf-8")
    monkeypatch.setattr(mg, "SLEEVES", p)


def test_both_rails_name_a_producer():
    for name in ("ordered_standby_hold", "replication_live_door"):
        m = rail(name).measure
        assert m in mg.MEASURES and m != "measure_veto" and m in mg.DIRECT_MEASURES


def test_nothing_held_is_not_binding(tmp_path, monkeypatch):
    _book(tmp_path, monkeypatch, [{"name": "x", "status": "LIVE"}])
    for fn in (mg.measure_ordered_standby_hold, mg.measure_replication_live_door):
        assert fn(None, ALLOC, {})["verdict"] == mg.NOT_BINDING


def test_few_held_rows_are_unmeasured_with_the_count(tmp_path, monkeypatch):
    _book(tmp_path, monkeypatch, [{"name": "h", "status": "STANDBY", "standby_reason": "zuck",
                                   "shadow_exp": 0.3}])
    out = mg.measure_ordered_standby_hold(None, ALLOC, {})
    assert out["verdict"] == mg.UNMEASURED and out["n"] == 1 and out["names"] == ["h"]


def test_paying_held_rows_cost_growth(tmp_path, monkeypatch):
    rows = [{"name": f"r{i}", "status": "STANDBY", "shadow_exp": 0.2,
             "replication_refusal": "REFUSED_UNREPLICATED: no verdict"} for i in range(12)]
    _book(tmp_path, monkeypatch, rows)
    out = mg.measure_replication_live_door(None, ALLOC, {})
    assert out["verdict"] == mg.COSTS and out["n"] == 12
    assert out["value_logw_per_veto"] < 0
    assert mg.measure_ordered_standby_hold(None, ALLOC, {})["verdict"] == mg.NOT_BINDING


def test_losing_held_rows_earn_their_place(tmp_path, monkeypatch):
    rows = [{"name": f"r{i}", "status": "STANDBY", "standby_reason": "hold",
             "shadow_exp": -0.1} for i in range(10)]
    _book(tmp_path, monkeypatch, rows)
    assert mg.measure_ordered_standby_hold(None, ALLOC, {})["verdict"] == mg.EARNS

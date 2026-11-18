"""Participant structure (row 103): the retail-heavy cluster, its floor, the sweep honouring it."""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

DESK = Path(__file__).resolve().parents[1]
for p in (str(DESK / "research"), str(DESK), str(DESK.parents[1])):
    if p not in sys.path:
        sys.path.insert(0, p)

import breadth_ladder as bl  # noqa: E402
import participant_structure as ps  # noqa: E402

NOW = datetime(2026, 11, 18, tzinfo=UTC)


def _cot(path: Path, small: float, last: str = "2026-11-10") -> None:
    """A legacy COT file whose gross small-trader share is exactly `small`."""
    dates = pd.date_range(end=last, periods=60, freq="7D", tz="UTC")
    oi = 1000.0
    each = (1.0 - small) * 2 * oi / 4
    pd.DataFrame({"report_date": dates, "contract_market_name": "X", "open_interest_all": oi,
                  "noncomm_positions_long_all": each, "noncomm_positions_short_all": each,
                  "comm_positions_long_all": each, "comm_positions_short_all": each}
                 ).to_parquet(path)


def _tree(tmp_path: Path) -> Path:
    d = tmp_path / "cot"
    d.mkdir()
    for stem, small in (("silver", 0.30), ("gold", 0.20), ("aud", 0.15), ("gbp", 0.14),
                        ("cad", 0.12), ("nzd", 0.09)):
        _cot(d / f"{stem}.parquet", small)
    _cot(d / "sp500.parquet", 0.40, last="2021-09-14")          # stale: never tags
    return d


def test_upper_tercile_of_fresh_small_trader_share_is_the_cluster(tmp_path) -> None:
    doc = ps.build(now=NOW, cot_dir=_tree(tmp_path), axis_path=tmp_path / "none.json")
    assert doc["members"] == ["XAGUSD", "XAUUSD"]
    assert doc["tags"]["US500"] == "UNMEASURED" and doc["per_symbol"]["US500"]["status"] == "STALE"
    assert doc["tags"]["NZDUSD"] == "INSTITUTIONAL"
    assert doc["exploration_floor"]["floor"] == round(2 / 6, 3)
    assert doc["crowd"]["status"] == "UNMEASURED"
    assert doc["n_members"] == 2 and doc["n_measured"] == 6


def test_too_few_readings_publish_no_floor(tmp_path) -> None:
    d = tmp_path / "cot"
    d.mkdir()
    _cot(d / "gold.parquet", 0.2)
    doc = ps.build(now=NOW, cot_dir=d, axis_path=tmp_path / "none.json")
    assert doc["status"] == "UNMEASURED" and doc["exploration_floor"]["floor"] is None
    assert ps.cluster_floor(doc) == (set(), None)


def test_axis_net_share_is_published_but_never_tags(tmp_path) -> None:
    axis = tmp_path / "cot.json"
    axis.write_text(json.dumps({"rows": [
        {"symbol": "WHEAT", "open_interest": 100.0, "net_noncommercial": 10.0,
         "net_commercial": -30.0}]}))
    doc = ps.build(now=NOW, cot_dir=_tree(tmp_path), axis_path=axis)
    assert doc["per_symbol"]["WHEAT"]["net_small_share"] == 0.2
    assert doc["tags"]["WHEAT"] == "UNMEASURED"


def test_order_with_floor_reorders_never_filters() -> None:
    rows = [{"symbol": "EURUSD", "i": i} for i in range(8)] + \
           [{"symbol": "XAGUSD", "i": i} for i in range(8, 12)]
    out, st = ps.order_with_floor(rows, 6, {"XAGUSD"}, 0.5)
    assert len(out) == len(rows) and sorted(r["i"] for r in out) == list(range(12))
    head = out[:6]
    assert sum(r["symbol"] == "XAGUSD" for r in head) == 3 and st["moved"] == 3
    same, st2 = ps.order_with_floor(rows, 20, {"XAGUSD"}, 0.5)
    assert same == rows and st2["moved"] == 0
    same, _ = ps.order_with_floor(rows, 6, set(), None)
    assert same == rows


def test_breadth_ladder_publishes_the_cluster_floor(tmp_path) -> None:
    doc = ps.build(now=NOW, cot_dir=_tree(tmp_path), axis_path=tmp_path / "none.json")
    cf = bl.cluster_floors(doc)
    assert cf["retail_heavy"]["floor"] == doc["exploration_floor"]["floor"]
    assert cf["retail_heavy"]["members"] == ["XAGUSD", "XAUUSD"]
    assert bl.cluster_floors({})["retail_heavy"]["floor"] is None


def test_breadth_sweep_applies_the_floor_inside_its_cap(monkeypatch, tmp_path) -> None:
    import breadth_sweep as bs
    doc = ps.build(now=NOW, cot_dir=_tree(tmp_path), axis_path=tmp_path / "none.json")
    monkeypatch.setattr(ps, "load", lambda path=None: doc)
    rows = [{"symbol": "EURUSD", "i": i} for i in range(10)] + \
           [{"symbol": "XAUUSD", "i": i} for i in range(10, 14)]
    out = bs._with_cluster_floor(rows, 6)
    assert len(out) == 14
    want = round(doc["exploration_floor"]["floor"] * 6)
    assert sum(r["symbol"] == "XAUUSD" for r in out[:6]) == want
    assert bs.CLUSTER_FLOOR_STATS["moved"] >= 1

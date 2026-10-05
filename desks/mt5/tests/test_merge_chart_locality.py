"""The canonical writer must stop thrashing bars before parallel judging starts."""
import json

from research.merge_hypotheses import _chart_local_order, _write_docket_atomically


def test_locality_preserves_rows_and_attention_within_a_chart(tmp_path):
    rows = [
        {"sym": "B", "family": "carry", "params": {"timeframe": "M5"}, "rank": 0},
        {"sym": "A", "family": "carry", "params": {"timeframe": "M15"}, "rank": 1},
        {"sym": "B", "family": "formula", "params": {"timeframe": "M5"}, "rank": 2},
        {"symbol": "A", "family": "carry", "params": {}, "rank": 3},
        {"sym": "A", "family": "lvc_asia_london", "params": {}, "rank": 4},
    ]
    before = json.dumps(rows, sort_keys=True)
    ordered = _chart_local_order(rows)
    assert [r["rank"] for r in ordered] == [3, 1, 4, 0, 2]
    assert {id(r) for r in rows} == {id(r) for r in ordered}
    assert json.dumps(rows, sort_keys=True) == before
    target = tmp_path / "docket.json"
    _write_docket_atomically(target, rows)
    assert json.loads(target.read_text()) == ordered


def test_row_charts_follow_native_loader_precedence_and_keep_stable_attention():
    rows = [
        {"symbol": "A", "family": "carry", "timeframe": "m15", "rank": 0},
        {"symbol": "A", "family": "carry", "timeframe": "h1", "rank": 1},
        {"symbol": "A", "family": "carry", "timeframe": "H4",
         "params": {"timeframe": "M15"}, "rank": 2},
        {"symbol": "A", "family": "lvc_asia_london", "timeframe": "H4", "rank": 3},
        {"symbol": "A", "family": "carry", "timeframe": "M15", "rank": 4},
        {"symbol": "A", "family": "carry", "timeframe": "M15",
         "params": {"timeframe": ""}, "rank": 5},
    ]
    before = json.dumps(rows, sort_keys=True)
    ordered = _chart_local_order(rows)
    assert [r["rank"] for r in ordered] == [1, 5, 0, 2, 4, 3]
    assert {id(r) for r in ordered} == {id(r) for r in rows}
    assert json.dumps(rows, sort_keys=True) == before

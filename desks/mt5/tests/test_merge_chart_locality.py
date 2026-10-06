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


def test_locality_holds_inside_value_bands_so_a_prefix_keeps_the_top_cells():
    # a value-ordered docket: rank 0 is the most valuable; symbols interleave by value
    syms = ["ZARJPY", "AUDCAD", "XAUUSD", "EURUSD"]
    rows = [{"sym": syms[i % 4], "family": "carry", "params": {"timeframe": "H1"}, "rank": i}
            for i in range(40)]
    ordered = _chart_local_order(rows, block=8)
    assert len(ordered) == len(rows) and {id(r) for r in ordered} == {id(r) for r in rows}
    # every prefix of whole blocks holds exactly the top-valued cells
    for k in range(8, 41, 8):
        assert {r["rank"] for r in ordered[:k]} == set(range(k))
    # and each block is chart-local: one run per (symbol, chart)
    for start in range(0, 40, 8):
        block = [(r["sym"], "H1") for r in ordered[start:start + 8]]
        runs = [b for i, b in enumerate(block) if i == 0 or b != block[i - 1]]
        assert len(runs) == len(set(block))
    # one global sort (the old behaviour) loses the value head to the alphabet
    whole = _chart_local_order(rows, block=len(rows))
    assert {r["rank"] for r in whole[:8]} != set(range(8))


def test_block_size_is_measured_or_declared(monkeypatch):
    from research import merge_hypotheses as mh
    monkeypatch.setenv("QUANT_CHART_LOCAL_BLOCK", "333")
    assert mh.chart_local_block() == (333, "QUANT_CHART_LOCAL_BLOCK")

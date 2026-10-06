"""Coverage must join verdicts and parked builds in the sealed judge's key space."""
import sys
from pathlib import Path

import pytest

DESK = Path(__file__).resolve().parents[1]
if str(DESK) not in sys.path:
    sys.path.insert(0, str(DESK))

from research import judge_coverage as coverage  # noqa: E402
from research.frontier_identity import cell_id, docket_cell_id  # noqa: E402


@pytest.mark.parametrize("row", [
    {"symbol": "GBPAUD", "family": "cross_asset_residual", "timeframe": "M15",
     "params": {"factor_symbols": ["EURUSD"]}},
    {"symbol": "UK100", "family": "exogenous_conditioner", "timeframe": "H1",
     "params": {"timeframe": "M1", "x": 1}},
    {"symbol": "USDJPY", "family": "session_range_breakout", "timeframe": "H1",
     "params": {"rr": 2.5, "wait_bars": 12}},
])
def test_coverage_joins_the_actual_judge_identity_without_mutating_the_spec(row):
    import copy

    original = copy.deepcopy(row)
    # This is the chart folding performed by external_gauntlet.main.
    params = dict(row["params"])
    tf = str(row.get("timeframe") or "").upper()
    if tf and tf != "H1" and "timeframe" not in params:
        params["timeframe"] = tf
    judged = cell_id({"sym": row["symbol"], "family": row["family"], "params": params})
    assert coverage._cell_id(row) == judged == docket_cell_id(row)
    assert row == original


def test_chart_on_row_and_in_params_share_identity_but_different_charts_do_not():
    row = {"symbol": "XAUUSD", "family": "carry", "params": {}, "timeframe": "M15"}
    in_params = {**row, "timeframe": "H1", "params": {"timeframe": "M15"}}
    assert coverage._cell_id(row) == coverage._cell_id(in_params)
    assert coverage._cell_id(row) != coverage._cell_id({**row, "timeframe": "H1"})

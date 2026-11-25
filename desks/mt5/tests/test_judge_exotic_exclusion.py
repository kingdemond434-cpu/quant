"""Exotic cells get no judge slot: set aside by name (EXOTIC_BANNED), kept, never a trial."""
from __future__ import annotations

import sys
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import judge_exotic_exclusion as jee  # noqa: E402


def _ex(sym: str) -> bool:
    return sym in {"USDZAR", "EURTRY"}


def test_exotics_set_aside_by_name_and_counted():
    rows = [{"sym": "EURUSD", "family": "carry"}, {"symbol": "USDZAR", "family": "carry"},
            {"sym": "EURTRY", "family": "cot_net_fade"}, {"sym": "XAUUSD", "family": "carry"}]
    keep, aside, rep = jee.split(rows, "2026-11-25T00:00:00+00:00", is_exotic=_ex)
    assert [jee.row_symbol(r) for r in keep] == ["EURUSD", "XAUUSD"]
    assert len(aside) == 2 and all(r["excluded_reason"] == "EXOTIC_BANNED" for r in aside)
    assert rep["count"] == 2 and rep["reason"] == "EXOTIC_BANNED"
    assert rep["charged_as_trial"] is False
    assert rep["by_family"] == {"carry": 1, "cot_net_fade": 1}
    assert len(keep) + len(aside) == len(rows)


def test_set_aside_round_trip_reoffers_rows_unstamped(tmp_path):
    p = tmp_path / jee.SET_ASIDE_NAME
    _, aside, _ = jee.split([{"sym": "USDZAR", "family": "carry"}], "t", is_exotic=_ex)
    jee.write_set_aside(p, aside)
    back = jee.read_set_aside(p)
    assert back == [{"sym": "USDZAR", "family": "carry"}]


def test_fault_keeps_every_row():
    def boom(_s: str) -> bool:
        raise RuntimeError("registry")
    rows = [{"sym": "USDZAR"}]
    keep, aside, rep = jee.split(rows, "t", is_exotic=boom)
    assert keep == rows and aside == [] and rep["status"].startswith("FAILED")


def test_judged_split_by_cell_symbol():
    out = jee.judged_split({"USDZAR.carry.p=1", "EURUSD.carry.p=2", "EURUSD.x.p=3"},
                           is_exotic=_ex)
    assert out["judged_cells_exotic"] == 1 and out["judged_cells_non_exotic"] == 2


def test_real_classifier_matches_universe_policy():
    from research.universe_policy import is_exotic_symbol
    for sym in ("USDZAR", "EURUSD", "BTCUSD", "XAUUSD"):
        _k, aside, _r = jee.split([{"sym": sym}], "t")
        assert bool(aside) == bool(is_exotic_symbol(sym))

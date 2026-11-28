"""A coevolved survivor reaches the judge with params its family actually reads.

2026-11-04: the cell passed the factor grammar's names (`w`, `h`, `fast`) into families that read
none of them, so `range_reversion {w: 48}` ran as the default `range_reversion` cell. Every
survivor of every op was fake breadth: a trial charged for a cell already judged.
"""
from __future__ import annotations

import inspect
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
for _p in (str(BASE), str(BASE.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mt5desk.families import get_family_func  # noqa: E402
from research.sandboxes import coevolution_cell as CO  # noqa: E402


def test_every_translated_param_is_a_kwarg_of_the_target_family() -> None:
    for op, names in CO.PARAM_OF_OP.items():
        fn = get_family_func(CO.FAMILY_OF_OP[op])
        assert fn is not None, op
        kwargs = set(inspect.signature(fn).parameters)
        for dst in names.values():
            assert dst in kwargs, (op, dst)


def test_every_grammar_op_has_a_translation() -> None:
    for op, grid in CO.GRAMMAR:
        params, rest = CO.family_params(op, {k: v[0] for k, v in grid.items()})
        assert params, op
        assert set(params) | set(rest) and len(params) + len(rest) == len(grid)


def test_range_pos_window_becomes_range_n() -> None:
    params, rest = CO.family_params("range_pos", {"w": 48})
    assert params == {"range_n": 48} and rest == {}
    params, rest = CO.family_params("vol_ratio", {"w1": 24, "w2": 240})
    assert params == {"lookback": 240} and rest == {"w1": 24}

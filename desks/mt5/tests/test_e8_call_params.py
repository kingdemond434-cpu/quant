"""An E8 sleeve must be called with the parameters its certificate was earned on.

TWENTY SLEEVES REPORTED NO_SIGNAL EVERY PASS (measured 2026-09-14). The guard was green --
`may_open: true`, equity 100,000, day_pnl 0.0, 2,500 to the daily floor and 10,000 to the static
one -- the lane was armed (`armed_by: E8_ARMED present`), 20 sleeves were considered, and
`n_sent` was 0 with every row reading NO_SIGNAL.

TWO FAULTS, EITHER ONE FATAL ALONE.

  1. `e8_book` writes the docket row's envelope through unchanged:
         {"condition": null, "params": {"feature": "dd_24", "band": [0.75, 0.9], ...}}
     and the executor spread the OUTER dict, offering `condition=` and `params=` to a family
     that takes neither.

  2. The filter kept only scalars, so `condition` (None) and the inner dict were both dropped,
     leaving {} and falling through to the unparameterised `func(closed)` branch. That filter
     would have been fatal even with the nesting fixed: `band` is a LIST.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "prop")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

e8 = pytest.importorskip("prop.e8_executor")


def test_the_nested_envelope_is_unwrapped():
    s = {"params": {"condition": None,
                    "params": {"feature": "dd_24", "band": [0.75, 0.9],
                               "horizon": 6, "side": -1}}}
    got = e8._call_params(s)
    assert got == {"feature": "dd_24", "band": [0.75, 0.9], "horizon": 6, "side": -1}


def test_a_list_valued_param_survives():
    """`band` is a list. The old scalar-only filter dropped it, and a `discovered` cell without
    its band selects no rows at all -- so this is the difference between signals and silence."""
    got = e8._call_params({"params": {"feature": "x", "band": [0.9, 1.0], "horizon": 1}})
    assert got["band"] == [0.9, 1.0]


def test_flat_params_still_work():
    """A producer writing params flat must keep working: the unwrap is by SHAPE, not by family."""
    got = e8._call_params({"params": {"feature": "dd_24", "horizon": 6}})
    assert got == {"feature": "dd_24", "horizon": 6}


def test_identity_keys_are_stripped():
    """`timeframe` names the chart to LOAD; no family takes it as an argument."""
    got = e8._call_params({"params": {"feature": "x", "timeframe": "M15"}})
    assert "timeframe" not in got
    assert got["feature"] == "x"


def test_a_missing_or_malformed_params_block_is_empty_not_a_crash():
    assert e8._call_params({}) == {}
    assert e8._call_params({"params": None}) == {}
    assert e8._call_params({"params": "nonsense"}) == {}

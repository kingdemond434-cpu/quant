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


def test_resolved_inputs_are_cached_within_a_pass(monkeypatch):
    """`resolve` hits the venue for peer, factor and macro series, and sleeves share drivers.

    Called blind it refetches the identical series for every cell that names it, which took this
    executor from about six minutes a pass to eleven when the call was added. Two sleeves agreeing
    on symbol, family and params must resolve ONCE.
    """
    calls = []

    def _fake_resolve(sym, family, params, bars):
        calls.append((sym, family))
        return {"extra": {"series": 1}}, ""

    import mt5desk.family_inputs as fi
    monkeypatch.setattr(fi, "resolve", _fake_resolve)
    e8._INPUT_CACHE.clear()
    s = {"symbol": "EURAUD", "family": "discovered",
         "params": {"params": {"feature": "ext_residz_AUDCAD", "band": [0.0, 0.1]}}}
    a = e8._call_params(s, "EURAUD", bars=object())
    b = e8._call_params(dict(s), "EURAUD", bars=object())
    assert a == b
    assert len(calls) == 1, f"resolve must be called once for identical inputs, got {len(calls)}"


def test_the_cache_does_not_outlive_the_pass():
    """A cache that outlives its bar feeds this hour's decision from last hour's data."""
    e8._INPUT_CACHE["stale"] = ({"extra": "old"}, "")
    e8._INPUT_CACHE.clear()
    assert e8._INPUT_CACHE == {}


def test_a_refusal_is_cached_as_a_refusal_not_dropped(monkeypatch):
    """A cell whose inputs cannot be rebuilt must stay refused on the second call too."""
    import mt5desk.family_inputs as fi
    monkeypatch.setattr(fi, "resolve", lambda *a, **k: (None, "peer bars unavailable"))
    e8._INPUT_CACHE.clear()
    s = {"symbol": "X", "family": "discovered", "tag": "T",
         "params": {"params": {"feature": "f"}}}
    assert e8._call_params(s, "X", bars=object()) is None
    assert e8._call_params(dict(s), "X", bars=object()) is None

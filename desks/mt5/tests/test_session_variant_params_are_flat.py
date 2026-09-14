"""A session/chart variant must carry FLAT params, or nothing can build it.

EVERY VARIANT THIS GENERATOR EMITTED WAS UNBUILDABLE (measured 2026-09-14). A certificate's
`shadow_spec` carries the docket envelope -- `{"condition": null, "params": {...}}` -- and copying
it through produced variants whose params read:

    {"condition": null, "params": {"rr": 1.5, "wait_bars": 12}, "range_start": 19}

`build_cell` is handed `condition=` and `params=` instead of `rr=` and `wait_bars=`, and refuses.
The gauntlet recorded all 1,090 as NOT_RUN_BUILD_FAILED: 996 session_range_breakout, 63
overnight_gap_decay, 26 spread_state, 5 carry -- days on the docket with not one gate ever run on
them. Unwrapped, the same cells build and carry ~3,600 signals each.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

sce = pytest.importorskip("research.session_chart_equivalents")


def test_the_docket_envelope_is_unwrapped():
    got = sce._flat_params({"condition": None, "params": {"rr": 1.5, "wait_bars": 12},
                            "range_start": 19})
    assert got == {"rr": 1.5, "wait_bars": 12, "range_start": 19}
    assert "params" not in got and "condition" not in got


def test_flat_params_pass_through_unchanged():
    """Unwrapped by SHAPE, not by family: a producer writing flat params must keep working."""
    flat = {"rr": 2.0, "wait_bars": 8, "range_start": 7}
    assert sce._flat_params(dict(flat)) == flat


def test_an_outer_key_survives_the_unwrap():
    """`range_start` sits OUTSIDE the envelope and is the hour the variant varies -- losing it
    would make every variant of a parent identical to the parent."""
    got = sce._flat_params({"params": {"rr": 1.5}, "range_start": 21, "timeframe": "M15"})
    assert got["range_start"] == 21
    assert got["timeframe"] == "M15"
    assert got["rr"] == 1.5


def test_an_inner_key_wins_over_a_stale_outer_one():
    """The envelope's inner block is the parameterisation the certificate was earned on."""
    got = sce._flat_params({"params": {"rr": 1.5}, "rr": 99})
    assert got["rr"] == 1.5


def test_empty_and_malformed_specs_do_not_raise():
    assert sce._flat_params({}) == {}
    assert sce._flat_params({"params": None}) == {}
    assert sce._flat_params({"params": "nonsense"}) == {}

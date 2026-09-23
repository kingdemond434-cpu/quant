"""A certified survivor can now be re-judged with a condition REMOVED (Tier-1 audit G19).

The distiller only ever stepped parameters toward the survivor median -- it added neighbours and
never subtracted terms -- so a certified cell carrying a condition that contributes nothing kept
carrying it, and every condition is a place the fit could have been to noise. What is pinned: a
droppable condition is one the family's OWN signature gives a default for, dropping it produces
an executable cell that falls back to that default, the instrument and its data sources are never
dropped, the operator is `drop_<param>` (which mutation_yield already bills), and history is
never re-proposed.
"""
from __future__ import annotations

import sys
from pathlib import Path

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mt5desk import families_orthogonal as fo  # noqa: E402

from libs.research.hypothesis_graph import node_id  # noqa: E402
from research import survivor_distiller as sd  # noqa: E402


def _cert(**kw) -> dict:
    base = {"key": "external.XAUUSD.carry.1", "id": "nid-parent", "symbol": "XAUUSD",
            "family": "carry", "mechanism": "carry on XAUUSD: financing differential"}
    base.setdefault("params", {"require_quiet": False, "rr": 2.5, "min_edge_bp_per_day": 0.9,
                               "input_symbol": "XAUUSD", "atr_n": 14})
    base.update(kw)
    return base


# --------------------------------------------------------------------------- what is droppable
def test_a_droppable_condition_is_one_the_family_gives_a_default_for() -> None:
    got = sd.droppable("carry", _cert()["params"])
    sig = fo.family_carry.__kwdefaults__
    assert set(got) == {"require_quiet", "rr", "min_edge_bp_per_day"}
    assert got["require_quiet"] == sig["require_quiet"] is True
    assert got["rr"] == sig["rr"]


def test_the_instrument_its_sources_and_the_atr_window_are_never_dropped() -> None:
    got = sd.droppable("carry", _cert()["params"])
    for frozen in ("input_symbol", "atr_n"):
        assert frozen not in got, f"{frozen} names the cell; removing it is a new hypothesis"
    assert "atr_n" in sd.FROZEN and "input_symbol" in sd.FROZEN


def test_a_param_already_at_its_default_is_not_a_condition_to_drop() -> None:
    """Dropping it would produce the same cell under a new name -- a trial spent on nothing."""
    params = {"rr": fo.family_carry.__kwdefaults__["rr"], "require_quiet": False}
    got = sd.droppable("carry", params)
    assert set(got) == {"require_quiet"}


def test_a_key_the_family_does_not_accept_is_identity_not_a_condition() -> None:
    got = sd.droppable("carry", {"timeframe": "M5", "rr": 2.5})
    assert "timeframe" not in got and "rr" in got


def test_an_unregistered_family_yields_nothing_rather_than_a_guess() -> None:
    assert sd.droppable("no_such_family", {"rr": 2.5}) == {}
    assert sd.simplify(_cert(family="no_such_family")) == []


# --------------------------------------------------------------------------- the proposals
def test_one_cell_per_condition_with_that_condition_dropped() -> None:
    cert = _cert()
    rows = sd.simplify(cert)
    assert {r["operator"] for r in rows} == {"drop_require_quiet", "drop_rr",
                                             "drop_min_edge_bp_per_day"}
    for r in rows:
        name = r["operator"].removeprefix("drop_")
        assert name not in r["params"], "the condition is still on the cell"
        assert set(r["params"]) == set(cert["params"]) - {name}
        assert r["symbol"] == "XAUUSD" and r["family"] == "carry"
        assert r["parent"] == cert["key"] and r["parent_id"] == cert["id"]
        assert r["id"] == node_id("XAUUSD", "carry", r["params"])
        assert r["dropped"]["was"] == cert["params"][name]
        assert r["dropped"]["falls_back_to"] == fo.family_carry.__kwdefaults__[name]
        assert name in r["mechanism"] and "dropped" in r["mechanism"]


def test_the_simplified_cell_is_executable_and_means_what_it_says() -> None:
    """Dropping a key IS what the gauntlet, the forward engine and the gateway do with an
    absent one: the family falls back to its own default. So the proposal must run."""
    import numpy as np
    import pandas as pd
    n = 3000
    rng = np.random.default_rng(2)
    close = 100 + np.cumsum(rng.normal(0, 0.3, n))
    o = np.concatenate([[100.0], close[:-1]])
    idx = pd.date_range("2024-01-01", periods=n, freq="1h", tz="UTC")
    bars = pd.DataFrame({"open": o, "high": np.maximum(o, close) + 0.3,
                         "low": np.minimum(o, close) - 0.3, "close": close}, index=idx)
    cert = _cert(family="drawdown_conditional",
                 params={"lookback": 480, "dd_pct": 0.02, "rr": 3.0})
    rows = sd.simplify(cert)
    assert rows
    for r in rows:
        got = fo.ORTHOGONAL_FAMILIES["drawdown_conditional"](bars, **r["params"])
        assert isinstance(got, list)
    # And the dropped param genuinely changes the cell: with dd_pct dropped the family uses its
    # own 0.05 threshold, which is a different set of entries from 0.02.
    with_it = fo.family_drawdown_conditional(bars, **cert["params"])
    dropped = next(r for r in rows if r["operator"] == "drop_dd_pct")
    without = fo.family_drawdown_conditional(bars, **dropped["params"])
    assert len(with_it) != len(without)


def test_a_cell_the_graph_already_holds_is_history_not_a_proposal() -> None:
    cert = _cert()
    first = sd.simplify(cert)
    seen = {r["id"] for r in first}
    assert sd.simplify(cert, seen) == []
    # ... and one already-known id removes only its own row.
    one = next(iter(seen))
    again = sd.simplify(cert, {one})
    assert len(again) == len(first) - 1 and all(r["id"] != one for r in again)


def test_the_operator_weights_rank_the_drops_and_default_to_one() -> None:
    rows = sd.simplify(_cert(), None, {"drop_rr": 3.0})
    by_op = {r["operator"]: r["score"] for r in rows}
    assert by_op["drop_rr"] == 3.0
    assert by_op["drop_require_quiet"] == 1.0, "an unbilled operator is neutral, never zero"


def test_a_certificate_with_nothing_droppable_yields_nothing() -> None:
    assert sd.simplify(_cert(params={"input_symbol": "XAUUSD"})) == []
    assert sd.simplify(_cert(params={})) == []
    assert sd.simplify({"family": "carry", "symbol": "", "params": {"rr": 2.0}}) == []


# --------------------------------------------------------------------------- the wiring
def test_the_run_puts_simplifications_through_the_same_door() -> None:
    import inspect
    src = inspect.getsource(sd.run)
    assert "simplify(c, existing, weights)" in src
    assert "neighbours.extend(simplifications)" in src, (
        "simplifications must be screened, deflated and donated as neighbours are")
    assert "simplifications_generated" in src and "dropped_params" in src


def test_the_operator_name_is_the_one_mutation_yield_bills() -> None:
    """`mutation_yield` joins a lineage row to its verdict by node id and tallies by operator;
    the distiller's own docstring names step_/swap_ and this adds drop_."""
    rows = sd.simplify(_cert())
    assert all(r["operator"].startswith("drop_") for r in rows)
    from research import mutation_yield as my
    assert "survivor_distiller" in my.LINEAGE_SOURCES

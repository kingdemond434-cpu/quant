"""The decision core is IMPORTED here, on Linux, and every branch of it is driven.

WHY THESE TESTS LOOK DIFFERENT FROM THE REST OF THIS DIRECTORY. Until the split, the gateway's
sizing, heat, roster, bracket and gate logic could only be tested by AST-extracting functions
out of `gateway.py`'s source and exec'ing them under a compiled string, because the module
imports MetaTrader5 at the top. That tested the code and attributed the execution to nothing:
branch coverage of the capital-moving file read 0.6% while the proof sat in a dozen files.
`mt5desk.decision_core` imports on any host, so this file imports it -- and coverage.py sees
every branch it takes.

What is pinned, by section: the sizing laws and their edges (floor, ceiling, ramp ladder, fade,
the allocator's un-shrunk fraction, zero heat, unpriceable instruments); the heat cap's ordering
and admission rules with and without an allocator verdict; the artifact readers failing closed on
every doubt; roster admission and its refusals; the state gate; bracket arithmetic from bars; the
retcode diagnosis and pause verdict; the per-session bracket deadline; the execution context; the
release gate's refusal default; and the family and scalp lanes' pure decision steps.
"""
from __future__ import annotations

import json
import math
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from mt5desk import decision_core as dc  # noqa: E402
from mt5desk import risk_units as ru  # noqa: E402
from mt5desk import sizing  # noqa: E402
from mt5desk.gateway_config_fallback import HEAT_TARGET, Q_OPT  # noqa: E402

EQ = 1683.89


class _Info:
    """A live `symbol_info` stand-in, duck-typed exactly as the gateway passes it."""

    def __init__(self, tick_size=0.01, tick_value=1.0, vmin=0.01, vstep=0.01, stops_level=20):
        self.trade_tick_size = tick_size
        self.trade_tick_value = tick_value
        self.volume_min = vmin
        self.volume_step = vstep
        self.trade_stops_level = stops_level


# =========================================================================== the module itself

def test_the_core_imports_without_the_broker_library() -> None:
    """THE POINT OF THE SPLIT. No MetaTrader5 anywhere in the import chain, so this host -- and
    the coverage report -- can execute the decisions the gateway sends.

    IMPORTED FOR REAL, WITH THE LIBRARY BANNED, NOT JUST READ. An AST scan of this one file
    proves nothing about the chain BELOW it: `gateway_config_fallback`, `sizing` and anything
    they pull are equally part of `import mt5desk.decision_core`, and one module-scope
    `import MetaTrader5` down there would take the core off every host but the box while every
    source scan still read clean. So this purges the core and its package from `sys.modules`,
    installs a finder that REFUSES MetaTrader5 the way a Linux runner does, and imports it
    fresh. The ban is removed and the module restored afterwards, whatever happens.
    """
    import ast
    import importlib

    class _NoBroker:
        """A meta-path finder that makes MetaTrader5 unimportable, as it is on this host."""

        def find_module(self, fullname, path=None):        # pragma: no cover - legacy protocol
            return None

        def find_spec(self, fullname, path=None, target=None):
            if fullname == "MetaTrader5" or fullname.startswith("MetaTrader5."):
                raise ImportError("MetaTrader5 is Windows-only; the core must not need it")
            return None

    saved = {k: v for k, v in sys.modules.items()
             if k == "MetaTrader5" or k.startswith("mt5desk")}
    guard = _NoBroker()
    sys.meta_path.insert(0, guard)
    try:
        for name in saved:
            del sys.modules[name]
        fresh = importlib.import_module("mt5desk.decision_core")
        assert fresh.GOLD_SYMBOL == "XAUUSD" and callable(fresh.promoted_lot)
        assert "MetaTrader5" not in sys.modules
    finally:
        sys.meta_path.remove(guard)
        sys.modules.update(saved)

    tree = ast.parse((_DESK / "mt5desk" / "decision_core.py").read_text("utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(a.name != "MetaTrader5" for a in node.names)
        if isinstance(node, ast.ImportFrom):
            assert node.module != "MetaTrader5"
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            assert node.value.id != "mt5", "the core reached for the terminal"


def test_the_gateway_is_the_only_module_here_that_reaches_the_terminal() -> None:
    """One file pays the Windows tax, and it is the venue adapter.

    The claim is about `mt5desk/` -- the package the money path imports -- and about MODULE
    SCOPE, which is what decides whether a file can be imported at all on a runner. `tape.py`
    and the research fetchers import the broker library INSIDE a function on purpose: the module
    loads anywhere and only the call needs the terminal. If a second module here ever takes the
    import to the top, everything that imports it leaves the coverage report the same way the
    gateway did, and this says so by name.
    """
    import ast
    offenders = []
    for path in sorted((_DESK / "mt5desk").glob("*.py")):
        tree = ast.parse(path.read_text("utf-8"))
        for node in tree.body:                       # module scope only, deliberately
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            if any(n == "MetaTrader5" or n.startswith("MetaTrader5.") for n in names):
                offenders.append(path.name)
    assert offenders == ["gateway.py"], f"module-scope MetaTrader5 imports: {offenders}"


def test_every_decision_that_moved_is_still_reachable_through_the_gateway() -> None:
    """CALLERS DID NOT MOVE. `research/allocation.py`, `pf_allocator`, `portfolio_gap`,
    `regime_monitor` and the desk's own scripts read these names off `mt5desk.gateway`, and the
    split may not quietly take one away -- a rename that only the core knows about is an
    ImportError on the box, at import time, on the file that places orders.

    Read from the gateway's AST because the module cannot be imported here (MetaTrader5). Every
    public function and constant the core defines must be bound at the gateway's module scope,
    by re-export or by a delegating `def`.
    """
    import ast
    core_tree = ast.parse((_DESK / "mt5desk" / "decision_core.py").read_text("utf-8"))
    gw_tree = ast.parse((_DESK / "mt5desk" / "gateway.py").read_text("utf-8"))
    wanted = {n.name for n in core_tree.body
              if isinstance(n, ast.FunctionDef) and not n.name.startswith("_")}
    wanted |= {t.id for n in core_tree.body if isinstance(n, ast.Assign)
               for t in n.targets if isinstance(t, ast.Name) and not t.id.startswith("_")}
    bound: set[str] = set()
    for n in gw_tree.body:
        if isinstance(n, ast.ImportFrom):
            bound |= {a.asname or a.name for a in n.names}
        elif isinstance(n, ast.Import):
            bound |= {a.asname or a.name.split(".")[0] for a in n.names}
        elif isinstance(n, ast.FunctionDef):
            bound.add(n.name)
        elif isinstance(n, ast.Assign):
            bound |= {t.id for t in n.targets if isinstance(t, ast.Name)}
    # `load_retired_gold` and `ACCEPTED_RETCODES` were never on the gateway's surface: the
    # gateway binds the reader as the private `_load_retired_gold` (it supplies the path) and
    # has always spelled the accepted retcodes inline at its one call site.
    exempt = {"load_retired_gold", "ACCEPTED_RETCODES"}
    assert (wanted - exempt) <= bound, f"lost from the gateway: {sorted(wanted - exempt - bound)}"
    assert "_load_retired_gold" in bound


def test_the_budget_is_imported_not_restated() -> None:
    assert dc.Q_OPT == Q_OPT and dc.HEAT_TARGET == HEAT_TARGET
    assert dc.MAX_HEAT_CEILING == dc.HEAT_HARD_CEILING == 0.30
    assert dc.MIN_LOT_RISK_EUR == pytest.approx(0.01 * dc.DIST_USD * dc.CONTRACT_OZ * dc.FX_EUR)


# ================================================================================= sizing laws

def test_lot_steps_snap_down_never_up() -> None:
    assert dc._lot_steps(0.0199) == pytest.approx(0.01)
    assert dc._lot_steps(0.02) == pytest.approx(0.02)
    assert dc._lot_steps(0.0) == 0.0


def test_stop_distance_reads_either_leg_and_refuses_a_degenerate_spec() -> None:
    assert dc.stop_distance({"buy_stop": {"price": 100.0, "sl": 90.0}}) == pytest.approx(10.0)
    # buy leg unusable (no sl), sell leg carries the stop
    assert dc.stop_distance({"buy_stop": {"price": 100.0},
                             "sell_stop": {"price": 80.0, "sl": 85.0}}) == pytest.approx(5.0)
    assert dc.stop_distance({"buy_stop": {"price": 100.0, "sl": 100.0}}) is None
    assert dc.stop_distance({}) is None and dc.stop_distance(None) is None


def test_eur_per_price_unit_falls_back_to_gold_alone(monkeypatch) -> None:
    assert dc._eur_per_price_unit("XAUUSD") == pytest.approx(86.414, rel=1e-2)
    assert dc._eur_per_price_unit("XAUUSD", _Info(0.01, 1.0)) == pytest.approx(100.0)

    def _blind(symbol, info=None):
        raise ru.RiskUnitUnmeasured("no tick data anywhere")
    monkeypatch.setattr(ru, "eur_per_price_unit", _blind)
    assert dc._eur_per_price_unit("XAUUSD") == pytest.approx(dc.CONTRACT_OZ * dc.FX_EUR)
    with pytest.raises(ru.RiskUnitUnmeasured):
        dc._eur_per_price_unit("CADJPY")


def test_min_lot_risk_reads_fresh_and_defaults_the_house_distance() -> None:
    pu = dc._eur_per_price_unit("XAUUSD")
    assert dc.min_lot_risk_eur() == pytest.approx(0.01 * dc.DIST_USD * pu)
    assert dc.min_lot_risk_eur("XAUUSD", 53.4) == pytest.approx(0.01 * 53.4 * pu)
    assert dc.min_lot_risk_eur("XAUUSD", 0) == dc.min_lot_risk_eur("XAUUSD", None)


def test_auto_lot_floors_ceils_and_takes_q_or_the_house_policy() -> None:
    pu = dc._eur_per_price_unit("XAUUSD")
    raw = Q_OPT * 25_000.0 / (53.4 * pu)
    assert dc.auto_lot(25_000.0, 53.4) == pytest.approx(math.floor(raw / 0.01 + 1e-9) * 0.01)
    assert dc.auto_lot(25_000.0, 53.4, q=None) == dc.auto_lot(25_000.0, 53.4, q=0.0)
    assert dc.auto_lot(25_000.0, 53.4, q=2 * Q_OPT) > dc.auto_lot(25_000.0, 53.4)
    assert dc.auto_lot(10.0, 53.4) == 0.01                          # the venue floor
    assert dc.auto_lot(1e9, 1.0) == 5.0                             # the ceiling
    assert dc.auto_lot(25_000.0) == dc.auto_lot(25_000.0, dc.DIST_USD)
    with pytest.raises(ru.RiskUnitUnmeasured):
        dc.auto_lot(EQ, 0.5, "NOSUCHPAIR")


def test_realised_q_reports_the_lot_actually_taken() -> None:
    pu = dc._eur_per_price_unit("XAUUSD")
    assert dc.realised_q(300.0, 53.4) == pytest.approx(0.01 * 53.4 * pu / 300.0, rel=1e-6)
    assert dc.realised_q(EQ, 0.5, "CADJPY", None, lot=0.18) == pytest.approx(
        ru.realised_risk_eur("CADJPY", 0.5, 0.18) / EQ, rel=1e-6)
    assert dc.realised_q(0.0, 53.4) == 0.0
    assert dc.realised_q(25_000.0, None) == dc.realised_q(25_000.0, dc.DIST_USD)


def test_ramped_fraction_is_the_one_ladder() -> None:
    """THE ONE EXPRESSION THE SPLIT REWROTE RATHER THAN MOVED, so it is pinned against the
    pre-split source it replaced. `promoted_lot` used to compute
    `clamp_risk_frac(risk_frac) * ramp * decay_factor(decay_faded)` inline with its own copy of
    the 0.25/0.5/1.0 ladder; naming it made the heat cap bill the same number the order is sized
    at, and the two must still agree to the float."""
    for rf in (None, 0.03, 0.06, 0.99, "junk"):
        for live_n in (0, 49, 50, 199, 200, 10_000):
            for faded in (None, "2026-08-29"):
                ramp = 0.25 if live_n < 50 else (0.5 if live_n < 200 else 1.0)
                assert dc.ramped_fraction(rf, live_n, faded) == (
                    sizing.clamp_risk_frac(rf) * ramp * sizing.decay_factor(faded))
    for live_n, ramp in ((0, 0.25), (49, 0.25), (50, 0.5), (199, 0.5), (200, 1.0), (10_000, 1.0)):
        assert dc.ramped_fraction(None, live_n) == pytest.approx(sizing.BASE_RISK_FRAC * ramp)
    assert dc.ramped_fraction(0.06, 500) == pytest.approx(0.06)
    assert dc.ramped_fraction(0.99, 500) == pytest.approx(sizing.MAX_RISK_FRAC)
    assert dc.ramped_fraction(0.06, 500, "2026-08-29") == pytest.approx(0.06 * sizing.FADE_FACTOR)
    assert dc.ramped_fraction("junk", 500) == pytest.approx(sizing.BASE_RISK_FRAC)


def test_promoted_lot_ramps_fades_floors_and_ceils(monkeypatch) -> None:
    monkeypatch.setattr(dc, "auto_lot", lambda equity, dist, symbol, info, q: q * 100.0)
    lot = dc.promoted_lot
    # The ladder in equity terms: 0.75% / 1.5% / 3% of a 3% base.
    assert lot(1000.0, 3, 10.0, "EURUSD", None, 0.03, None) == pytest.approx(0.75)
    assert lot(1000.0, 60, 10.0, "EURUSD", None, 0.03, None) == pytest.approx(1.5)
    assert lot(1000.0, 500, 10.0, "EURUSD", None, 0.03, None) == pytest.approx(3.0)
    # The fade halves, outside the clamp, so a faded 3% sleeve sizes at 1.5%.
    assert lot(1000.0, 500, 10.0, "EURUSD", None, 0.03, "2026-08-29") == pytest.approx(1.5)
    # The ceiling and the floor.
    assert lot(1000.0, 500, 10.0, "EURUSD", None, 0.10, None) == 5.0
    monkeypatch.setattr(dc, "auto_lot", lambda equity, dist, symbol, info, q: 0.0)
    assert lot(1000.0, 500, 10.0, "EURUSD", None, 0.03, None) == 0.01
    # FLOOR, not nearest: 0.0199 lots is 0.01, never 0.02.
    monkeypatch.setattr(dc, "auto_lot", lambda equity, dist, symbol, info, q: 0.0199)
    assert lot(1000.0, 500, 10.0, "EURUSD", None, 0.03, None) == pytest.approx(0.01)


def test_the_books_fraction_reaches_the_venue_unshrunk(monkeypatch) -> None:
    """`from_book=True` applies neither the 3% floor clamp nor the authority ramp: the
    allocator's h_i was solved on worlds that already shrink by evidence. Only the fade and
    the outer per-trade envelope survive, and no heat is no lot."""
    monkeypatch.setattr(dc, "auto_lot", lambda equity, dist, symbol, info, q: q * 100.0)
    lot = dc.promoted_lot
    assert lot(1000.0, 3, 10.0, "EURUSD", None, 0.017, None, from_book=True) == pytest.approx(1.7)
    assert lot(1000.0, 3, 10.0, "EURUSD", None, 0.017, None) == pytest.approx(0.75)
    assert lot(1000.0, 3, 10.0, "EURUSD", None, 0.5, None, from_book=True) == pytest.approx(5.0)
    assert lot(1000.0, 3, 10.0, "EURUSD", None, 0.04, True, from_book=True) == pytest.approx(2.0)
    assert lot(1000.0, 3, 10.0, "EURUSD", None, 0.0, None, from_book=True) == 0.0
    assert lot(1000.0, 3, 10.0, "EURUSD", None, None, None, from_book=True) == 0.0
    assert lot(1000.0, 3, 10.0, "EURUSD", None, "x", None, from_book=True) == 0.0
    assert lot(1000.0, 3, 10.0, "EURUSD", None, -0.01, None, from_book=True) == 0.0


def test_promoted_lot_end_to_end_prices_in_the_sleeves_own_units() -> None:
    for sym, stop in (("CADJPY", 0.50), ("USDJPY", 0.60), ("EURUSD", 0.0040)):
        got = dc.promoted_lot(EQ, 500, stop, sym)
        true_risk = ru.realised_risk_eur(sym, stop, got)
        assert true_risk / EQ <= sizing.clamp_risk_frac(None) * 1.02, sym
        assert abs(got / 0.01 - round(got / 0.01)) < 1e-9
    assert dc.promoted_lot(25_000.0, 500, 53.40) < dc.promoted_lot(25_000.0, 500, 19.1)


def test_sleeve_live_n_counts_only_this_sleeves_closed_trades(tmp_path) -> None:
    p = tmp_path / "ledger.jsonl"
    assert dc.sleeve_live_n("a", p) == 0
    p.write_text('{"sleeve": "a"}\n\n{"sleeve": "b"}\nnot json\n{"sleeve": "a"}\n', "utf-8")
    assert dc.sleeve_live_n("a", p) == 2 and dc.sleeve_live_n("b", p) == 1
    assert dc.sleeve_live_n("a", tmp_path) == 0                 # unreadable: a directory


# =================================================================================== the budget

def test_heat_budget_returns_base_unless_breadth_is_measured() -> None:
    base = HEAT_TARGET
    for bad in (None, float("nan"), 0.0, 0.9):
        assert dc.heat_budget(bad) == pytest.approx(base)
    mid = dc._HEAT_BASE_KEFF * 1.2
    assert dc.heat_budget(mid) == pytest.approx(
        min(base * (mid / dc._HEAT_BASE_KEFF) ** 0.5, dc.MAX_HEAT_CEILING))
    assert dc.heat_budget(1.0) == pytest.approx(base)           # scaled below base -> base
    assert dc.heat_budget(1000.0) == pytest.approx(dc.MAX_HEAT_CEILING)


# ------------------------------------------------------------------------ the allocator readers

def _artifact(tmp_path: Path, doc: dict | str, *, armed: bool = True, age_s: float = 0.0) -> Path:
    (tmp_path / "data").mkdir(exist_ok=True)
    (tmp_path / "reports").mkdir(exist_ok=True)
    if armed:
        (tmp_path / "data" / "PF_ALLOCATOR_ARMED").write_text("", "utf-8")
    f = tmp_path / "reports" / "pf_allocation.json"
    f.write_text(doc if isinstance(doc, str) else json.dumps(doc), "utf-8")
    return f


_OK = {"heat": {"total": 0.2, "certified": True, "binding": "target"},
       "growth": {"annual_growth_pct": 12.0},
       "book": {"a": 0.12, "b": 0.08}, "marginal_delta_elog": {"a": 0.01, "b": 0.02}}


def test_allocator_heat_fails_closed_on_every_doubt(tmp_path) -> None:
    assert dc.allocator_heat(tmp_path)[0] is None
    assert "not armed" in dc.allocator_heat(tmp_path)[1]
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "PF_ALLOCATOR_ARMED").write_text("", "utf-8")
    assert dc.allocator_heat(tmp_path) == (None, "no pf_allocation.json")
    f = _artifact(tmp_path, _OK)
    stale = f.stat().st_mtime + dc._ALLOC_MAX_AGE_S + 600
    total, why = dc.allocator_heat(tmp_path, now=stale)
    assert total is None and "min stale" in why
    _artifact(tmp_path, {**_OK, "heat": {"total": 0.2, "certified": False}})
    assert dc.allocator_heat(tmp_path)[1] == "allocator did not certify the utilisation target"
    _artifact(tmp_path, {**_OK, "heat": {"total": 0.31, "certified": True}})
    assert "outside (0, 0.30]" in dc.allocator_heat(tmp_path)[1]
    _artifact(tmp_path, {**_OK, "heat": {"total": 0.0, "certified": True}})
    assert "outside" in dc.allocator_heat(tmp_path)[1]
    _artifact(tmp_path, {**_OK, "growth": {"annual_growth_pct": float("-inf")}})
    assert "no finite growth" in dc.allocator_heat(tmp_path)[1]
    _artifact(tmp_path, {**_OK, "growth": {}})
    assert "no finite growth (None)" in dc.allocator_heat(tmp_path)[1]
    _artifact(tmp_path, "{ not json")
    assert "unreadable (JSONDecodeError)" in dc.allocator_heat(tmp_path)[1]


def test_allocator_heat_returns_the_certified_total_with_its_provenance(tmp_path) -> None:
    f = _artifact(tmp_path, _OK)
    total, why = dc.allocator_heat(tmp_path, now=f.stat().st_mtime + 120)
    assert total == pytest.approx(0.2)
    assert why == "allocator book (2 min old, binding=target)"
    assert dc.allocator_heat(tmp_path)[0] == pytest.approx(0.2)          # wall clock too


def test_allocator_rank_reads_a_fresh_marginal_map_or_nothing(tmp_path) -> None:
    assert dc.allocator_rank(tmp_path) is None
    f = _artifact(tmp_path, _OK)
    assert dc.allocator_rank(tmp_path) == {"a": 0.01, "b": 0.02}
    assert dc.allocator_rank(tmp_path, now=f.stat().st_mtime + 2 * dc._ALLOC_MAX_AGE_S) is None
    _artifact(tmp_path, {**_OK, "marginal_delta_elog": {}})
    assert dc.allocator_rank(tmp_path) is None
    _artifact(tmp_path, {**_OK, "marginal_delta_elog": [1, 2]})
    assert dc.allocator_rank(tmp_path) is None
    _artifact(tmp_path, {**_OK, "marginal_delta_elog": {"a": "x"}})
    assert dc.allocator_rank(tmp_path) is None
    _artifact(tmp_path, "{ not json")
    assert dc.allocator_rank(tmp_path) is None


def test_allocator_order_ranks_known_first_and_leaves_the_rest_in_place() -> None:
    sl = [{"name": "z"}, {"name": "a"}, {"name": "b"}, {"name": "y"}]
    assert dc.allocator_order(sl, None) is sl and dc.allocator_order(sl, {}) is sl
    got = dc.allocator_order(sl, {"a": 0.01, "b": 0.02})
    assert [s["name"] for s in got] == ["b", "a", "z", "y"]


def test_book_from_allocation_deploys_the_floor_with_the_best_baseline_when_unproven() -> None:
    fb = {"name": "inverse_vol", "book": {"a": 0.09, "b": 0.11}}
    book, why = dc.book_from_allocation(0.2, {"a": 0.12, "b": 0.08}, fb, certified=False,
                                        why="proof failed")
    assert book == {"a": 0.09, "b": 0.11}
    assert "inverse_vol" in why and "withheld" in why and "proof failed" in why
    # No fallback: rank but do not size.
    book, why = dc.book_from_allocation(0.2, {"a": 0.12}, {}, certified=False, why="stale")
    assert book is None and "may rank but not size: stale" in why
    book, why = dc.book_from_allocation(0.2, {"a": 0.12}, None, certified=False, why="stale")
    assert book is None
    # A fallback that does not sum to the heat is refused.
    book, why = dc.book_from_allocation(0.2, {}, {"book": {"a": 0.05}}, certified=False, why="s")
    assert book is None and "fallback book sums to 0.0500" in why
    # Junk values in the fallback read as no fallback; zero-weight sleeves are dropped.
    book, why = dc.book_from_allocation(0.2, {}, {"book": {"a": "x"}}, certified=False, why="s")
    assert book is None and "no fallback book either" in why
    book, _ = dc.book_from_allocation(0.2, {}, {"book": {"a": 0.2, "b": 0.0}}, certified=False,
                                      why="s")
    assert book == {"a": 0.2}
    book, why = dc.book_from_allocation(0.2, {}, {"book": {}}, certified=False, why="s")
    assert book is None and "?" not in why


def test_book_from_allocation_sizes_the_proven_book_and_refuses_a_drifted_or_empty_one() -> None:
    book, why = dc.book_from_allocation(0.2, {"a": 0.12, "b": 0.08, "c": 0.0}, None,
                                        certified=True, why="proof 1h old")
    assert book == {"a": 0.12, "b": 0.08}
    assert why == "allocator book authoritative (2 sleeve(s)); proof 1h old"
    assert dc.book_from_allocation(0.2, {"a": 0.5}, None, certified=True, why="")[1] == (
        "book sums to 0.5000, heat says 0.2000")
    assert dc.book_from_allocation(0.2, {}, None, certified=True, why="")[1] == (
        "allocator book is empty (no positive-heat sleeve)")
    assert dc.book_from_allocation(0.2, None, None, certified=True, why="")[0] is None
    assert "unreadable (ValueError)" in dc.book_from_allocation(
        0.2, {"a": "x"}, None, certified=True, why="")[1]


# ================================================================================== the heat cap

def _sleeves(n: int) -> list[dict]:
    return [{"name": f"s{i}"} for i in range(n)]


def test_cap_by_heat_degenerate_inputs_do_not_open_the_gate() -> None:
    assert dc.cap_by_heat([], EQ) == ([], None)
    admitted, note = dc.cap_by_heat(_sleeves(3), 0.0)
    assert len(admitted) == 3 and note is None


def test_cap_by_heat_bills_each_sleeve_its_own_price() -> None:
    gold = [{"name": f"gold_{w}", "symbol": "XAUUSD", "dist": d}
            for w, d in (("asia", 53.40), ("london_am", 27.91), ("afternoon", 48.64))]
    admitted, note = dc.cap_by_heat(gold, EQ)
    assert len(admitted) == 3 and note is None
    qs = [dc.realised_q(EQ, s["dist"], s["symbol"]) for s in gold]
    assert len(set(round(q, 6) for q in qs)) > 1
    # q_charge beats the stop; a nominal gold leg is priced at the house stop; a non-gold leg
    # with no stop is priced at Q_OPT; an unpriceable leg costs the dearest measured leg.
    mixed = [{"name": "charged", "q_charge": 0.05},
             {"name": "gold_nominal", "symbol": "XAUUSD"},
             {"name": "jpy_no_stop", "symbol": "CADJPY"},
             {"name": "bad", "symbol": "NOSUCHPAIR", "dist": 1.0}]
    admitted, note = dc.cap_by_heat(mixed, EQ, per_sleeve_q=None, k_eff=None)
    assert [s["name"] for s in admitted] == ["charged", "gold_nominal", "jpy_no_stop", "bad"]
    assert note is None
    # An explicit scalar q applies to every sleeve; the count is limit / q.
    limit = min(dc.heat_budget(None) + dc.HEAT_SLIDE, dc.MAX_HEAT_CEILING)
    admitted, note = dc.cap_by_heat(_sleeves(40), EQ, 0.01, None)
    assert len(admitted) == int(limit / 0.01 + 1e-9) and note and "deferring" in note


def test_cap_by_heat_admits_nobody_when_nothing_can_be_priced() -> None:
    admitted, note = dc.cap_by_heat([{"name": "bad", "symbol": "NOSUCHPAIR", "dist": 1.0}], EQ)
    assert admitted == [] and "admitting none" in note


def test_cap_by_heat_greedy_fill_continues_past_a_misfit() -> None:
    """CONTINUE, NOT BREAK: one expensive leg near the front must not defer the cheap tail."""
    sl = [{"name": "cheap1", "q_charge": 0.05}, {"name": "whale", "q_charge": 0.25},
          {"name": "cheap2", "q_charge": 0.05}]
    admitted, note = dc.cap_by_heat(sl, EQ)
    assert [s["name"] for s in admitted] == ["cheap1", "cheap2"]
    assert "deferring ['whale']" in note and "k_eff unmeasured" in note
    _, note = dc.cap_by_heat(sl, EQ, k_eff=2.26)
    assert "k_eff 2.26" in note


def test_cap_by_heat_budgets_from_the_allocator_verdict_when_given() -> None:
    sl = [{"name": "a", "q_charge": 0.08}, {"name": "b", "q_charge": 0.08}]
    # Derived budget (20% + 2% slide) fits both; a solved 10% total does not.
    assert dc.cap_by_heat(sl, EQ)[1] is None
    admitted, note = dc.cap_by_heat(sl, EQ, allocation=(0.10, "allocator book (3 min old)"))
    assert [s["name"] for s in admitted] == ["a"]
    assert "budget 10.0%" in note and "[allocator book (3 min old)]" in note
    # An unusable verdict names itself in the note and the derivation stands.
    sl = [{"name": f"s{i}", "q_charge": 0.05} for i in range(6)]
    _, note = dc.cap_by_heat(sl, EQ, allocation=(None, "no pf_allocation.json"))
    assert "[derived (allocator unusable: no pf_allocation.json)]" in note
    _, note = dc.cap_by_heat(sl, EQ)
    assert "no allocator verdict given" in note


def test_cap_by_heat_orders_by_the_allocators_marginal_value() -> None:
    sl = [{"name": "old", "q_charge": 0.15}, {"name": "new", "q_charge": 0.15}]
    admitted, _ = dc.cap_by_heat(sl, EQ, rank={"new": 0.02, "old": 0.01})
    assert [s["name"] for s in admitted] == ["new"]
    admitted, _ = dc.cap_by_heat(sl, EQ)
    assert [s["name"] for s in admitted] == ["old"]


def test_the_slide_is_a_tolerance_and_the_ceiling_is_absolute() -> None:
    q = dc.realised_q(1684.0)
    budget = dc.heat_budget()
    n = int(budget // q) + 1
    admitted, _ = dc.cap_by_heat(_sleeves(n), 1684.0)
    assert len(admitted) == n and n * q > budget
    for k_eff in (None, 2.26, 9.0, 40.0):
        admitted, _ = dc.cap_by_heat(_sleeves(80), 1684.0, k_eff=k_eff)
        assert len(admitted) * q <= dc.MAX_HEAT_CEILING + 1e-9


# ============================================================================ roster admission

def test_load_sleeves_keeps_live_rows_only_and_never_raises(tmp_path) -> None:
    p = tmp_path / "sleeves.json"
    assert dc.load_sleeves(p) == []
    p.write_text(json.dumps({"sleeves": [{"name": "a", "status": "LIVE"},
                                         {"name": "b", "status": "RETIRED"}]}), "utf-8")
    assert [s["name"] for s in dc.load_sleeves(p)] == ["a"]
    p.write_text("{ nope", "utf-8")
    assert dc.load_sleeves(p) == []


def test_load_retired_gold_fails_open(tmp_path) -> None:
    p = tmp_path / "GOLD_RETIRED.json"
    assert dc.load_retired_gold(p) == {}
    p.write_text("[1, 2]", "utf-8")
    assert dc.load_retired_gold(p) == {}
    p.write_text('{"gold_asia": {"reason": "roll20"}}', "utf-8")
    assert dc.load_retired_gold(p) == {"gold_asia": {"reason": "roll20"}}


def test_ledger_rows_skips_torn_and_foreign_lines(tmp_path) -> None:
    p = tmp_path / "ledger.jsonl"
    assert dc.ledger_rows(p) == []
    p.write_text('{"a": 1}\n\n[1]\n{"b": 2\n{"c": 3}\n', "utf-8")
    assert dc.ledger_rows(p) == [{"a": 1}, {"c": 3}]


def test_roster_emits_gold_first_and_admits_only_validated_semantics() -> None:
    promoted = [
        {"name": "fam", "symbol": "EURUSD", "exec": "family_market", "family": "f",
         "selector": "asia", "state": "S", "risk_frac": 0.03},
        {"name": "scalp", "symbol": "XAUUSD", "exec": "scalp_market", "timeframe": "M15",
         "family": "anti", "stop_atr": 1.0, "target_atr": 1.5, "max_hold": 6, "risk_frac": 0.03},
        {"name": "bad_window", "symbol": "CADJPY", "window": "ny_open"},
        {"name": "cond", "symbol": "CADJPY", "window": "asia", "state": "FAILED_BREAK",
         "risk_frac": 0.04, "lot": 0.01},
    ]
    sleeves, notes = dc.roster({}, promoted)
    names = [s["name"] for s in sleeves]
    assert names == ["gold_asia", "gold_london_am", "gold_afternoon", "fam", "scalp", "cond"]
    assert notes == []
    gold = sleeves[0]
    assert gold == {"name": "gold_asia", "symbol": "XAUUSD", "window": "asia", "sig_hour": 7,
                    "rng": None, "lot": "auto", "status": "LIVE"}
    fam = sleeves[3]
    assert fam["exec"] == "family_market" and fam["side"] == "LONG" and fam["lot"] == "auto_ramp"
    scalp = sleeves[4]
    assert scalp["exec"] == "scalp_market" and scalp["session"] == "all"
    assert scalp["stop_atr"] == 1.0 and scalp["lot"] == "auto_ramp"
    cond = sleeves[5]
    # THE LITERAL LOT NEVER REACHES THE VENUE and the state travels with the sleeve.
    assert cond["lot"] == "auto_ramp" and cond["state"] == "FAILED_BREAK"
    assert cond["sig_hour"] == 7 and cond["rng"] is None and cond["risk_frac"] == 0.04


def test_roster_drops_a_retired_gold_window_and_says_why() -> None:
    sleeves, notes = dc.roster({"gold_asia": {"reason": "roll20 t=-1.2"}, "gold_afternoon": {}},
                               [])
    assert [s["name"] for s in sleeves] == ["gold_london_am"]
    assert notes == ["GOLD gold_asia: RETIRED (roll20 t=-1.2); not emitted this pass",
                     "GOLD gold_afternoon: RETIRED (no reason recorded); not emitted this pass"]


def test_hibernated_maps_gold_windows_and_promoted_tags() -> None:
    sleeves = [{"name": "gold_asia"}, {"name": "CADJPY.asia"}, {"name": "gold_afternoon"}]
    state = {"sleeves": {"XAUUSD|asia": {"flag": "hibernate"},
                         "CADJPY|asia": {"flag": "hibernate"},
                         "XAUUSD|afternoon": {"flag": "ok"}}}
    assert dc.hibernated(sleeves, state) == {"gold_asia", "CADJPY.asia"}
    assert dc.hibernated(sleeves, {}) == set()


_H1 = pd.DataFrame({"open": [1.0], "high": [1.0], "low": [1.0], "close": [1.0]},
                   index=pd.to_datetime(["2026-08-17 07:00"], utc=True))


def test_state_allows_fails_closed(monkeypatch) -> None:
    assert dc.state_allows({"name": "gold_asia"}, _H1, None) == (True, "")
    ok, why = dc.state_allows({"name": "x", "state": "FAILED_BREAK"}, None, None)
    assert not ok and "UNCOMPUTABLE" in why
    import research.run_hunt12 as h12
    monkeypatch.setattr(h12, "day_states", lambda h1: {"D": "NORMAL_DAY"})
    ok, why = dc.state_allows({"name": "x", "state": "FAILED_BREAK"}, _H1, "D")
    assert not ok and why == "state NORMAL_DAY != FAILED_BREAK"
    ok, why = dc.state_allows({"name": "x", "state": "FAILED_BREAK"}, _H1, "E")
    assert not ok and "unknown for today" in why
    monkeypatch.setattr(h12, "day_states", lambda h1: {"D": "FAILED_BREAK"})
    assert dc.state_allows({"name": "x", "state": "FAILED_BREAK"}, _H1, "D") == (True, "")


# ===================================================================================== brackets

def _h1(n: int = 60, start: str = "2026-09-03 00:00") -> pd.DataFrame:
    idx = pd.date_range(start, periods=n, freq="h", tz="UTC")
    base = 4300.0 + np.arange(n, dtype=float)
    return pd.DataFrame({"open": base, "high": base + 8.0, "low": base - 8.0, "close": base + 1.0,
                         "tick_volume": 100.0}, index=idx)


def test_h1_frame_indexes_broker_rows_by_utc_time() -> None:
    rows = [{"time": 1_756_710_000 + 3600 * i, "open": 1.0, "high": 2.0, "low": 0.5,
             "close": 1.5, "tick_volume": 3} for i in (2, 0, 1)]
    df = dc.h1_frame(rows)
    assert df.index.tz is not None and df.index.is_monotonic_increasing and len(df) == 3
    assert list(df.columns) == ["open", "high", "low", "close", "tick_volume"]


def test_day_range_reads_the_last_days_window() -> None:
    df = _h1(30)                                     # 2026-09-03 00:00 .. 2026-09-04 05:00
    hi, lo = dc.day_range(df, None, 7)               # hours [0, 7) of the LAST day
    assert hi == pytest.approx(4300.0 + 29 + 8.0) and lo == pytest.approx(4300.0 + 24 - 8.0)
    assert dc.day_range(df, (10, 13), 13) is None    # not yet formed today
    hi, lo = dc.day_range(df, (0, 3), 13)
    assert hi == pytest.approx(4300.0 + 26 + 8.0) and lo == pytest.approx(4300.0 + 24 - 8.0)


def test_atr_last_is_the_one_definition() -> None:
    df = _h1()
    tr = pd.concat([df["high"] - df["low"], (df["high"] - df["close"].shift(1)).abs(),
                    (df["low"] - df["close"].shift(1)).abs()], axis=1).max(axis=1)
    assert dc.atr_last(df) == pytest.approx(
        float(tr.ewm(alpha=1 / dc.ATR_N, min_periods=dc.ATR_N).mean().iloc[-1]))
    assert math.isnan(dc.atr_last(df.iloc[:5]))      # too few bars for the window


def test_bracket_spec_places_stops_outside_the_venue_band() -> None:
    spec = dc.bracket_spec(4360.0, 4300.0, 30.0, 0.01, stops_level=20)
    # dist = max(1.2*30, 60) = 60 -> sl 6000 + 20 pts, tp 12000 pts at 0.01
    assert spec["buy_stop"] == {"price": 4360.0, "sl": pytest.approx(4360.0 - 60.20),
                                "tp": pytest.approx(4480.0)}
    assert spec["sell_stop"] == {"price": 4300.0, "sl": pytest.approx(4360.20),
                                 "tp": pytest.approx(4180.0)}
    wide = dc.bracket_spec(4310.0, 4300.0, 30.0, 0.0, stops_level=0)   # ATR dominates, tick floor
    assert wide["buy_stop"]["sl"] == pytest.approx(4310.0 - 36.0)


def test_bracket_from_bars_is_the_loop_and_the_veto_record_in_one_place() -> None:
    df = _h1(30)
    assert dc.bracket_from_bars(df, (10, 13), 13, 0.01, 20) is None
    hi, lo, spec = dc.bracket_from_bars(df, None, 7, 0.01, 20)
    assert (hi, lo) == dc.day_range(df, None, 7)
    assert spec == dc.bracket_spec(hi, lo, max(dc.atr_last(df), 5.0), 0.01, stops_level=20)
    assert dc.stop_distance(spec) == pytest.approx(spec["buy_stop"]["price"] -
                                                   spec["buy_stop"]["sl"])


# ====================================================================== diagnosis and placement

def test_diagnose_turns_a_retcode_into_something_actionable() -> None:
    assert "terminal connection is gone" in dc.diagnose(None)
    assert dc.diagnose(10008) == "" and dc.diagnose(10009) == ""
    assert dc.diagnose(10017).startswith("10017 Trade disabled: the ACCOUNT")
    assert "PENDING ORDER PRICE" in dc.diagnose(10015)
    assert dc.diagnose(99999, "weird").startswith("99999 weird: not a retcode")
    assert dc.diagnose(99999).startswith("99999 unrecognised: ")


def test_placement_verdict_separates_unavailable_from_rejected() -> None:
    una = [{"side": "buy_stop", "retcode": None, "unavailable": True}]
    attempted, ok, diags = dc.placement_verdict(una)
    assert not attempted and not ok
    ok_pass = [{"retcode": 10009}, {"retcode": 10008}]
    assert dc.placement_verdict(ok_pass)[:2] == (True, True)
    rej = [{"retcode": 10017, "comment": "Trade disabled"}, {"retcode": 10015}]
    attempted, ok, diags = dc.placement_verdict(rej)
    assert attempted and not ok
    assert [d[:5] for d in diags] == ["10015", "10017"]
    mixed = [*una, {"retcode": 10017}]
    assert dc.placement_verdict(mixed)[:2] == (True, False)
    assert dc.placement_verdict([]) == (False, False, [])


def test_entry_is_legal_refuses_inside_the_band_on_both_sides() -> None:
    ok, why = dc.entry_is_legal(4360.50, "buy_stop", 4360.0, 4360.30, 0.01, 50)
    assert not ok and "NOT AVAILABLE" in why and "buy_stop" in why
    assert dc.entry_is_legal(4365.0, "buy_stop", 4360.0, 4360.30, 0.01, 50) == (True, "")
    ok, why = dc.entry_is_legal(4359.90, "sell_stop", 4360.0, 4360.30, 0.01, 50)
    assert not ok and why.startswith("sell_stop")
    assert dc.entry_is_legal(4350.0, "sell_stop", 4360.0, 4360.30, 0.01, 50) == (True, "")
    assert dc.entry_is_legal(4360.001, "buy_stop", 4360.0, 4360.0, 0.01, 0)[0]
    assert dc.entry_is_legal(4360.001, "buy_stop", 4360.0, 4360.0, 0.0, -5)[0]


def test_bracket_deadline_is_each_sessions_own_end() -> None:
    at = datetime(2026, 9, 3, 8, 0, tzinfo=UTC)
    assert dc.bracket_deadline("gold_asia", now=at) == at.replace(hour=13)
    assert dc.bracket_deadline("gold_london_am", now=at) == at.replace(hour=17)
    assert dc.bracket_deadline("gold_afternoon", now=at) == at.replace(hour=19, minute=30)
    assert dc.bracket_deadline("promoted", window="asia", now=at) == at.replace(hour=13)
    # An unrecognised window is bounded by the ceiling; a late pass rolls forward but never
    # past the ceiling, and never into the past.
    assert dc.bracket_deadline("promoted_new", now=at) == at + timedelta(hours=6)
    late = datetime(2026, 9, 3, 18, 0, tzinfo=UTC)
    assert dc.bracket_deadline("gold_asia", now=late) == late + timedelta(hours=6)
    later = datetime(2026, 9, 3, 19, 30, tzinfo=UTC)
    assert dc.bracket_deadline("gold_afternoon", now=later) == later + timedelta(hours=6)
    assert dc.bracket_deadline("gold_asia") > datetime.now(tz=UTC)


def test_sleeve_from_comment_and_closed_trade_r() -> None:
    assert dc.sleeve_from_comment("DWgold_asia") == "gold_asia"
    assert dc.sleeve_from_comment("", "UNATTRIBUTED") == "UNATTRIBUTED"
    assert dc.sleeve_from_comment("broker rewrote") == "broker rewrote"
    assert dc.closed_trade_r(100.0, 90.0, True, 100.0, 500.0) == (pytest.approx(10.0),
                                                                    pytest.approx(0.5))
    assert dc.closed_trade_r(100.0, 110.0, False, 100.0, -1000.0) == (pytest.approx(10.0),
                                                                        pytest.approx(-1.0))
    assert dc.closed_trade_r(0.0, 90.0, True, 100.0, 5.0) == (0.0, 0.0)
    assert dc.closed_trade_r(100.0, 110.0, True, 100.0, 5.0) == (pytest.approx(-10.0), 0.0)


# ================================================================== execution context and gates

def test_exec_context_prices_the_same_order_both_ways() -> None:
    tick = SimpleNamespace(bid=2011.8, ask=2012.1)
    g = SimpleNamespace(atr_frac=0.002, edge_r=0.4)
    c = dc.exec_context("XAUUSD", 1, 2012.1, tick, 3.0, g, 0.12, hour=9)
    assert (c.symbol, c.side, c.quote, c.lot, c.hour) == ("XAUUSD", "buy", 2012.1, 0.12, 9)
    assert c.spread_frac == pytest.approx(0.3 / 2012.1) and c.atr_frac == 0.002
    assert c.stop_frac == pytest.approx(3.0 / 2012.1) and c.edge_r == 0.4
    bare = dc.exec_context("XAUUSD", -1, 2011.8, None, 3.0, SimpleNamespace(), 0.0)
    assert bare.side == "sell" and bare.spread_frac == 0.0 and bare.lot == 0.0
    assert bare.atr_frac == pytest.approx(3.0 / 2011.8) and bare.edge_r == 0.3
    assert bare.hour == datetime.now(tz=UTC).hour


def test_release_gate_refuses_by_default_and_never_raises(monkeypatch) -> None:
    from mt5desk import release_identity as ri
    monkeypatch.setattr(ri, "verdict", lambda root=None: SimpleNamespace(
        allows_new_risk=lambda: True, reason="running the sealed commit"))
    assert dc.release_gate() == (True, "running the sealed commit")
    monkeypatch.setattr(ri, "verdict", lambda root=None: SimpleNamespace(
        allows_new_risk=lambda: False, reason="UNMEASURED"))
    assert dc.release_gate(Path("/nowhere")) == (False, "UNMEASURED")

    def _boom(root=None):
        raise RuntimeError("git exploded")
    monkeypatch.setattr(ri, "verdict", _boom)
    ok, why = dc.release_gate()
    assert not ok and why == "release_identity unavailable: RuntimeError: git exploded"


def test_ttl_expired_compares_iso_text() -> None:
    assert not dc.ttl_expired(None, "2026-09-05T10:00:00+00:00")
    assert not dc.ttl_expired("", "2026-09-05T10:00:00+00:00")
    assert not dc.ttl_expired("2026-09-05T11:00:00+00:00", "2026-09-05T10:00:00+00:00")
    assert dc.ttl_expired("2026-09-05T10:00:00+00:00", "2026-09-05T10:00:00+00:00")


# ============================================================================== the family lane

def _sig(when, stop=4290.0, target=4340.0, ttl_bars=12):
    return SimpleNamespace(time=when, stop=stop, target=target, ttl_bars=ttl_bars)


def test_family_signal_hour_prefers_signal_at() -> None:
    assert dc.family_signal_hour({"signal_at": 13, "range_start": 10}) == 13
    assert dc.family_signal_hour({"range_start": 10}) == 10
    assert dc.family_signal_hour({"signal_at": 0, "range_start": 10}) == 10


def test_family_bar_due_is_the_last_closed_bar_at_the_signal_hour() -> None:
    closed = _h1(31)                                         # last bar 2026-09-04 06:00
    assert dc.family_bar_due(closed, 6) == closed.index[-1]
    assert dc.family_bar_due(closed, 7) is None


def test_family_signal_step_is_replay_faithful() -> None:
    closed = _h1(31)
    last = closed.index[-1]
    fam = lambda bars, side: [_sig(closed.index[-2]), _sig(last), _sig(last, stop=4291.0)]  # noqa: E731
    states = lambda bars: {last.date(): "FAILED_BREAK"}                                    # noqa: E731
    # Already considered: silent, no mark.
    step = dc.family_signal_step(closed, last, last_signal_bar=str(last), want_state=None,
                                 side=1, family_fn=fam, day_states_fn=states)
    assert step == dc.FamilyStep(mark=False)
    # State mismatch: marked and named.
    step = dc.family_signal_step(closed, last, last_signal_bar=None, want_state="NORMAL_DAY",
                                 side=1, family_fn=fam, day_states_fn=states)
    assert step.mark and step.signal is None
    assert step.note == "no trade: day state FAILED_BREAK != NORMAL_DAY"
    # State match: the LAST signal on the bar is taken.
    step = dc.family_signal_step(closed, last, last_signal_bar=None, want_state="FAILED_BREAK",
                                 side=1, family_fn=fam, day_states_fn=states)
    assert step.mark and step.note == "" and step.signal.stop == 4291.0
    # No signal on this bar: marked, silent.
    step = dc.family_signal_step(closed, last, last_signal_bar=None, want_state=None, side=-1,
                                 family_fn=lambda bars, side: [_sig(closed.index[-2])],
                                 day_states_fn=states)
    assert step == dc.FamilyStep(mark=True)

    def _boom(bars, side):
        raise ValueError("no such column")
    step = dc.family_signal_step(closed, last, last_signal_bar=None, want_state=None, side=1,
                                 family_fn=_boom, day_states_fn=states)
    assert not step.mark and step.signal is None
    assert step.note == "FAMILY-EXEC signal computation failed (no such column); skipped"


def test_family_entry_ttl_and_order_line() -> None:
    g = _sig(pd.Timestamp("2026-09-04 06:00", tz="UTC"), stop=4290.0, target=4340.5, ttl_bars=12)
    assert dc.family_entry(g, 1, 4300.0, 4300.3) == (4300.3, pytest.approx(10.3))
    assert dc.family_entry(g, -1, 4300.0, 4300.3) == (4300.0, pytest.approx(10.0))
    ttl = dc.family_ttl_until(pd.Timestamp("2026-09-04 06:00", tz="UTC"), 12)
    assert ttl == "2026-09-04T19:00:00+00:00"
    assert dc.family_order_desc(1, 0.12, "XAUUSD", g, ttl) == (
        "BUY 0.12 XAUUSD @market sl=4290.00000 tp=4340.50000 ttl_until=2026-09-04T19:00:00+00:00")
    assert dc.family_order_desc(-1, 0.5, "EURUSD", g, ttl).startswith("SELL 0.5 EURUSD")


# =============================================================================== the scalp lane

def test_scalp_recipe_is_the_promoters_exact_row() -> None:
    row = {"family": "anti", "session": None, "stop_atr": "1.0", "target_atr": 1.5, "max_hold": 6}
    assert dc.scalp_recipe(row) == ("anti", "all", 1.0, 1.5, 6)
    with pytest.raises(KeyError):
        dc.scalp_recipe({"family": "anti", "stop_atr": 1.0, "target_atr": 1.5})
    with pytest.raises(ValueError):
        dc.scalp_recipe({**row, "stop_atr": "wide"})
    with pytest.raises(TypeError):
        dc.scalp_recipe({**row, "max_hold": None})


def test_scalp_basket_arithmetic_and_order_lines() -> None:
    plan = SimpleNamespace(side=-1, stop=2015.0, target=2005.0, atr=1.0, entry_ref=2011.8,
                           bar_time="2026-09-04T10:00:00+00:00", ttl_until="2026-09-04T11:45:00")
    entries = dc.addon_entries([[2011.8, 0.03]], 2011.0, 0.03)
    assert entries == [(2011.8, 0.03), (2011.0, 0.03)]
    assert dc.basket_lots(entries) == pytest.approx(0.06)
    rec = dc.basket_record(plan, 0.03, "bounded_structural", 1.5)
    assert rec == {"side": -1, "stop": 2015.0, "target": 2005.0, "atr": 1.0, "target_atr": 1.5,
                   "mode": "bounded_structural", "entries": [[2011.8, 0.03]],
                   "opened_bar": "2026-09-04T10:00:00+00:00"}
    assert dc.scalp_order_desc(plan, 0.03, "XAUUSD", "bounded_structural") == (
        "SELL 0.03 XAUUSD @market sl=2015.00000 tp=2005.00000 mode=bounded_structural "
        "ttl_until=2026-09-04T11:45:00")
    assert dc.addon_desc(1, 0.03, "XAUUSD", 2000.0, 2010.5, 2) == (
        "ADD BUY 0.03 XAUUSD @market sl=2000.00000 tp->2010.50000 depth=2")
    assert dc.addon_desc(-1, 0.03, "XAUUSD", 2000.0, 2010.5, 3).startswith("ADD SELL")


def test_the_artifact_age_uses_the_clock_it_is_given(tmp_path) -> None:
    """A stale artifact is a claim about an opportunity set that has moved; the clock is an
    argument so that claim is testable without sleeping through an hour."""
    f = _artifact(tmp_path, _OK)
    fresh = f.stat().st_mtime + 30
    assert dc.allocator_heat(tmp_path, now=fresh)[0] == pytest.approx(0.2)
    assert dc.allocator_rank(tmp_path, now=fresh) is not None
    assert time.time() - f.stat().st_mtime < dc._ALLOC_MAX_AGE_S

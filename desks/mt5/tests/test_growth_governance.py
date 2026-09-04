"""Growth governance: the floor is deployed, growth is free above it, and every rail pays rent.

What is pinned:

  * the heat law resolves 20% when growth wants less, 23% when it wants 23%, 30% when it wants
    more, and never above 30% (wiring, not a new rule);
  * the allocator's fraction reaches the venue un-re-shrunk: `promoted_lot(from_book=True)`
    applies neither the 3% floor clamp nor the authority ramp, and a zero-heat sleeve gets no lot;
  * when the proof certificate is stale or failed the gateway sizes the floor with the best
    baseline the contest scored, at the same total heat -- never with nothing;
  * the contest carries its baseline books; the Kelly surface's tail bound is monotone in the
    fraction; the governor's verdict names unused upside and nothing else;
  * every capital modifier is two-sided or a registered kill switch / measured decay signal;
  * every rail has a measurement, the calibration is clipped to its bounds, and a rail that
    costs growth is weakened while one that earns is left alone;
  * the portable governance fence passes on this tree.
"""
from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

import itertools

from mt5desk.gateway_config_fallback import HEAT_HARD_CEILING, HEAT_TARGET  # noqa: E402
from research.heat_policy import resolve  # noqa: E402

from libs.portfolio import aggression, capital_modifiers, kelly_surface, rails  # noqa: E402
from libs.portfolio.allocator_proof import contest  # noqa: E402
from libs.portfolio.robust_elog import (  # noqa: E402
    SleeveEvidence,
    WorldConfig,
    sample_worlds,
)
from research import missed_growth  # noqa: E402

_GW_SRC = (_DESK / "mt5desk" / "gateway.py").read_text(encoding="utf-8")
_GW_TREE = ast.parse(_GW_SRC)
GOOD_CURVE = {0.05: 0.0010, 0.10: 0.0018, 0.15: 0.0023, 0.20: 0.0025, 0.25: 0.0025,
              0.30: 0.0024}


# --------------------------------------------------------------------------- the heat law
def test_floor_20_growth_free_to_30() -> None:
    assert resolve(0.08, curve=GOOD_CURVE).total_heat == pytest.approx(HEAT_TARGET)
    assert resolve(0.23, curve=GOOD_CURVE).total_heat == pytest.approx(0.23)
    assert resolve(0.30, curve=GOOD_CURVE).total_heat == pytest.approx(0.30)
    assert resolve(0.45, curve=GOOD_CURVE).total_heat == pytest.approx(HEAT_HARD_CEILING)
    for r in (0.0, 0.3, 1.0):                                        # readiness never gates
        assert resolve(0.01, curve=GOOD_CURVE, readiness=r).total_heat == pytest.approx(0.20)


# --------------------------------------------------------------------------- the sizer
def _exec(names: tuple[str, ...], ns: dict) -> dict:
    keep = [n for n in _GW_TREE.body if isinstance(n, ast.FunctionDef) and n.name in names]
    exec(compile(ast.Module(body=keep, type_ignores=[]), "<gw>", "exec"), ns)
    return ns


def test_the_books_fraction_reaches_the_venue_unshrunk() -> None:
    import math

    from mt5desk.sizing import MAX_RISK_FRAC, clamp_risk_frac, decay_factor
    ns = _exec(("promoted_lot",), {"math": math, "MAX_RISK_FRAC": MAX_RISK_FRAC,
                                   "clamp_risk_frac": clamp_risk_frac,
                                   "decay_factor": decay_factor, "GOLD_SYMBOL": "XAUUSD",
                                   "auto_lot": lambda equity, dist, symbol, info, q: q * 100.0})
    lot = ns["promoted_lot"]
    # A 1.7% book fraction on a sleeve with 3 live trades: the ramp would have made it 0.75%
    # and the clamp would have raised it to 3%. From the book it is 1.7%.
    assert lot(1000.0, 3, 10.0, "EURUSD", None, 0.017, None, from_book=True) == pytest.approx(1.7)
    assert lot(1000.0, 3, 10.0, "EURUSD", None, 0.017, None) == pytest.approx(0.75)
    # The outer per-trade envelope still holds, the fade still reduces, no heat is no lot.
    assert lot(1000.0, 3, 10.0, "EURUSD", None, 0.5, None, from_book=True) == pytest.approx(5.0)
    assert lot(1000.0, 3, 10.0, "EURUSD", None, 0.04, True, from_book=True) == pytest.approx(2.0)
    assert lot(1000.0, 3, 10.0, "EURUSD", None, 0.0, None, from_book=True) == 0.0
    assert lot(1000.0, 3, 10.0, "EURUSD", None, None, None, from_book=True) == 0.0


def test_both_promoted_lot_call_sites_pass_from_book() -> None:
    assert _GW_SRC.count('from_book=(s.get("sized_by") == "allocator_book")') == 2
    assert '_s["q_charge"] = float(_book[_s["name"]]) * decay_factor' in _GW_SRC


# --------------------------------------------------------------------------- the fallback
def test_gateway_sizes_the_floor_with_the_best_baseline_when_the_proof_fails(tmp_path,
                                                                             monkeypatch) -> None:
    import libs.portfolio.allocator_proof as ap
    (tmp_path / "reports").mkdir()
    art = {"heat": {"total": 0.2, "certified": True}, "growth": {"annual_growth_pct": 12.0},
           "book": {"a": 0.12, "b": 0.08},
           "book_fallback": {"name": "inverse_vol", "book": {"a": 0.09, "b": 0.11}}}
    (tmp_path / "reports" / "pf_allocation.json").write_text(json.dumps(art))
    ns = _exec(("allocator_book",), {"json": json, "BASE": tmp_path,
                                     "allocator_heat": lambda: (0.2, "allocator book (ok)")})
    monkeypatch.setattr(ap, "read_certificate", lambda root: (None, "proof failed"))
    book, why = ns["allocator_book"]()
    assert book == {"a": 0.09, "b": 0.11} and "inverse_vol" in why and "withheld" in why
    monkeypatch.setattr(ap, "read_certificate", lambda root: ({"passed": True}, "proof 1h old"))
    book, why = ns["allocator_book"]()
    assert book == {"a": 0.12, "b": 0.08}
    # No fallback carried and no proof: rank but do not size (the derived budget still deploys).
    art["book_fallback"] = {}
    (tmp_path / "reports" / "pf_allocation.json").write_text(json.dumps(art))
    monkeypatch.setattr(ap, "read_certificate", lambda root: (None, "proof failed"))
    assert ns["allocator_book"]()[0] is None


def _evidence(n: int = 4, seed: int = 0) -> list[SleeveEvidence]:
    rng = np.random.default_rng(seed)
    return [SleeveEvidence(name=f"s{i}", daily_r=rng.normal(0.02, 0.3, 400), family=f"f{i}",
                           forward_days=100, live_days=20) for i in range(n)]


def test_the_resolved_heat_is_filled_when_bounds_cannot_fund_it() -> None:
    """Four sleeves bounded at 1% each can hold 4%; the resolved 20% is held anyway, and the
    note says which bound yielded."""
    from research.pf_allocator import fill_floor

    from libs.portfolio.robust_elog import optimise
    ev = _evidence(seed=4)
    cfg = WorldConfig(n_worlds=16, n_rows=64, seed=4)
    worlds = sample_worlds(ev, cfg)
    ub = {e.name: 0.01 for e in ev}
    with pytest.raises(ValueError):                    # the mandated solve refuses such bounds
        optimise(ev, hard_cap=0.30, target=0.20, cfg=cfg, worlds=worlds, max_per_sleeve=ub)
    bounded = optimise(ev, hard_cap=0.30, target=None, cfg=cfg, worlds=worlds, max_per_sleeve=ub)
    assert bounded.total_heat < 0.05
    filled, note = fill_floor(bounded, ev, 0.20, ub, {e.name: e.family for e in ev},
                              cfg=cfg, worlds=worlds)
    assert note["needed"] and note["relaxed"] in ("drawdown_bound", "family_cap", "share_cap",
                                                   "proportional")
    assert filled.total_heat == pytest.approx(0.20, abs=1e-3)
    assert np.isfinite(filled.mean_log_growth)
    # A book already at the floor is returned untouched.
    same, note2 = fill_floor(filled, ev, 0.20, ub, {}, cfg=cfg, worlds=worlds)
    assert same is filled and not note2["needed"]


def test_contest_carries_the_baseline_books_at_the_same_heat() -> None:
    ev = _evidence()
    cfg = WorldConfig(n_worlds=16, n_rows=64, seed=1)
    worlds = sample_worlds(ev, cfg)
    dyn = {"s0": 0.08, "s1": 0.06, "s2": 0.04, "s3": 0.02}
    out = contest(ev, dyn, cfg=cfg, worlds=worlds)
    assert set(out["books"]) >= {"equal_weight", "inverse_vol", "risk_parity"}
    for name, b in out["books"].items():
        if name != "static_incumbent":
            assert sum(b.values()) == pytest.approx(0.20, abs=1e-6), name
    assert out["best_baseline"] in out["books"]


# --------------------------------------------------------------------------- the surface
def test_kelly_surface_tail_bound_is_monotone_and_named() -> None:
    ev = _evidence(seed=2)
    cfg = WorldConfig(n_worlds=24, n_rows=64, seed=2)
    worlds = sample_worlds(ev, cfg)
    book = {"s0": 0.06, "s1": 0.05, "s2": 0.05, "s3": 0.04}
    s = kelly_surface.surface(worlds, book, tolerance=0.35, alpha=0.2)
    rows = s["rows"]
    assert rows[0]["f"] == 0.0 and rows[0]["p_ruin"] == 0.0 and rows[0]["dd_p90"] == 0.0
    ruin = [r["p_ruin"] for r in rows]
    assert all(b >= a - 1e-12 for a, b in itertools.pairwise(ruin))  # monotone
    dd = [r["p_dd_over_tolerance"] for r in rows]
    assert all(b >= a - 1e-12 for a, b in itertools.pairwise(dd))
    assert s["heat_tail_max"] == pytest.approx(s["f_tail"] * s["total_heat"])
    assert s["at_book"]["f"] == 1.0


def test_governor_names_unused_upside_and_nothing_else() -> None:
    ev = _evidence(seed=3)
    book = {"s0": 0.06, "s1": 0.05, "s2": 0.05, "s3": 0.04}
    surf = {"heat_tail_max": 0.28, "alpha": 0.2,
            "at_book": {"p_ruin": 0.0, "p_dd_over_tolerance": 0.05}}
    common = {"floor": 0.20, "ceiling": 0.30, "readiness": 0.4, "proof_passed": True, "surface": surf,
                  "book": book, "ev": ev}
    assert aggression.explain(total_heat=0.20, free_optimum=0.12, **common)["verdict"] == "AT_FLOOR"
    g = aggression.explain(total_heat=0.24, free_optimum=0.24, **common)
    assert g["verdict"] == "GROWTH_ABOVE_FLOOR" and g["A"] == pytest.approx(1.2)
    assert aggression.explain(total_heat=0.30, free_optimum=0.40, **common)["verdict"] == "CEILING_BOUND"
    assert aggression.explain(total_heat=0.28, free_optimum=0.29, **common)["verdict"] == "TAIL_BOUND"
    u = aggression.explain(total_heat=0.20, free_optimum=0.26, **common)
    assert u["verdict"] == "UNUSED_UPSIDE" and u["unused_upside_heat"] == pytest.approx(0.06)
    assert u["components"]["effective_breadth"] is not None and u["components"]["model_agreement"]


# --------------------------------------------------------------------------- modifiers
def test_every_modifier_is_two_sided_or_a_registered_kill_switch() -> None:
    rail_names = {r.name for r in rails.RAILS}
    for m in capital_modifiers.REGISTRY:
        if m.kind == "two_sided":
            assert m.hi > 1.0, m.name
        elif m.kind == "reduce_only":
            assert m.name in rail_names, m.name
        else:
            assert m.kind == "integrity", m.name
    assert {"state_posterior", "ai_capital_modifier"} <= {m.name for m in capital_modifiers.REGISTRY}


def test_ai_capital_modifier_boosts_as_readily_as_it_cuts() -> None:
    cat = capital_modifiers.category
    assert cat(0.02, 0.01, n_state=200)[0] in ("BOOST", "STRONG_BOOST")
    assert cat(-0.02, 0.01, n_state=200)[0] == "STRONG_VETO"
    assert cat(0.01, 0.01, n_state=200)[0] == "NORMAL"
    assert cat(0.02, 0.01, n_state=2)[0] == "NORMAL"          # two observations move nothing
    assert cat(float("nan"), 0.01, n_state=50) == ("NORMAL", 1.0)
    assert 0.0 <= cat(0.05, 0.01, 500)[1] <= 2.0


# --------------------------------------------------------------------------- rails
def test_every_rail_is_measured_and_calibration_is_bounded(tmp_path, monkeypatch) -> None:
    for r in rails.RAILS:
        assert r.measure in missed_growth.MEASURES, r.name
        assert r.kind in ("veto", "gate", "shrink", "cap", "inertia", "integrity", "mandate")
    monkeypatch.setattr(rails, "CALIBRATION", tmp_path / "cal.json")
    rails._CACHE["mtime"] = None
    assert rails.rail_multiplier("position_inertia") == 1.0
    (tmp_path / "cal.json").write_text(json.dumps({"multipliers": {"position_inertia": 0.1,
                                                                   "regime_hibernate": 0.1}}))
    rails._CACHE["mtime"] = None
    assert rails.rail_multiplier("position_inertia") == 0.5      # clipped to lo
    assert rails.rail_multiplier("regime_hibernate") == 1.0      # not tunable
    assert rails.rail_multiplier("no_such_rail") == 1.0


def test_a_rail_that_costs_growth_is_weakened_and_one_that_earns_is_left(tmp_path,
                                                                          monkeypatch) -> None:
    monkeypatch.setattr(missed_growth, "LEDGER", tmp_path / "mg.jsonl")
    monkeypatch.setattr(missed_growth, "OUT", tmp_path / "MG.json")
    monkeypatch.setattr(missed_growth, "ALLOC", tmp_path / "none.json")
    monkeypatch.setattr(missed_growth, "FILTER_VALUE", tmp_path / "none2.json")
    monkeypatch.setattr(missed_growth, "STATE_ADM", tmp_path / "none3.json")
    monkeypatch.setattr(rails, "CALIBRATION", tmp_path / "cal.json")
    monkeypatch.setattr(missed_growth, "CALIBRATION", tmp_path / "cal.json")
    rails._CACHE["mtime"] = None
    rows = [{"day": f"2026-08-{d:02d}", "rail": "position_inertia", "value": -0.001}
            for d in range(1, 16)]
    rows += [{"day": f"2026-08-{d:02d}", "rail": "hard_ceiling", "value": 0.001}
             for d in range(1, 16)]
    (tmp_path / "mg.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    monkeypatch.setattr(missed_growth, "_merge_into_queue", lambda *a, **k: None, raising=False)
    d = missed_growth.run(write=True, today="2026-08-20")
    assert d["rails"]["position_inertia"]["verdict"] == missed_growth.COSTS
    assert d["rails"]["hard_ceiling"]["verdict"] == missed_growth.EARNS
    assert d["calibration"]["position_inertia"] == pytest.approx(0.9)
    assert "hard_ceiling" not in d["calibration"]                  # never strengthened
    d2 = missed_growth.run(write=True, today="2026-08-21")
    assert d2["calibration"]["position_inertia"] == pytest.approx(0.81)
    assert d2["rails"]["regime_hibernate"]["verdict"] == missed_growth.UNMEASURED


def test_the_governance_fence_passes_on_this_tree() -> None:
    r = subprocess.run([sys.executable, str(_ROOT / "scripts" / "check_growth_governance.py")],
                       capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stdout + r.stderr

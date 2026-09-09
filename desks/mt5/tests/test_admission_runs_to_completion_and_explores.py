"""The admission scan prices every candidate every pass, and the ambiguous ones are explored.

TWO HOLES, ONE SCAN. (P2) A 180 s wall-clock budget for the WHOLE scan left a tail of candidates
`unscored` every hour -- named, refused, and a compute limit hardening into a verdict. The budget
is now per candidate: every candidate is re-solved on every heavy pass, a re-solve that hits its
own budget is carried forward WARM-STARTED from where it stopped, and none is refused for
compute. (P9) A candidate whose dE[log W] sat inside the noise margin was refused for ever with
nothing to resolve the ambiguity; `thompson_explore` lends it a small heat from WITHIN the book
so it accrues a forward record, and the `explore_thompson` rail bills what that cost.

THE LAW, pinned in every funding test: the total never moves, no incumbent goes below zero or
above its bound, no candidate is lent more than the optimiser's own equal-heat re-solve gave it,
and when the rule cannot be honoured the block lends nothing and says why.
"""
from __future__ import annotations

import inspect
import sys
from pathlib import Path

import numpy as np
import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.portfolio import rails  # noqa: E402
from libs.portfolio.robust_elog import SleeveEvidence, WorldConfig, sample_worlds  # noqa: E402

pa = pytest.importorskip("research.pf_allocator", reason="the allocator ships with the desk")
mg = pytest.importorskip("research.missed_growth", reason="the ledger ships with the desk")


# --------------------------------------------------------------------------- the world it lives in
def _sleeve(name: str, sharpe: float, rho: float, core: np.ndarray,
            rng: np.random.Generator, family: str, vol: float = 0.35) -> SleeveEvidence:
    idio = rng.normal(0.0, 1.0, core.size)
    z = rho * core + np.sqrt(max(1.0 - rho * rho, 0.0)) * idio
    z = (z - z.mean()) / z.std()
    return SleeveEvidence(name=name, daily_r=z * vol + sharpe / np.sqrt(252.0) * vol,
                          family=family, symbol=name.split("_")[0], n_trials=50,
                          forward_days=40, live_days=0, cost_r=0.02)


def _book_and_two_candidates(seed: int = 7, n: int = 600):
    rng = np.random.default_rng(seed)
    core = rng.normal(0.0, 1.0, n)
    held = [_sleeve(f"HELD_{i}", 2.3, 0.97, core, rng, "core") for i in range(4)]
    diversifier = _sleeve("EURJPY_carry_asia", 1.2, -0.20, core, rng, "carry")
    correlated_star = _sleeve("XAUUSD_trend_ny", 2.5, 0.95, core, rng, "core")
    return held, diversifier, correlated_star


def _scan(held, *candidates, total_heat: float = 0.20, bound: float = 0.20, **kw):
    ev = [*held, *candidates]
    cfg = WorldConfig(seed=3, n_worlds=96, n_rows=200)
    worlds = sample_worlds(ev, cfg)
    return pa.marginal_admission(ev, worlds, cfg, incumbent={e.name: 0.05 for e in held},
                                 bounds={e.name: bound for e in ev},
                                 total_heat=total_heat, **kw)


# ------------------------------------------------------------- P2: the budget is per candidate
def test_the_budget_is_per_candidate_and_the_scan_runs_to_completion() -> None:
    held, diversifier, star = _book_and_two_candidates()
    doc = _scan(held, diversifier, star)
    assert doc["status"] == "MEASURED"
    assert doc["priced"] == doc["n_scored"] == 2 and doc["unscored"] == {}
    assert doc["n_unscored"] == 0 and doc["n_partial"] == 0
    assert doc["budget"]["per_candidate_s"] == pa.ADMISSION_CANDIDATE_BUDGET_S
    assert "per candidate" in doc["budget"]["scope"] and "never refused" in doc["budget"]["scope"]
    assert doc["per_candidate_s"] is not None and doc["max_candidate_s"] >= doc["per_candidate_s"]
    assert doc["elapsed_s"] >= 0.0
    for row in doc["candidates"].values():
        assert row["budget_hit"] is False and row["warm_started_from_last_pass"] is False
        assert row["solve_s"] >= 0.0 and row["iterations"] >= 1


def test_the_whole_scan_wall_clock_cut_is_gone() -> None:
    src = inspect.getsource(pa.marginal_admission)
    assert "admission budget was spent" not in src
    assert "deadline=deadline" in src
    assert not hasattr(pa, "ADMISSION_BUDGET_S"), "the scan-wide constant must not linger"
    assert pa.ADMISSION_CANDIDATE_BUDGET_S > 0


def test_a_partial_solve_is_carried_warm_started_and_the_next_pass_finishes_it() -> None:
    """THE WARM START ACROSS PASSES. A solve that hits its budget is not restarted next hour
    from the incumbent again; the next pass continues from the book it reached, and reaches
    the same verdict a cold complete scan reaches."""
    held, diversifier, star = _book_and_two_candidates()
    ev = [*held, diversifier, star]
    cfg = WorldConfig(seed=3, n_worlds=96, n_rows=200)
    worlds = sample_worlds(ev, cfg)
    common = {"incumbent": {e.name: 0.05 for e in held},
              "bounds": {e.name: 0.20 for e in ev}, "total_heat": 0.20}
    first = pa.marginal_admission(ev, worlds, cfg, budget_s=1e-9, **common)
    assert set(first["unscored"]) == {"EURJPY_carry_asia", "XAUUSD_trend_ny"}
    assert first["admitted"] == [] and first["n_partial"] == 2
    for name, why in first["unscored"].items():
        assert "carried forward warm-started" in why and "NOT admitted" in why
        assert first["partial"][name]["budget_hit"] is True
        assert first["partial"][name]["iterations"] == 0
        assert sum(first["warm"][name].values()) == pytest.approx(0.20, abs=1e-6)
    second = pa.marginal_admission(ev, worlds, cfg, prefer=set(first["unscored"]),
                                   warm=first["warm"], budget_s=-1.0, **common)
    assert second["unscored"] == {} and second["priced"] == 2
    assert second["n_carried_from_last_unreached"] == 2
    for row in second["candidates"].values():
        assert row["warm_started_from_last_pass"] is True
    cold = pa.marginal_admission(ev, worlds, cfg, budget_s=-1.0, **common)
    assert second["admitted"] == cold["admitted"] == ["EURJPY_carry_asia"]
    assert second["refused"] == cold["refused"]


# ---------------------------------------------------------- P9: the explore block, unit level
BAR = 1e-4
ROWS = {"amb1": {"delta_elogw_per_day": 0.6 * BAR, "heat_earned": 0.03, "admit": False},
        "amb2": {"delta_elogw_per_day": -0.3 * BAR, "heat_earned": 0.02, "admit": False},
        "amb3": {"delta_elogw_per_day": 0.9 * BAR, "heat_earned": 0.004, "admit": False},
        "far": {"delta_elogw_per_day": -5 * BAR, "heat_earned": 0.01, "admit": False},
        "zero": {"delta_elogw_per_day": 0.2 * BAR, "heat_earned": 0.0, "admit": False},
        "adm": {"delta_elogw_per_day": 3 * BAR, "heat_earned": 0.05, "admit": True}}
HELD = {"h1": 0.08, "h2": 0.07, "h3": 0.05}
#: Candidates bounded at 5%; incumbents at 10%, above what they hold, as a live book's are.
BOUNDS = {**dict.fromkeys(ROWS, 0.05), **dict.fromkeys(HELD, 0.10)}


def _explore(seed: int, **kw):
    args = {"bar": BAR, "total_heat": 0.20, "basis": "equal_heat", "share": 0.05, "seed": seed}
    args.update(kw)
    return pa.thompson_explore(ROWS, HELD, BOUNDS, **args)


def test_only_the_ambiguous_candidates_are_in_the_band() -> None:
    d = _explore(1)
    assert set(d["band"]) == {"amb1", "amb2", "amb3"}, (
        "outside the margin, zero heat in the re-solve, and admitted are not ambiguous")
    assert d["n_band"] == 3 and d["bar"] == BAR and d["share"] == 0.05


def test_a_positive_draw_lends_from_within_the_book_capped_by_the_resolve_and_the_bound() -> None:
    d = _explore(1)
    assert d["status"] == "FUNDED" and d["applied"] is False
    lent = d["explore_heat"]
    assert set(lent) == {"amb1", "amb2", "amb3"}
    assert d["explore_heat_total"] == pytest.approx(sum(lent.values()), abs=1e-6)
    assert d["explore_heat_total"] <= 0.05 * 0.20 + 1e-9, "never more than the share of total"
    for name, x in lent.items():
        assert 0 < x <= ROWS[name]["heat_earned"] + 1e-9, "never more than the re-solve gave it"
        assert x <= BOUNDS[name] + 1e-9
    assert lent["amb3"] == pytest.approx(0.004), "capped at what the re-solve gave it"
    assert all(b["z_draw"] > 0 for n, b in d["band"].items() if n in lent)
    assert "lent from within" in d["why"]


def test_a_negative_draw_funds_nothing_and_lists_the_band() -> None:
    d = _explore(8)
    assert d["status"] == "NONE" and "explore_heat" not in d
    assert all(b["z_draw"] <= 0 for b in d["band"].values())
    assert "at or below zero" in d["why"]


def test_the_draw_is_deterministic_in_its_seed_so_a_day_explores_one_set() -> None:
    assert _explore(1)["explore_heat"] == _explore(1)["explore_heat"]
    assert _explore(1)["explore_heat"] != _explore(2)["explore_heat"]


def test_explore_lends_nothing_and_says_why_when_it_cannot() -> None:
    free = _explore(1, basis="free")
    assert free["status"] == "NONE" and "free basis" in free["why"]
    none = pa.thompson_explore(ROWS, {}, BOUNDS, bar=BAR, total_heat=0.2, basis="equal_heat",
                               seed=1)
    assert none["status"] == "NONE"
    calm = pa.thompson_explore({"far": ROWS["far"], "adm": ROWS["adm"]}, HELD, BOUNDS, bar=BAR,
                               total_heat=0.2, basis="equal_heat", seed=1)
    assert calm["status"] == "NONE" and "nothing is ambiguous" in calm["why"]
    zero = _explore(1, share=0.0)
    assert zero["status"] == "NONE" and "budget is zero" in zero["why"]


def test_the_rail_multiplier_scales_the_lent_share_and_only_weaker(monkeypatch) -> None:
    monkeypatch.setattr(rails, "rail_multiplier",
                        lambda name: 0.5 if name == "explore_thompson" else 1.0)
    d = _explore(3)
    assert d["rail_multiplier"] == 0.5
    assert d["budget_heat"] == pytest.approx(0.05 * 0.5 * 0.20)
    r = rails.rail("explore_thompson")
    assert r.tunable and r.lo == 0.25 and r.hi == 1.0 and r.weaken_dir == "down"
    assert r.kind == "shrink" and r.measure == "measure_explore" and r.measure in mg.MEASURES


# ------------------------------------------------------------- P9: applying it to the book
def test_apply_explore_keeps_the_total_and_every_incumbent_inside_its_bounds() -> None:
    lent = _explore(1)["explore_heat"]
    book, why = pa.apply_explore(HELD, lent, BOUNDS)
    assert sum(book.values()) == pytest.approx(sum(HELD.values()), abs=1e-9), "total unchanged"
    for k, v in HELD.items():
        assert 0.0 <= book[k] <= v + 1e-12, f"{k}: an incumbent only ever scales DOWN"
        assert book[k] <= BOUNDS.get(k, 1.0) + 1e-12
    for k, x in lent.items():
        assert book[k] == pytest.approx(x)
    scale = book["h1"] / HELD["h1"]
    assert all(book[k] / HELD[k] == pytest.approx(scale) for k in HELD), "pro rata"
    assert "unchanged" in why


def test_apply_explore_refuses_rather_than_break_a_bound_or_move_the_total() -> None:
    same, why = pa.apply_explore(HELD, {}, BOUNDS)
    assert same == HELD and "no exploration heat" in why
    too_much, why = pa.apply_explore(HELD, {"amb1": 0.25}, BOUNDS)
    assert too_much == HELD and "not fundable" in why
    over_bound, why = pa.apply_explore(HELD, {"amb1": 0.06}, BOUNDS)
    assert over_bound == HELD and "exceeds its bound" in why
    # A held book already carrying MORE exploration than this draw: incumbents would have to
    # grow to keep the total; the book stands as held and the reason names it.
    held_more = {**HELD, "amb1": 0.02}
    stands, why = pa.apply_explore(held_more, {"amb1": 0.005}, BOUNDS)
    assert stands == held_more and "would have to grow" in why
    nothing, why = pa.apply_explore({}, {"amb1": 0.005}, BOUNDS)
    assert nothing == {} and "no held book" in why


def test_the_counterfactual_hands_the_lent_heat_back_pro_rata() -> None:
    lent = _explore(1)["explore_heat"]
    book, _ = pa.apply_explore(HELD, lent, BOUNDS)
    without = pa.without_explore(book, lent)
    assert set(without) == set(HELD)
    assert sum(without.values()) == pytest.approx(sum(HELD.values()), abs=1e-9)
    for k, v in HELD.items():
        assert without[k] == pytest.approx(v)
    assert pa.without_explore({"amb1": 0.01}, {"amb1": 0.01}) == {}


# ------------------------------------------------------------------------ end to end and run()
def test_the_scan_publishes_an_explore_block_that_only_holds_candidates_inside_the_margin():
    held, diversifier, star = _book_and_two_candidates()
    doc = _scan(held, diversifier, star, explore_seed=1)
    ex = doc["explore"]
    assert ex["status"] in ("NONE", "FUNDED") and ex["applied"] is False
    assert ex["bar"] == pytest.approx(doc["margin_per_day"])
    for name in ex.get("band") or {}:
        row = doc["candidates"][name]
        assert row["admit"] is False and row["heat_earned"] > 1e-5
        assert abs(row["delta_elogw_per_day"]) <= doc["margin_per_day"] + 1e-15
    assert "explore_thompson" in ex["rule"]


def test_the_missed_growth_line_bills_the_pair_and_a_pass_that_lent_nothing_is_a_zero() -> None:
    r = rails.rail("explore_thompson")
    assert mg.measure_explore(r, {}, {})["verdict"] == "UNMEASURED"
    assert mg.measure_explore(r, {"heat": {}}, {})["verdict"] == "UNMEASURED"
    none = mg.measure_explore(r, {"admission": {"explore": {"status": "NONE",
                                                            "why": "nothing ambiguous"}}}, {})
    assert none["verdict"] == "NOT_BINDING" and none["why"] == "nothing ambiguous"
    unapplied = mg.measure_explore(r, {"admission": {"explore": {"status": "FUNDED",
                                                                 "applied": False}}}, {})
    assert unapplied["verdict"] == "NOT_BINDING"
    billed = mg.measure_explore(r, {"admission": {"explore": {
        "status": "FUNDED", "applied": True, "growth_with": 0.00190, "growth_without": 0.00200,
        "band": {"a": {}, "b": {}}, "explore_heat_total": 0.009}}}, {})
    assert billed["verdict"] == "SAMPLE" and billed["sample"] is True
    assert billed["value_logw_per_day"] == pytest.approx(-0.0001)
    assert billed["n_explored"] == 2


def test_run_explores_before_the_proof_on_the_published_book_and_never_moves_the_total() -> None:
    src = inspect.getsource(pa.run)
    i_bind = src.index("book, funded = bind_verdict(nt, prev_book, held, book, funded)")
    i_adm = src.index("admission = marginal_admission(")
    i_apply = src.index("explored, e_why = apply_explore(base_now, lend, adm_bounds)")
    i_proof = src.index("proof = contest(ev, funded, current_book()")
    i_cert = src.index("certify(proof, root=ROOT, book=funded)")
    assert i_bind < i_adm < i_apply < i_proof < i_cert, (
        "exploration must be applied to the PUBLISHED book before the contest certifies it")
    assert "warm=prev_admission.get(\"warm\") or {}" in src, "partial solves must be carried"
    assert 'strftime("%Y%m%d")' in src, "one draw per UTC day"
    assert "total_heat=float(sum(explored.values()))" in src
    assert 'book.total_heat if nt.get("binding") else verdict.total_heat' in src

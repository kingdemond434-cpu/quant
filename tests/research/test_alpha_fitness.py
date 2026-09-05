"""The portfolio-aware fitness, term by term, on synthetic data with a known answer.

THE PIN THIS SUITE EXISTS FOR is `test_a_tail_payer_outranks_a_correlated_winner`: a series with a
WORSE standalone Sharpe that pays in the book's worst decile must outrank a higher-Sharpe series
that is a near-copy of the book. That single ordering is the whole point of the rewrite -- the old
scalar got it backwards, and any future change that gets it backwards again fails here.

Everything else pins one term at a time: that it measures what it says on data built to have that
property, and that where it cannot measure it returns 0.0 AND names itself in `unmeasured` rather
than passing a silent zero off as a measurement.

No network, no files the desk owns; every path is a tmp_path.
"""
from __future__ import annotations

import json
import math

import numpy as np
import pandas as pd
import pytest

from libs.research import alpha_fitness as af


def _days(n: int, start: str = "2024-01-01") -> pd.DatetimeIndex:
    return pd.date_range(start, periods=n, freq="D", tz="UTC")


def _book(n: int = 400, seed: int = 0) -> pd.Series:
    rng = np.random.default_rng(seed)
    return pd.Series(rng.normal(0.01, 0.05, n), index=_days(n))


# --------------------------------------------------------------------------- THE PIN
def test_a_tail_payer_outranks_a_correlated_winner() -> None:
    """A worse Sharpe that pays when the book bleeds beats a better Sharpe that does not."""
    book = _book()
    rng = np.random.default_rng(7)
    thr = float(book.quantile(af.TAIL_Q))
    tail_payer = pd.Series(rng.normal(0.0, 0.03, len(book)), index=book.index)
    tail_payer[book <= thr] += 0.10                      # pays exactly on the book's worst days
    correlated = 0.9 * book + pd.Series(rng.normal(0.02, 0.01, len(book)), index=book.index)
    assert correlated.mean() / correlated.std() > tail_payer.mean() / tail_payer.std()

    bk = af.Book(daily=book, source="synthetic")
    a = af.evaluate(af.Candidate(daily=tail_payer, name="tail_payer", refs=(correlated,)), bk)
    b = af.evaluate(af.Candidate(daily=correlated, name="correlated", refs=(tail_payer,)), bk)
    assert a.score() > b.score(), (a.as_dict(), b.as_dict())
    assert a.tail > 0.0 > b.tail
    # and the ordering survives the multi-objective sort, which is what selection actually uses
    assert af.nsga2_order([a, b])[0] == 0
    # ... and it is the TAIL that carries it: on the same data with no book, it does not hold
    empty = af.Book()
    a0 = af.evaluate(af.Candidate(daily=tail_payer, name="tail_payer", refs=(correlated,)), empty)
    b0 = af.evaluate(af.Candidate(daily=correlated, name="correlated", refs=(tail_payer,)), empty)
    assert b0.score() > a0.score()
    assert "tail" in a0.unmeasured and a0.tail == 0.0


# --------------------------------------------------------------------------- the tail term
def test_tail_term_conditions_on_the_books_own_worst_decile() -> None:
    book = _book(300, seed=3)
    idx = book.index
    thr = float(book.quantile(af.TAIL_Q))
    pays = pd.Series(0.0, index=idx)
    pays[book <= thr] = 1.0
    value, detail, why = af.tail_term(pays, book)
    assert detail["tail_days"] == int((book <= thr).sum()) == 30
    assert detail["tail_contribution"] == pytest.approx(1.0)
    assert value > 0 and "q10" in why
    # the mirror image: a series that pays only on the book's BEST days is negative there
    hurts = pd.Series(0.0, index=idx)
    hurts[book >= float(book.quantile(0.9))] = 1.0
    v2, d2, _ = af.tail_term(hurts, book)
    assert d2["tail_contribution"] == pytest.approx(0.0) and v2 == pytest.approx(0.0)
    # tail novelty rides along: a copy of the book is not independent in the book's own tail
    _v, d3, _w = af.tail_term(book, book)
    assert d3["tail_novelty"] is not None and d3["tail_novelty"] < 0.5


def test_tail_term_names_every_way_it_cannot_be_measured() -> None:
    short = _book(10)
    v, d, why = af.tail_term(short, short)
    assert v == 0.0 and "unmeasured" in why and d["tail_days"] == 0
    book = _book(200)
    away = pd.Series(1.0, index=_days(200, "2030-01-01"))
    v, _d, why = af.tail_term(away, book)
    assert v == 0.0 and "unmeasured" in why           # no overlapping days at all
    flat = pd.Series(0.0, index=book.index)
    v, _d, why = af.tail_term(flat, book)
    assert v == 0.0 and "no dispersion" in why


# --------------------------------------------------------------------------- the other terms
def test_oos_is_the_holdout_t_and_the_split_is_chronological() -> None:
    idx = _days(400)
    # flat in the train slice, strongly positive in the holdout: an in-sample t would miss it
    v = np.zeros(400)
    v[280:] = 1.0
    got, why = af.oos_term(pd.Series(v + 1e-9 * np.arange(400), index=idx))
    assert got > 5.0 and "holdout" in why
    assert af.oos_term(pd.Series(np.zeros(10)))[0] == 0.0
    assert "unmeasured" in af.oos_term(pd.Series(np.zeros(10)))[1]


def test_novelty_is_one_minus_the_largest_absolute_correlation() -> None:
    idx = _days(200)
    rng = np.random.default_rng(2)
    a = pd.Series(rng.normal(size=200), index=idx)
    assert af.novelty_term(a, [a])[0] == pytest.approx(0.0, abs=1e-9)
    assert af.novelty_term(a, [-a])[0] == pytest.approx(0.0, abs=1e-9)   # sign-blind
    b = pd.Series(rng.normal(size=200), index=idx)
    assert 0.6 < af.novelty_term(a, [b])[0] <= 1.0
    # an absence of comparison is not evidence of difference: 0.0 and named, not a free bonus
    got, why = af.novelty_term(a, [])
    assert got == 0.0 and "unmeasured" in why


def test_state_breadth_counts_only_admitted_buckets() -> None:
    idx = _days(500)
    state = pd.Series(np.linspace(-2, 2, 500), index=idx)
    # pays only in the top two quintiles of the state, so the answer is 2 of 5 by construction
    forward = pd.Series(np.where(state > 0.4, 0.01, -0.01), index=idx)
    got, detail, why = af.state_breadth(state, forward)
    assert detail["admitted"] == 5 and detail["positive"] == 2
    assert got == pytest.approx(2 / 5) and "admitted state buckets" in why
    everywhere = pd.Series(0.01, index=idx)
    assert af.state_breadth(state, everywhere)[0] == pytest.approx(1.0)
    # a bucket under MIN_STATE_OBS is not admitted, so a finely sliced state cannot inflate it
    tiny = pd.Series(np.linspace(-2, 2, 40), index=_days(40))
    got, detail, why = af.state_breadth(tiny, pd.Series(0.01, index=tiny.index))
    assert got == 0.0 and "unmeasured" in why and detail["admitted"] == 0
    flat_state = pd.Series(1.0, index=idx)
    assert "unmeasured" in af.state_breadth(flat_state, forward)[2]


def test_capacity_is_a_named_proxy_and_absence_is_not_fullness() -> None:
    at_ref, why = af.capacity_term(af.CAPACITY_SPREAD_REF, af.CAPACITY_TICKS_REF)
    assert at_ref == pytest.approx(0.5) and "proxy" in why
    assert af.capacity_term(0.0, af.CAPACITY_TICKS_REF)[0] == pytest.approx(1.0)
    assert af.capacity_term(af.CAPACITY_SPREAD_REF, 1.0)[0] < 0.01     # thin book, no capacity
    got, why = af.capacity_term(None, None)
    assert got == 0.0 and "unmeasured" in why


def test_cost_is_the_round_trip_as_a_multiple_of_the_gross_edge() -> None:
    assert af.cost_term(1e-4, 2e-4)[0] == pytest.approx(0.5)
    assert af.cost_term(2e-4, 2e-4)[0] == pytest.approx(1.0)
    assert af.cost_term(1e-2, 1e-4)[0] == 3.0                          # capped, and meant to be
    assert af.cost_term(1e-4, 0.0)[0] == 3.0
    got, why = af.cost_term(None, 1e-4, "XAUUSD")
    assert got == 0.0 and "unmeasured" in why and "XAUUSD" in why


def test_fragility_counts_losses_only_and_names_the_worst_parameter() -> None:
    def knife(p):
        return 10.0 if int(p["hold"]) == 8 else 0.0
    got, detail, why = af.fragility(knife, {"hold": 8}, pct=0.5)
    assert got == pytest.approx(1.0) and detail["worst_param"] == "hold" and "+-50%" in why

    def flat(_p):
        return 3.0
    assert af.fragility(flat, {"hold": 8, "z": 1.5})[0] == pytest.approx(0.0)

    def better(p):
        return 1.0 + float(p["z"])
    # a perturbation that scores HIGHER is not robustness; only losses count -- so the -20%
    # move contributes (2.5 - 2.2) / 2.5 and the +20% move contributes nothing, over two moves
    assert af.fragility(better, {"z": 1.5})[0] == pytest.approx(0.5 * (0.3 / 2.5), abs=1e-9)
    assert "unmeasured" in af.fragility(flat, {})[2]

    def boom(_p):
        raise RuntimeError("no signals")
    assert af.fragility(boom, {"z": 1.5})[0] == 0.0


def test_multiplicity_is_the_gauntlets_own_deflation() -> None:
    from libs.validation.dsr import expected_max_sharpe
    got, why = af.multiplicity_term(500, variance_of_sharpes=0.25)
    assert got == pytest.approx(expected_max_sharpe(500, 0.25))
    assert "E[max Sharpe" in why
    wider, _ = af.multiplicity_term(50_000, variance_of_sharpes=0.25)
    assert wider > got                                     # a wider haystack costs more
    assert af.multiplicity_term(1, variance_of_sharpes=0.25)[0] == 0.0
    measured, why = af.multiplicity_term(100, sharpes=[0.1, 0.5, -0.3, 0.9])
    assert measured > 0 and ("dispersion" in why or "gate_policy" in why)
    got, why = af.multiplicity_term(100)
    assert (got == 0.0 and "unmeasured" in why) or "gate_policy" in why


# --------------------------------------------------------------------------- the vector
def test_the_score_is_the_declared_formula_and_penalties_subtract() -> None:
    t = af.FitnessTerms(delta_elog=1.0, oos=2.0, novelty=1.0, tail=1.0, state_breadth=1.0,
                        capacity=1.0, cost=1.0, fragility=1.0, complexity=10.0,
                        multiplicity=1.0)
    w = af.WEIGHTS
    expect = (w["delta_elog"] + 2 * w["oos"] + w["novelty"] + w["tail"] + w["state_breadth"]
              + w["capacity"] - w["cost"] - w["fragility"] - 10 * w["complexity"]
              - w["multiplicity"])
    assert t.score() == pytest.approx(expect)
    assert {"cost", "fragility", "complexity", "multiplicity"} == af.PENALTIES
    assert set(af.WEIGHTS) == set(t.as_dict())
    # every penalty is signed negative as an objective, every credit positive
    obj = t.objectives()
    assert all(obj[k] <= 0 for k in af.PENALTIES if w[k] > 0)
    assert all(obj[k] >= 0 for k in set(af.WEIGHTS) - af.PENALTIES if w[k] > 0)
    # weights are an argument, not a hard-coded law
    assert t.score({"tail": 100.0}) == pytest.approx(100.0)


def test_every_unmeasured_term_is_named_rather_than_silently_zero() -> None:
    bare = af.evaluate(af.Candidate(daily=_book(60)), af.Book())
    assert bare.as_dict()["delta_elog"] == 0.0
    for name in ("delta_elog", "tail", "capacity", "fragility", "state_breadth", "novelty"):
        assert name in bare.unmeasured, (name, bare.unmeasured)
        assert bare.why[name]
    assert set(bare.why) == set(af.WEIGHTS)
    assert "no book to measure against" in bare.why["delta_elog"]


def test_the_growth_term_uses_the_allocators_own_solver() -> None:
    """dE[logW_P] is `marginal_delta_elog`, not a correlation haircut standing in for it."""
    robust_elog = pytest.importorskip("libs.portfolio.robust_elog")
    rng = np.random.default_rng(11)
    n = 260
    held = rng.normal(0.02, 0.4, n)
    sleeves = (robust_elog.SleeveEvidence(name="gold", daily_r=held, forward_days=120),)
    book = af.Book(daily=pd.Series(held, index=_days(n)), sleeves=sleeves, hard_cap=0.35,
                   source="synthetic one-sleeve book")
    cfg = robust_elog.WorldConfig(n_worlds=32, n_rows=96)
    idx = _days(n)
    # SAME mean and SAME dispersion as the book's sleeve, opposite swings: the only difference
    # between the two candidates is whether they pay when the sleeve does.
    diversifier = pd.Series(2 * held.mean() - held, index=idx)
    clone = pd.Series(held, index=idx) + rng.normal(0.0, 1e-6, n)
    d_div, why = af.delta_elog_term(book, diversifier, name="diversifier", cfg=cfg)
    d_clone, _ = af.delta_elog_term(book, clone, name="clone", cfg=cfg)
    assert "marginal_delta_elog" in why and math.isfinite(d_div) and math.isfinite(d_clone)
    assert d_div > d_clone                              # independence is worth more than a copy
    # and a candidate already in the book is refused rather than double counted
    got, why = af.delta_elog_term(book, pd.Series(held, index=idx), name="gold", cfg=cfg)
    assert got == 0.0 and "unmeasured" in why


# --------------------------------------------------------------------------- the book
def test_load_book_prefers_the_allocator_artifact_and_names_what_it_used(tmp_path) -> None:
    n = 120
    idx = [str(d.date()) for d in _days(n)]
    frame = pd.DataFrame({"gold_a": np.linspace(-0.1, 0.1, n),
                          "fx_b": np.linspace(0.1, -0.1, n)}, index=idx)
    daily = tmp_path / "daily_r.parquet"
    frame.to_parquet(daily)
    alloc = tmp_path / "pf_allocation.json"
    alloc.write_text(json.dumps({"book": {"gold_a": 0.2, "fx_b": 0.1}, "hard_cap": 0.3}))
    book = af.load_book(allocation=alloc, daily=daily, sleeves_json=tmp_path / "absent.json")
    assert not book.is_empty and book.hard_cap == 0.3
    assert "2 funded sleeves" in book.source and len(book.daily) == n
    assert book.daily.iloc[0] == pytest.approx(0.2 * -0.1 + 0.1 * 0.1)
    assert len(book.sleeves) == 2


def test_load_book_falls_through_to_the_sleeve_list_then_to_an_empty_book(tmp_path) -> None:
    sleeves = tmp_path / "sleeves.json"
    sleeves.write_text(json.dumps({"sleeves": [
        {"name": "a", "daily_r": [0.1, -0.2, 0.3]},
        {"name": "b", "daily_r": [0.0, 0.1, -0.1]}]}))
    book = af.load_book(allocation=tmp_path / "no.json", daily=tmp_path / "no.parquet",
                        sleeves_json=sleeves)
    assert "sleeves.json" in book.source and len(book.daily) == 3
    empty = af.load_book(allocation=tmp_path / "no.json", daily=tmp_path / "no.parquet",
                         sleeves_json=tmp_path / "no2.json")
    assert empty.is_empty and "empty book" in empty.source
    # a corrupt artifact is a fall-through, not an exception into the search
    bad = tmp_path / "bad.json"
    bad.write_text("{not json")
    assert af.load_book(allocation=bad, daily=tmp_path / "no.parquet",
                        sleeves_json=tmp_path / "no2.json").is_empty


# --------------------------------------------------------------------------- NSGA-II
def test_non_dominated_sort_keeps_the_specialist_the_scalar_would_delete() -> None:
    rows = [{"tail": 10.0, "cost": -5.0},        # best tail, worst cost
            {"tail": 1.0, "cost": -1.0},         # best cost, worst tail
            {"tail": 0.5, "cost": -2.0}]         # dominated by BOTH
    fronts = af.non_dominated_sort(rows)
    assert fronts[0] == [0, 1] and fronts[1] == [2]
    dist = af.crowding_distance(rows, fronts[0])
    assert dist[0] == math.inf and dist[1] == math.inf
    assert af.non_dominated_sort([{"a": 1.0}]) == [[0]]
    assert af.non_dominated_sort([]) == []


def test_nsga2_order_ranks_by_front_then_by_crowding() -> None:
    specialist = af.FitnessTerms(tail=4.0, cost=9.0)          # extraordinary tail, awful cost
    allrounder = af.FitnessTerms(tail=1.0, cost=0.5)
    mediocre = af.FitnessTerms(tail=0.4, cost=1.0)
    order = af.nsga2_order([specialist, allrounder, mediocre])
    assert order.index(2) == 2                                 # the dominated one sorts last
    assert set(order[:2]) == {0, 1}
    assert specialist.score() < allrounder.score()             # the scalar disagrees, on purpose

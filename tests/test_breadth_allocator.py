from libs.ops.breadth_allocator import (
    Candidate,
    Limits,
    allocate,
    coverage_report,
)


def _c(i, sym="EURUSD", tf="H1", fam="trend", **kw):
    return Candidate(cell_id=f"c{i}", symbol=sym, timeframe=tf, family=fam, **kw)


def test_concentrated_pile_is_capped_and_spread_wins():
    pile = [_c(i, base_score=2.0) for i in range(50)]
    spread = [
        _c(100 + i, sym=s, tf=t, fam=f)
        for i, (s, t, f) in enumerate(
            (s, t, f)
            for s in ("XAUUSD", "US500", "USDJPY")
            for t in ("M15", "D1")
            for f in ("carry", "mean_reversion")
        )
    ]
    d = allocate(pile + spread, Limits(budget=20, cell_share=0.1))
    pile_taken = sum(1 for c in d.selected if c.key == ("EURUSD", "H1", "trend"))
    assert pile_taken <= 2
    assert len({c.key for c in d.selected}) >= 12
    assert any(r == "cell_cap" for _, r in d.deferred)


def test_near_duplicate_goes_to_back_and_orthogonal_first():
    dup = _c(1, sym="GBPUSD", corr_to_book=0.95)
    half = _c(2, sym="AUDUSD", corr_to_book=0.5)
    orth = _c(3, sym="NZDUSD", corr_to_book=0.05)
    d = allocate([dup, half, orth], Limits(budget=2, quota_per_empty_cell=0))
    assert [c.cell_id for c in d.selected] == ["c3", "c2"]
    assert d.deferred[0][1] == "near_duplicate_of_book"


def test_exotic_needs_cost_room():
    exotic_fast = _c(1, sym="USDTRY", tf="M5", cost_bps=30.0)
    exotic_slow = _c(2, sym="USDZAR", tf="D1", cost_bps=15.0)
    major_fast = _c(3, sym="EURUSD", tf="M5", cost_bps=0.6)
    d = allocate([exotic_fast, exotic_slow, major_fast], Limits(budget=10))
    ids = {c.cell_id for c in d.selected}
    assert ids == {"c2", "c3"}
    assert {c.cell_id: r for c, r in d.deferred}["c1"] == (
        "cost_exceeds_timeframe_budget"
    )


def test_under_covered_cells_get_quota_before_crowded():
    crowded = [_c(i, base_score=5.0) for i in range(5)]
    empty = _c(99, sym="XAGUSD", tf="H4", fam="seasonality", base_score=0.1)
    cov = {("EURUSD", "H1", "trend"): 400}
    d = allocate([*crowded, empty], Limits(budget=1), coverage=cov)
    assert d.selected[0].cell_id == "c99"


def test_family_cap_holds():
    cands = [_c(i, sym=f"S{i}", fam="trend") for i in range(30)]
    cands += [_c(100 + i, sym=f"S{i}", fam="carry") for i in range(30)]
    d = allocate(cands, Limits(budget=20, family_share=0.5, symbol_share=1.0))
    fams = [c.family for c in d.selected]
    assert fams.count("trend") <= 10 and fams.count("carry") <= 10


def test_nothing_is_dropped():
    cands = [_c(i) for i in range(10)]
    d = allocate(cands, Limits(budget=3))
    assert len(d.selected) + len(d.deferred) == 10


def test_coverage_report_flags_concentration():
    keys = [("EURUSD", "H1", "trend")] * 9 + [("XAUUSD", "D1", "carry")]
    r = coverage_report(keys)
    assert r["symbol"]["top"] == "EURUSD"
    assert r["symbol"]["top_share"] == 0.9
    assert r["symbol"]["effective_n"] < 1.3
    assert coverage_report([]) == {"n": 0}


def test_yield_multipliers_shrink_and_floor():
    from libs.ops.breadth_allocator import yield_multipliers

    stats = {
        ("EURUSD", "H1", "trend"): (160000, 48),
        ("XAUUSD", "M15", "flow"): (4000, 100),
        ("US500", "D1", "carry"): (5, 0),
    }
    m = yield_multipliers(stats)
    assert m[("XAUUSD", "M15", "flow")] > 1.0
    assert m[("EURUSD", "H1", "trend")] >= 0.25
    assert 0.25 <= m[("US500", "D1", "carry")] <= 1.1


def test_evolve_raises_quota_when_empty_cells_win_and_tightens_on_decay():
    from libs.ops.breadth_allocator import evolve_limits

    lim = Limits(budget=100)
    hist = [
        {"effective_n_cells": 50, "orth_edges": 20, "trials": 1000,
         "edges_from_empty": 2, "trials_from_empty": 100},
        {"effective_n_cells": 48, "orth_edges": 10, "trials": 1000,
         "edges_from_empty": 5, "trials_from_empty": 100},
    ]
    new, journal = evolve_limits(lim, hist)
    assert new.quota_per_empty_cell == 2
    assert new.cell_share < lim.cell_share
    assert new.dup_corr == lim.dup_corr
    assert len(journal) == 2


def test_evolve_needs_history():
    from libs.ops.breadth_allocator import evolve_limits

    lim = Limits(budget=10)
    assert evolve_limits(lim, [])[0] is lim


def test_novelty_rejects_factor_copy_and_scores_marginal():
    import numpy as np

    from libs.ops.breadth_allocator import novelty, residualise

    rng = np.random.default_rng(7)
    t = 750
    mkt = rng.normal(0, 1, t)
    pooled = 0.5 * mkt + rng.normal(0, 1, t)
    pool_res = [residualise(pooled, mkt)]
    copy = 2.0 * mkt + pooled + rng.normal(0, 0.2, t)  # pooled edge + beta
    fresh = 0.3 * mkt + rng.normal(0.05, 1, t)  # own alpha, independent noise
    book = pooled

    v_copy = novelty(copy, factors=mkt, pool_residuals=pool_res, book_returns=book)
    v_fresh = novelty(fresh, factors=mkt, pool_residuals=pool_res, book_returns=book)
    assert v_copy["reject"] and v_copy["pool_corr"] > 0.9
    assert not v_fresh["reject"] and v_fresh["pool_corr"] < 0.2
    assert v_fresh["marginal"] > v_copy["marginal"]


def test_beta_only_candidate_is_not_novel_after_residualising():
    import numpy as np

    from libs.ops.breadth_allocator import max_pool_corr, residualise

    rng = np.random.default_rng(1)
    mkt = rng.normal(0, 1, 500)
    a = mkt + rng.normal(0, 0.3, 500)
    b = mkt + rng.normal(0, 0.3, 500)
    raw = abs(np.corrcoef(a, b)[0, 1])
    assert raw > 0.8
    assert max_pool_corr(residualise(a, mkt), [residualise(b, mkt)]) < 0.2


def test_every_performance_scored_candidate_is_charged():
    scored = [_c(i, sym=f"S{i}", base_score=1.0 + i, performance_scored=True)
              for i in range(10)]
    unscored = [_c(100 + i, sym=f"U{i}") for i in range(5)]
    d = allocate([*scored, *unscored], Limits(budget=3))
    charged = {c.cell_id for c in d.charged}
    assert {c.cell_id for c in scored} <= charged
    assert {c.cell_id for c in d.selected} <= charged
    picked = {c.cell_id for c in d.selected}
    assert not ({c.cell_id for c in unscored} - picked) & charged
    assert len(d.charged) == len(charged)


def test_novelty_with_book_marks_charge_and_pool_reject_alone_does_not():
    import numpy as np

    from libs.ops.breadth_allocator import novelty

    rng = np.random.default_rng(3)
    x = rng.normal(0, 1, 300)
    assert novelty(x, book_returns=rng.normal(0, 1, 300))["charge"] is True
    assert novelty(x, pool_residuals=[x])["charge"] is False

"""R0141 sleeve allocator -- more sleeves only multiply growth if they are INDEPENDENT.

Correlated sleeves draw down together: risk scales with N, growth with 1, and the desk pays N sets
of costs for one bet. These tests pin that independence actually buys deployable risk, that
duplication does not, and that an unmeasured pair is assumed to be the same bet.
"""
from __future__ import annotations

import json
import math
import random

from scripts.run_sleeve_allocator import (DUPLICATE_RHO, MIN_OVERLAP, SEED_SHARE, TOTAL_HEAT,
                                          allocate, standalone_growth)


def _book(tmp_path, corr, n=30, seed=5):
    random.seed(seed)
    (tmp_path / "data").mkdir(exist_ok=True)
    marks = []
    for i in range(n):
        a = random.gauss(0.01, 0.06)
        b = corr * a + math.sqrt(max(0.0, 1 - corr ** 2)) * random.gauss(0.01, 0.06)
        day = f"2026-06-{i % 28 + 1:02d}T{i % 24:02d}:00:00+00:00"
        marks += [{"kind": "conviction", "closed": True, "equity_return": a, "exit_at": day},
                  {"kind": "event", "closed": True, "equity_return": b, "exit_at": day}]
    (tmp_path / "data/paper_book_pnl.json").write_text(json.dumps({"marks": marks}))


def test_independence_buys_deployable_risk_and_duplication_does_not(tmp_path):
    # THE WHOLE POINT. An earlier version normalised shares to 1, so two perfect duplicates got the
    # same total heat as two independent sleeves -- the exact failure this organ exists to prevent,
    # committed inside the organ itself.
    _book(tmp_path, 0.02)
    indep = allocate(tmp_path)
    _book(tmp_path, 0.95)
    dup = allocate(tmp_path)
    assert indep["total_deployed"] > dup["total_deployed"] * 1.2
    assert indep["status"] == "DIVERSIFIED" and dup["status"] == "DUPLICATION"


def test_correlation_adjusted_risk_never_exceeds_the_cap(tmp_path):
    # total_deployed is NOMINAL and exceeds the cap when diversified -- that is correct portfolio
    # arithmetic. What must hold is the CORRELATION-ADJUSTED figure.
    for corr in (0.02, 0.5, 0.95):
        _book(tmp_path, corr)
        rep = allocate(tmp_path)
        w = [s["risk_budget"] for s in rep["sleeves"].values()]
        rho = list(rep["pairs"].values())[0].get("rho", 1.0)
        adj = math.sqrt(sum(a * b * (1.0 if i == j else abs(rho))
                            for i, a in enumerate(w) for j, b in enumerate(w)))
        # tolerance is 1e-3, not 0: risk_budget is published rounded to 4dp, so two sleeves can
        # each round up by 5e-5 and the recomputed figure lands microns over. That is a display
        # rounding artifact, not a breach -- and stating the reason is why the number is loose.
        assert adj <= TOTAL_HEAT + 1e-3, f"corr-adjusted {adj} over cap at rho={rho}"


def test_an_unmeasured_pair_is_assumed_to_be_the_same_bet(tmp_path):
    # Assuming independence with no overlapping history would hand full risk to what may be a
    # duplicate. The assumption that costs money when wrong is the one that gets made.
    _book(tmp_path, 0.02, n=MIN_OVERLAP - 5)
    rep = allocate(tmp_path)
    pair = list(rep["pairs"].values())[0]
    assert pair["state"] == "UNMEASURED" and pair["assumed_rho"] == 1.0
    assert "DUPLICATE" in pair["why"]
    assert rep["status"] == "UNMEASURED"


def test_a_registered_sleeve_with_no_history_still_gets_a_seed(tmp_path):
    # A zero allocation is a sleeve that can never accumulate the record which would earn it more
    # -- idle capacity dressed as prudence (L1.28a).
    rep = allocate(tmp_path)
    for s in rep["sleeves"].values():
        assert s["risk_budget"] > 0 and s["n_closed"] == 0
        assert s["standalone_g"] is None          # absence, never a measured zero


def test_no_sleeve_can_take_the_whole_book_alone(tmp_path):
    _book(tmp_path, 0.02)
    rep = allocate(tmp_path)
    assert all(s["risk_budget"] <= TOTAL_HEAT for s in rep["sleeves"].values())


def test_standalone_growth_is_none_on_no_history_not_zero():
    assert standalone_growth([]) is None
    assert standalone_growth([-1.0]) is None          # a total loss is excluded, not logged as 0
    assert standalone_growth([0.1, -0.05]) is not None


def test_the_allocator_cannot_promote_anything(tmp_path):
    rep = allocate(tmp_path)
    assert "cannot promote" in rep["authority"] and "places no orders" in rep["authority"]
    assert "PAPER" in rep["authority"]


def test_the_duplicate_threshold_is_where_shared_variance_passes_half():
    assert abs(DUPLICATE_RHO ** 2 - 0.49) < 0.01
    assert 0 < SEED_SHARE < 0.5

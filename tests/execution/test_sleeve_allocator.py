"""R0141 sleeve allocator -- more sleeves only multiply growth if they are INDEPENDENT.

Correlated sleeves draw down together: risk scales with N, growth with 1, and the desk pays N sets
of costs for one bet. These tests pin that independence actually buys deployable risk, that
duplication does not, and that an unmeasured pair is assumed to be the same bet.
"""
from __future__ import annotations

import inspect
import json
import math
import random
import sys
from pathlib import Path

from scripts.run_sleeve_allocator import (
    DUPLICATE_RHO,
    MIN_OVERLAP,
    SEED_SHARE,
    TOTAL_HEAT,
    _max_drawdown,
    _persistence,
    _t_stat,
    allocate,
    standalone_growth,
)

from libs.risk.sleeve_allocation import EVIDENCE_LADDER, MIN_CLOSES


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
        rho = next(iter(rep["pairs"].values())).get("rho", 1.0)
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
    pair = next(iter(rep["pairs"].values()))
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


# --- R0357: the principal's evidence ladder must actually GOVERN -------------------------------
# It was implemented in libs/risk/sleeve_allocation.py on 2026-08-01 and imported by nothing, so
# the tiers were fully tested and enforced nothing. These pin the WIRING, which is the half that
# was missing: a green test on the library said nothing about whether the artifact obeyed it.


def test_a_sleeve_below_min_closes_cannot_exceed_the_unproven_cap(tmp_path):
    # THE REGRESSION BAR FOR R0357, and the exact live breach that raised it: the real artifact
    # gave `conviction` 27.3% of heat on 15 closed trades while the ladder's cap for an unproven
    # sleeve is 2%. A strong short record is what a hot streak looks like; sample size is the one
    # thing it cannot fake.
    _book(tmp_path, 0.02, n=MIN_CLOSES - 5)
    rep = allocate(tmp_path)
    for name, s in rep["sleeves"].items():
        ev = s["evidence"]
        assert ev["tier"] == "UNPROVEN", f"{name} reached {ev['tier']} on {s['n_closed']} closes"
        assert s["risk_budget"] <= EVIDENCE_LADDER[0][1] + 1e-9, (
            f"{name} drew {s['risk_budget']:.1%} on {s['n_closed']} closes")
        # L1.51: the clamp must name what would lift it, not merely refuse.
        assert "closes" in ev["blocker"] and str(s["n_closed"]) in ev["blocker"]


def test_the_ladder_is_a_ceiling_and_never_a_floor(tmp_path):
    # A wiring mistake in a CEILING can only ever under-fund. If this ever inverts, the ladder
    # could hand a sleeve size the correlation arithmetic refused -- which is strictly worse than
    # the unwired state it replaced, because it would arrive wearing the law's name.
    for corr in (0.02, 0.5, 0.95):
        for n in (2, MIN_CLOSES - 5, 40):
            _book(tmp_path, corr, n=n)
            for s in allocate(tmp_path)["sleeves"].values():
                assert s["risk_budget"] <= s["risk_budget_uncapped"] + 1e-9


def test_the_clamp_is_priced_and_the_total_is_the_sum_of_its_parts(tmp_path):
    # L1.51: an unpriced clamp is an argument the desk cannot have. `held_back` is the heat the
    # correlation arithmetic granted and evidence refused, and zero must mean "not binding"
    # rather than "nobody measured it".
    _book(tmp_path, 0.02, n=MIN_CLOSES - 5)
    rep = allocate(tmp_path)
    total = 0.0
    for s in rep["sleeves"].values():
        assert s["evidence"]["held_back"] == round(
            s["risk_budget_uncapped"] - s["risk_budget"], 4)
        assert s["evidence"]["held_back"] > 0          # this fixture IS clamped
        total += s["evidence"]["held_back"]
    assert abs(rep["evidence_ladder"]["held_back_total"] - total) < 1e-9


def test_the_rungs_are_imported_never_restated_here():
    # The defect R0357 names is TWO COPIES of a law, one of them dead. A second declaration of the
    # tier names in this script is how the copies drift apart again, so the script must carry the
    # rungs only by import.
    src = Path(inspect.getfile(sys.modules["scripts.run_sleeve_allocator"])).read_text("utf-8")
    body = src.split('"""', 2)[-1]                     # module docstring may legitimately cite them
    for tier in ("INITIAL", "STRONG", "DURABLE"):
        assert f'"{tier}"' not in body and f"'{tier}'" not in body, (
            f"{tier} is re-declared in the allocator -- import it from libs.risk.sleeve_allocation")


def test_statistics_nobody_measured_cannot_buy_a_rung(tmp_path):
    # Every ladder input defaults to the value that FAILS the higher rungs. An untagged record has
    # no regime breadth, so STRONG (min_regimes_positive 2) must stay out of reach however good
    # the returns are -- absence is not evidence of breadth.
    _book(tmp_path, 0.02, n=80)
    rep = allocate(tmp_path)
    for s in rep["sleeves"].values():
        assert s["evidence"]["regimes_positive"] == 0   # fixture carries no setup.vol_regime tags
        assert s["evidence"]["tier"] in ("UNPROVEN", "INITIAL")


def test_regime_breadth_is_read_from_the_tag_the_promotion_gate_uses(tmp_path):
    # check_promotion_gate.py reads setup.vol_regime for its two_regimes criterion. If the ladder
    # read a different tag the two organs could disagree about how many tapes one record spans.
    (tmp_path / "data").mkdir(exist_ok=True)
    marks = [{"kind": "conviction", "closed": True, "equity_return": 0.02,
              "exit_at": f"2026-06-{i % 28 + 1:02d}T00:00:00+00:00",
              "setup": {"vol_regime": ["HIGH", "LOW", "UNKNOWN"][i % 3]}} for i in range(60)]
    (tmp_path / "data/paper_book_pnl.json").write_text(json.dumps({"marks": marks}))
    ev = allocate(tmp_path)["sleeves"]["conviction"]["evidence"]
    assert ev["regimes_positive"] == 2                  # HIGH and LOW; UNKNOWN is not a regime


def test_drawdown_and_persistence_refuse_to_flatter_an_empty_record():
    # A sleeve with no history must not clear a drawdown rung by having no drawdown to show.
    assert _max_drawdown([]) == 1.0
    assert _max_drawdown([0.5, -0.5]) > 0
    assert _persistence([0.1, 0.1]) == 0.0              # too short to measure -> fails upward
    assert _t_stat([0.01]) == 0.0                       # one trade is not a t-statistic

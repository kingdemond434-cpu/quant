"""RANK 5 fusion search. The properties that stop a combinatorial search being a noise-mining rig.

Three, and all three must be STRUCTURAL rather than advisory:
  * an axis that failed its own single-axis screen may not enter combination search;
  * a cheaply-pruned cell STILL costs a trial (pre_filter's rule: compute is saved, multiplicity
    never is) -- and finding a survivor early does not shrink the bill either;
  * the grid is hashed before compute, so it cannot be grown after results are seen.
Break any one and the engine returns a beautiful fake survivor on every run.
"""

from __future__ import annotations

import numpy as np
import pytest

from libs.research.fusion_search import (
    DEFAULT_K,
    EARNING_VERDICT,
    MAX_CELLS,
    REPRESENTATIONS,
    FusionCell,
    FusionPlan,
    eligibility_from_screens,
    plan_search,
    run_search,
)


def _earned(*axes: str) -> list:
    return eligibility_from_screens(dict.fromkeys(axes, EARNING_VERDICT))


class TestBreadthIsEarnedNotAssumed:
    def test_an_axis_that_failed_its_own_screen_is_excluded(self) -> None:
        el = eligibility_from_screens({"netflow": "no_edge"})
        assert not el[0].earned
        assert "breadth is EARNED" in el[0].reason

    def test_only_the_earning_verdict_qualifies(self) -> None:
        for weak in ("no_edge", "TIMING-ARTIFACT", "SUSPECT-LOOKAHEAD", "SCREEN-UNDERPOWERED", ""):
            assert not eligibility_from_screens({"x": weak})[0].earned

    def test_todays_desk_searches_nothing_and_says_why(self) -> None:
        """Real graveyard verdicts: the correct output is a refusal, not a grid."""
        plan = plan_search(eligibility_from_screens({
            "exchange_netflow": "no_edge",
            "aggregate_positioning": "no_edge",
            "kimchi_premium": "TIMING-ARTIFACT",
        }))
        assert plan.cells == []
        assert plan.refused_reason and "earned breadth" in plan.refused_reason
        assert plan.effective_n_trials == 0

    def test_a_grid_needs_k_earned_axes(self) -> None:
        assert plan_search(_earned("a", "b"), k=3).cells == []
        assert plan_search(_earned("a", "b", "c"), k=3).cells

    def test_excluded_axes_are_reported_never_dropped(self) -> None:
        plan = plan_search(_earned("a", "b", "c") + eligibility_from_screens({"dead": "no_edge"}))
        assert [e.axis for e in plan.excluded] == ["dead"]

    def test_a_mixed_pool_only_combines_the_earned_ones(self) -> None:
        el = _earned("a", "b", "c") + eligibility_from_screens({"dead": "no_edge"})
        plan = plan_search(el, k=3)
        assert plan.eligible == ["a", "b", "c"]
        assert all("dead" not in c.axes for c in plan.cells)


class TestTheExplosionIsRefused:
    def test_twenty_axes_is_refused_on_multiplicity(self) -> None:
        plan = plan_search(_earned(*[f"ax{i}" for i in range(20)]))
        assert plan.cells == []
        assert plan.refused_reason and "MULTIPLICITY" in plan.refused_reason

    def test_the_refusal_names_the_size_it_would_have_been(self) -> None:
        plan = plan_search(_earned(*[f"ax{i}" for i in range(20)]))
        assert "6840" in plan.refused_reason

    def test_a_grid_at_the_ceiling_is_allowed(self) -> None:
        plan = plan_search(_earned("a", "b", "c"), representations=["composite"], horizons=[1])
        assert len(plan.cells) == 1 <= MAX_CELLS

    def test_an_unknown_representation_is_rejected_loudly(self) -> None:
        with pytest.raises(ValueError, match="unknown representation"):
            plan_search(_earned("a", "b", "c"), representations=["made_up"])


class TestTheBudgetIsChargedOnEnumeration:
    """pre_filter's rule, applied to combinatorics: compute is saved, multiplicity never is."""

    def _series(self, n: int = 300) -> dict[str, np.ndarray]:
        rng = np.random.default_rng(1)
        return {a: rng.normal(size=n) for a in ("a", "b", "c")}

    def test_effective_n_trials_is_the_enumerated_grid(self) -> None:
        plan = plan_search(_earned("a", "b", "c"))
        assert plan.effective_n_trials == len(plan.cells) == len(REPRESENTATIONS) * 2

    def test_pruning_every_cell_does_not_reduce_the_bill(self) -> None:
        data = self._series()
        plan = plan_search(_earned("a", "b", "c"))
        res = run_search(plan, lambda a: data[a], lambda h: data["a"],
                         pre_filter_fn=lambda r, name: {"pass": False, "reason": "cheap reject"},
                         screen=lambda *a, **k: {"verdict": EARNING_VERDICT})
        assert res.n_pruned == len(plan.cells), "every cell was pruned"
        assert res.effective_n_trials == len(plan.cells), "and every cell was still charged"

    def test_a_missing_input_is_a_charged_trial_not_a_free_skip(self) -> None:
        plan = plan_search(_earned("a", "b", "c"))
        res = run_search(plan, lambda a: None, lambda h: None)
        assert all(r.verdict == "NO-INPUT" for r in res.results)
        assert res.effective_n_trials == len(plan.cells)

    def test_an_early_survivor_does_not_shrink_the_bill(self) -> None:
        data = self._series()
        plan = plan_search(_earned("a", "b", "c"))
        res = run_search(plan, lambda a: data[a], lambda h: data["a"],
                         screen=lambda *a, **k: {"verdict": EARNING_VERDICT, "ic": 0.5})
        assert len(res.survivors) == len(plan.cells)
        assert res.effective_n_trials == len(plan.cells)

    def test_every_enumerated_cell_appears_in_the_results(self) -> None:
        data = self._series()
        plan = plan_search(_earned("a", "b", "c"))
        res = run_search(plan, lambda a: data[a], lambda h: data["a"],
                         screen=lambda *a, **k: {"verdict": "no_edge"})
        assert {r.cell_id for r in res.results} == {c.cell_id for c in plan.cells}

    def test_the_dsr_hurdle_rises_with_the_grid(self) -> None:
        data = self._series()
        small = plan_search(_earned("a", "b", "c"), representations=["composite"], horizons=[1])
        big = plan_search(_earned("a", "b", "c"))
        rs = run_search(small, lambda a: data[a], lambda h: data["a"],
                        screen=lambda *a, **k: {"verdict": "no_edge"})
        rb = run_search(big, lambda a: data[a], lambda h: data["a"],
                        screen=lambda *a, **k: {"verdict": "no_edge"})
        if rs.dsr_hurdle_sharpe is not None and rb.dsr_hurdle_sharpe is not None:
            assert rb.dsr_hurdle_sharpe > rs.dsr_hurdle_sharpe


class TestTheGridCannotGrowAfterTheFact:
    def test_the_hash_covers_the_cells(self) -> None:
        a = plan_search(_earned("a", "b", "c"))
        b = plan_search(_earned("a", "b", "c"))
        assert a.grid_hash == b.grid_hash

    def test_adding_a_cell_changes_the_hash(self) -> None:
        plan = plan_search(_earned("a", "b", "c"))
        before = plan.grid_hash
        plan.cells.append(FusionCell(("a", "b", "c"), "composite", 99))
        assert plan.grid_hash != before, "grid extension must be detectable after the fact"

    def test_the_hash_is_order_independent(self) -> None:
        cells = plan_search(_earned("a", "b", "c")).cells
        assert (FusionPlan(cells=list(cells)).grid_hash
                == FusionPlan(cells=list(reversed(cells))).grid_hash)

    def test_the_result_carries_the_hash_it_ran(self) -> None:
        data = {a: np.zeros(50) for a in ("a", "b", "c")}
        plan = plan_search(_earned("a", "b", "c"))
        res = run_search(plan, lambda a: data[a], lambda h: data["a"],
                         screen=lambda *a, **k: {"verdict": "no_edge"})
        assert res.grid_hash == plan.grid_hash


class TestRepresentationsAreCausalAndMeaningful:
    def test_every_representation_states_a_mechanism(self) -> None:
        for name, (_fn, mech) in REPRESENTATIONS.items():
            assert len(mech) > 20, f"{name} has no stated mechanism -- it is a free parameter"

    def test_representations_are_length_preserving(self) -> None:
        rng = np.random.default_rng(2)
        cols = [rng.normal(size=200) for _ in range(3)]
        for fn, _ in REPRESENTATIONS.values():
            assert len(fn(cols)) == 200

    def test_representations_do_not_read_the_future(self) -> None:
        """A causal z-score only: truncating after t must not change the value at t."""
        rng = np.random.default_rng(3)
        cols = [rng.normal(size=200) for _ in range(3)]
        for name, (fn, _) in REPRESENTATIONS.items():
            full = fn(cols)
            for t in (80, 120, 160):
                trunc = fn([c[:t + 1] for c in cols])
                a, b = full[t], trunc[t]
                assert (np.isnan(a) and np.isnan(b)) or a == pytest.approx(b), (
                    f"{name} at t={t} changed when future data was removed")

    def test_conditioned_takes_no_view_when_the_others_disagree(self) -> None:
        n = 120
        rng = np.random.default_rng(4)
        base = rng.normal(size=n)
        fn, _ = REPRESENTATIONS["conditioned"]
        # peers with permanently opposite signs -> never agree -> always flat
        up = np.linspace(1, 100, n)
        down = np.linspace(-1, -100, n)
        out = fn([base, up, down])
        assert np.allclose(out, 0.0), "ambiguous state must produce no view, not a coin flip"

    def test_divergence_is_zero_when_everything_moves_together(self) -> None:
        n = 120
        s = np.linspace(1.0, 50.0, n)
        fn, _ = REPRESENTATIONS["divergence"]
        out = fn([s, s.copy(), s.copy()])
        assert np.nanmax(np.abs(out)) < 1e-9, "no divergence means no signal"


class TestRefusalsPropagate:
    def test_running_a_refused_plan_computes_nothing(self) -> None:
        plan = plan_search(eligibility_from_screens({"x": "no_edge"}))
        res = run_search(plan, lambda a: np.zeros(10), lambda h: np.zeros(10),
                         screen=lambda *a, **k: pytest.fail("must not screen a refused plan"))
        assert res.results == [] and res.survivors == []
        assert res.refused_reason and res.effective_n_trials == 0

    def test_the_default_width_is_the_queues_triples(self) -> None:
        assert DEFAULT_K == 3

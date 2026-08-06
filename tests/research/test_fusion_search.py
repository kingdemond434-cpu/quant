"""COMBINATORIAL SEARCH THAT CANNOT MINE NOISE -- 192 statements, zero tests until now.

This module's entire value is that it REFUSES. It refuses to combine axes that failed alone, it
refuses grids too wide to promote from, and it charges every enumerated cell to the multiplicity
budget whether or not the cell was ever computed. A combinatorial searcher whose refusals are
untested is a combinatorial searcher, and this desk has a graveyard full of what those produce.

THE FOUR PROPERTIES ASSERTED, in the order they can fail:

  1. RULE 1 -- an axis with no single-axis signal cannot buy signal by being combined.
  2. THE BUDGET IS THE ENUMERATED GRID, NOT THE COMPUTED CELLS. Pruning buys compute and never
     multiplicity. This is the leak that makes every other guarantee here worthless if it opens:
     prune 200 of 240 cells, report the DSR hurdle for 40, and the search has laundered itself.
  3. THE GRID IS HASHED AT PLAN TIME so it cannot grow after the results are seen.
  4. SURVIVORS ENTER THE GRAPH AS `correlational`, never as mechanisms.

The z-scores are also checked for causality, because a rolling window that peeks is the one bug
that would make every representation look predictive at once.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from libs.research import fusion_search as F

# --------------------------------------------------------------------- causal transforms


def test_the_rolling_z_never_sees_the_future() -> None:
    """TRUNCATION TEST, the only one that actually proves causality: recomputing on the prefix must
    reproduce the value. A centred or full-sample window passes every other check and fails this."""
    rng = np.random.default_rng(0)
    x = rng.normal(size=200)
    full = F._z(x)
    for t in (30, 75, 199):
        assert F._z(x[:t + 1])[t] == pytest.approx(full[t], nan_ok=True)


def test_the_z_warmup_is_NaN_rather_than_a_fabricated_zero() -> None:
    """A zero during warmup is a real signal value the screen would trade on. NaN is not."""
    z = F._z(np.arange(50, dtype=float), win=20)
    assert np.isnan(z[0]) and np.isnan(z[3])
    assert np.isfinite(z[-1])


def test_a_constant_window_scores_zero_and_not_infinity() -> None:
    z = F._z(np.full(40, 3.0))
    assert np.nanmax(np.abs(z)) == 0.0


def test_col_mean_returns_NaN_for_an_all_NaN_column_without_warning() -> None:
    """`np.nanmean` emits 'Mean of empty slice' here, and this repo turns warnings into errors.
    Silencing it would also silence real ones, so the count guard is explicit -- and pinned."""
    rows = np.array([[np.nan, 1.0], [np.nan, 3.0]])
    got = F._col_mean(rows)
    assert np.isnan(got[0]) and got[1] == pytest.approx(2.0)


# --------------------------------------------------------------------- representations

def _cols(n: int = 120) -> list[np.ndarray]:
    rng = np.random.default_rng(7)
    base = rng.normal(size=n)
    return [base + rng.normal(scale=0.1, size=n) for _ in range(3)]


@pytest.mark.parametrize("rep", sorted(F.REPRESENTATIONS))
def test_every_representation_is_causal_and_length_preserving(rep: str) -> None:
    build, mechanism = F.REPRESENTATIONS[rep]
    cols = _cols()
    out = build(cols)
    assert out.shape == cols[0].shape
    assert mechanism, "a representation with no stated mechanism is a free parameter"
    for t in (40, 90):
        assert build([c[:t + 1] for c in cols])[t] == pytest.approx(out[t], nan_ok=True)


def test_composite_cancels_idiosyncratic_noise_toward_the_common_component() -> None:
    """The stated mechanism, measured: averaging z-scores of series sharing one latent pressure
    must track that pressure more closely than any single member does."""
    rng = np.random.default_rng(3)
    n = 400
    latent = rng.normal(size=n)
    cols = [latent + rng.normal(scale=1.5, size=n) for _ in range(3)]
    comp = F._composite(cols)
    single = F._z(cols[0])
    ok = np.isfinite(comp) & np.isfinite(single)
    zl = F._z(latent)[ok]
    assert abs(np.corrcoef(comp[ok], zl)[0, 1]) > abs(np.corrcoef(single[ok], zl)[0, 1])


def test_divergence_is_the_gap_and_is_zero_when_the_series_are_identical() -> None:
    x = np.asarray(_cols()[0])
    out = F._divergence([x, x, x])
    assert np.nanmax(np.abs(out)) == pytest.approx(0.0, abs=1e-9)


def test_conditioned_takes_no_view_when_the_confirming_series_disagree() -> None:
    """Disagreement means the state is ambiguous. Zero is 'no view'; passing the raw z through
    would be trading the ambiguous state as if it were confirmed."""
    n = 80
    lead = np.linspace(-1, 1, n)
    agree = np.linspace(-1, 1, n)
    disagree = np.linspace(1, -1, n)
    both_up = F._conditioned([lead, agree, agree])
    split = F._conditioned([lead, agree, disagree])
    assert np.nanmax(np.abs(both_up)) > 0.0
    assert np.nanmax(np.abs(split)) == pytest.approx(0.0, abs=1e-12)


def test_conditioned_on_a_single_series_is_just_its_z() -> None:
    x = np.asarray(_cols()[0])
    assert np.allclose(F._conditioned([x]), F._z(x), equal_nan=True)


# --------------------------------------------------------------------- RULE 1: earned breadth

def test_only_the_earning_verdict_qualifies_an_axis() -> None:
    """SCREEN-WEAK, TIMING-ARTIFACT and SUSPECT-LOOKAHEAD are not near-misses to be combined --
    two of them are ARTIFACTS. Combining them is fishing with more hooks."""
    screens = {"a": F.EARNING_VERDICT, "b": "SCREEN-WEAK", "c": "TIMING-ARTIFACT",
               "d": "SUSPECT-LOOKAHEAD", "e": "SCREEN-UNDERPOWERED"}
    el = {e.axis: e for e in F.eligibility_from_screens(screens)}
    assert el["a"].earned
    assert not any(el[k].earned for k in "bcde")
    for k in "bcde":
        assert "EARNED per axis" in el[k].reason


def test_an_excluded_axis_carries_the_verdict_that_excluded_it() -> None:
    el = F.eligibility_from_screens({"a": "SCREEN-WEAK"})[0]
    assert el.single_axis_verdict == "SCREEN-WEAK", "the reason must name the actual verdict"


# --------------------------------------------------------------------- the plan

def _earned(*names: str) -> list[F.AxisEligibility]:
    return F.eligibility_from_screens(dict.fromkeys(names, F.EARNING_VERDICT))


def test_too_few_earned_axes_REFUSES_and_says_it_is_the_designed_outcome() -> None:
    plan = F.plan_search(_earned("a", "b"), k=3)
    assert plan.cells == []
    assert plan.refused_reason and "designed outcome" in plan.refused_reason
    assert plan.effective_n_trials == 0


def test_a_grid_wider_than_the_ceiling_refuses_on_MULTIPLICITY_not_compute() -> None:
    """The distinction is the whole point: it is not that the search would be slow, it is that at
    that width no measurable edge could clear the hurdle, so a result could only be luck."""
    plan = F.plan_search(_earned(*(f"ax{i}" for i in range(12))), k=3,
                         horizons=(1, 5, 20), max_cells=F.MAX_CELLS)
    assert plan.cells == []
    assert plan.refused_reason and "MULTIPLICITY" in plan.refused_reason
    assert "not compute" in plan.refused_reason


def test_the_enumerated_grid_is_the_full_product_of_the_declared_axes() -> None:
    plan = F.plan_search(_earned("a", "b", "c", "d"), k=3,
                         representations=("composite", "divergence"), horizons=(1, 5))
    assert plan.effective_n_trials == 4 * 2 * 2 == len(plan.cells)   # C(4,3)=4
    assert len({c.cell_id for c in plan.cells}) == len(plan.cells), "cell ids must be unique"


def test_an_unknown_representation_is_rejected_loudly_at_plan_time() -> None:
    with pytest.raises(ValueError, match="unknown representation"):
        F.plan_search(_earned("a", "b", "c"), representations=("magic",))


def test_the_grid_hash_changes_when_the_grid_does_and_not_otherwise() -> None:
    """RULE 3. The hash exists so a grid cannot grow after the results are in. If it were
    insensitive to an added cell, the pre-registration would be decorative."""
    small = F.plan_search(_earned("a", "b", "c"), horizons=(1,))
    same = F.plan_search(_earned("a", "b", "c"), horizons=(1,))
    bigger = F.plan_search(_earned("a", "b", "c"), horizons=(1, 5))
    assert small.grid_hash == same.grid_hash
    assert small.grid_hash != bigger.grid_hash


def test_cell_ordering_does_not_change_the_hash() -> None:
    plan = F.plan_search(_earned("a", "b", "c"), horizons=(1, 5))
    before = plan.grid_hash
    plan.cells = list(reversed(plan.cells))
    assert plan.grid_hash == before, "the hash is of the SET; order is not part of the grid"


def test_excluded_axes_are_carried_on_the_plan_rather_than_dropped() -> None:
    el = F.eligibility_from_screens({"a": F.EARNING_VERDICT, "b": F.EARNING_VERDICT,
                                     "c": F.EARNING_VERDICT, "dead": "SCREEN-WEAK"})
    plan = F.plan_search(el)
    assert [e.axis for e in plan.excluded] == ["dead"]
    assert "dead" not in plan.eligible


# --------------------------------------------------------------------- the trial ledger

def test_every_enumerated_cell_is_logged_at_PLAN_time(tmp_path: Path) -> None:
    """RULE 2, and the timing is the substance. Logging after execution omits whatever got pruned,
    which is precisely the leak that would let a wide search report a narrow bill."""
    plan = F.plan_search(_earned("a", "b", "c"), horizons=(1, 5))
    led = tmp_path / "trials.jsonl"
    assert F.log_trials(plan, led) == len(plan.cells)
    rows = [json.loads(x) for x in led.read_text("utf-8").splitlines()]
    assert len(rows) == len(plan.cells)
    assert {r["grid_hash"] for r in rows} == {plan.grid_hash}
    assert all(r["grid_size"] == plan.effective_n_trials for r in rows)


def test_the_ledger_is_append_only_across_runs(tmp_path: Path) -> None:
    """A trial that can be un-logged is a budget that can be gamed."""
    plan = F.plan_search(_earned("a", "b", "c"), horizons=(1,))
    led = tmp_path / "trials.jsonl"
    F.log_trials(plan, led)
    F.log_trials(plan, led)
    assert len(led.read_text("utf-8").splitlines()) == 2 * len(plan.cells)


def test_a_refused_plan_logs_nothing(tmp_path: Path) -> None:
    led = tmp_path / "trials.jsonl"
    assert F.log_trials(F.plan_search(_earned("a"), k=3), led) == 0
    assert not led.exists()


# --------------------------------------------------------------------- the search

def _series(n: int = 300):
    rng = np.random.default_rng(11)
    base = rng.normal(size=n)
    store = {"a": base + rng.normal(scale=0.3, size=n),
             "b": base + rng.normal(scale=0.3, size=n),
             "c": base + rng.normal(scale=0.3, size=n)}
    return store, (lambda ax: store.get(ax)), (lambda h: rng.normal(size=n))


def test_a_refused_plan_produces_a_result_that_still_carries_the_refusal() -> None:
    plan = F.plan_search(_earned("a"), k=3)
    _, sf, tf = _series()
    res = F.run_search(plan, sf, tf)
    assert res.results == [] and res.survivors == []
    assert res.refused_reason == plan.refused_reason


def test_the_hurdle_is_computed_from_the_ENUMERATED_grid_before_any_cell_is_judged() -> None:
    """THE LEAK THAT WOULD VOID EVERYTHING ELSE. If the hurdle followed the surviving cells, a
    search could prune its way to a low bar and promote noise."""
    plan = F.plan_search(_earned("a", "b", "c"), horizons=(1, 5))
    _, sf, tf = _series()
    all_pruned = F.run_search(plan, lambda ax: None, tf)          # every cell NO-INPUT
    assert all_pruned.n_pruned == len(plan.cells)
    assert all_pruned.effective_n_trials == len(plan.cells), (
        "pruning bought compute and must never buy multiplicity")
    if all_pruned.dsr_hurdle_sharpe is not None:
        screened = F.run_search(plan, sf, tf, screen=lambda *a, **k: {"verdict": "SCREEN-WEAK"})
        assert screened.dsr_hurdle_sharpe == all_pruned.dsr_hurdle_sharpe


def test_a_missing_series_is_NO_INPUT_and_is_still_accounted_for() -> None:
    plan = F.plan_search(_earned("a", "b", "c"), horizons=(1,))
    _, _, tf = _series()
    res = F.run_search(plan, lambda ax: None, tf)
    assert len(res.results) == len(plan.cells), "every enumerated cell must be accounted for"
    assert all(r.verdict == "NO-INPUT" and r.pruned for r in res.results)


def test_a_missing_target_is_NO_INPUT_too() -> None:
    plan = F.plan_search(_earned("a", "b", "c"), horizons=(1,))
    _, sf, _ = _series()
    res = F.run_search(plan, sf, lambda h: None)
    assert all(r.verdict == "NO-INPUT" for r in res.results)


def test_a_pre_filter_reject_is_STILL_A_TRIAL() -> None:
    plan = F.plan_search(_earned("a", "b", "c"), horizons=(1, 5))
    _, sf, tf = _series()
    res = F.run_search(plan, sf, tf,
                       screen=lambda *a, **k: {"verdict": F.EARNING_VERDICT},
                       pre_filter_fn=lambda pnl, name: {"pass": False, "reason": "too thin"})
    assert all(r.verdict == "PRE-FILTER-REJECT" and r.pruned for r in res.results)
    assert res.survivors == []
    assert res.effective_n_trials == len(plan.cells), "the budget is unchanged by pruning"


def test_no_screen_supplied_is_UNSCREENED_rather_than_a_silent_pass() -> None:
    plan = F.plan_search(_earned("a", "b", "c"), horizons=(1,))
    _, sf, tf = _series()
    res = F.run_search(plan, sf, tf)
    assert all(r.verdict == "UNSCREENED" and r.pruned for r in res.results)
    assert res.survivors == []


def test_only_the_earning_verdict_becomes_a_survivor() -> None:
    plan = F.plan_search(_earned("a", "b", "c"), horizons=(1, 5))
    _, sf, tf = _series()
    seen: list[str] = []

    def screen(sig, tgt, *, name, horizon_days):
        seen.append(name)
        # the first cell "wins"; everything else lands one rung below
        return {"verdict": F.EARNING_VERDICT if len(seen) == 1 else "SCREEN-WEAK",
                "ic": 0.11, "sharpe": 1.2}

    res = F.run_search(plan, sf, tf, screen=screen)
    assert len(res.survivors) == 1
    assert len(res.results) == len(plan.cells)
    assert res.results[0].ic == pytest.approx(0.11)


def test_a_non_numeric_screen_field_becomes_None_and_not_a_crash() -> None:
    plan = F.plan_search(_earned("a", "b", "c"), horizons=(1,))
    _, sf, tf = _series()
    res = F.run_search(plan, sf, tf,
                       screen=lambda *a, **k: {"verdict": "SCREEN-WEAK", "ic": "n/a",
                                               "sharpe": None})
    assert all(r.ic is None and r.sharpe is None for r in res.results)


def test_ragged_series_are_truncated_to_the_shortest_rather_than_padded() -> None:
    """Padding would align two different rulers, which is the measurement-basis failure this desk
    keeps paying for."""
    plan = F.plan_search(_earned("a", "b", "c"), horizons=(1,))
    lens = {"a": 300, "b": 120, "c": 250}
    seen: dict[str, int] = {}

    def screen(sig, tgt, *, name, horizon_days):
        seen[name] = len(sig)
        return {"verdict": "SCREEN-WEAK"}

    F.run_search(plan, lambda ax: np.zeros(lens[ax]), lambda h: np.zeros(400), screen=screen)
    assert set(seen.values()) == {120}


# --------------------------------------------------------------------- the knowledge graph

def test_survivors_land_as_correlational_with_the_grid_size_attached(tmp_path: Path) -> None:
    """RULE 4. A fusion survivor is the weakest evidence class there is -- it survived a screen
    inside a grid that was selected over. Recording it any stronger launders a search into a claim.
    """
    res = F.FusionResult(grid_hash="abc", effective_n_trials=96,
                         survivors=["a+b+c|composite|h5"], dsr_hurdle_sharpe=3.1)
    g = tmp_path / "edges.jsonl"
    assert F.record_survivors(res, g) == 1
    row = json.loads(g.read_text("utf-8").strip())
    assert row["evidence_state"] == "correlational"
    assert row["n_trials_when_found"] == 96
    assert "NOT a mechanism" in row["caveat"]


def test_no_survivors_writes_no_edges(tmp_path: Path) -> None:
    g = tmp_path / "edges.jsonl"
    assert F.record_survivors(F.FusionResult(grid_hash="x", effective_n_trials=4), g) == 0
    assert not g.exists()


# --------------------------------------------------------------------- registry gate

def test_registry_eligibility_rejects_an_axis_whose_data_is_not_on_this_box(
        tmp_path: Path) -> None:
    """The second gate the screens cannot supply: a verdict says an axis carries signal, the
    registry says the data EXISTS. Cells built from an absent asset would be NO-INPUT and would
    still cost multiplicity -- paying real trials for cells that were never testable."""
    (tmp_path / "scripts").mkdir()
    (tmp_path / "libs").mkdir()
    (tmp_path / "data").mkdir()
    (tmp_path / "scripts/w.py").write_text('open("data/ghost.jsonl","a").write("x")\n', "utf-8")
    el = {e.axis: e for e in F.eligibility_from_registry({"ghost": F.EARNING_VERDICT}, tmp_path)}
    assert not el["ghost"].earned
    assert "absent" in el["ghost"].reason or "cost multiplicity" in el["ghost"].reason


def test_registry_eligibility_still_applies_rule_1_first(tmp_path: Path) -> None:
    (tmp_path / "scripts").mkdir()
    (tmp_path / "libs").mkdir()
    el = {e.axis: e for e in F.eligibility_from_registry({"x": "SCREEN-WEAK"}, tmp_path)}
    assert not el["x"].earned and "EARNED per axis" in el["x"].reason


def test_an_axis_with_no_registry_asset_at_all_is_refused(tmp_path: Path) -> None:
    (tmp_path / "scripts").mkdir()
    (tmp_path / "libs").mkdir()
    el = {e.axis: e for e in F.eligibility_from_registry({"nowhere": F.EARNING_VERDICT}, tmp_path)}
    assert not el["nowhere"].earned
    assert "no registry asset" in el["nowhere"].reason

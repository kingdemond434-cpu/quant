"""The physics wing and the engines: every physics tradition recovers its OWN planted structure
on a synthetic market and says UNMEASURED by name on a short one; the engines run numpy-only
with every optional library reported absent rather than crashed; the adversarial synthetic
world's fake law is rejected (acceptance J) and a no-LLM end-to-end pass runs on synthetic
data (acceptance A).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pytest

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK / "research"), str(DESK), str(DESK.parents[1])):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research.mathlab import burden as B  # noqa: E402
from research.mathlab import engines as E  # noqa: E402
from research.mathlab import grammar as G  # noqa: E402
from research.mathlab import physics as P  # noqa: E402
from research.mathlab import physics_ext as PX  # noqa: E402
from research.mathlab import scientists as S  # noqa: E402
from research.mathlab.objects import KINDS, Panel, Variable  # noqa: E402

N = 2600
PHYSICS = {**P.PHYSICS_CORE_REGISTRY, **PX.PHYSICS_EXT_REGISTRY}


def make_panel(seed: int = 1, *, target: str = "EURUSD", n: int = N, phi: float = 0.0,
               peers: int = 5, common: float = 0.0) -> Panel:
    """A synthetic market: a 24-bar cycle in returns, an AR(phi) residual, five peers that may
    share a common factor, three sessions and three regimes."""
    rng = np.random.default_rng(seed)
    ret = 0.0008 * np.sin(2 * np.pi * np.arange(n) / 24) + 0.0006 * rng.normal(0, 1, n)
    close = 100.0 * np.exp(np.cumsum(ret))
    columns = {"close": close, "open": close, "high": close * 1.0004, "low": close * 0.9996,
               "ret": ret, "range": np.abs(ret) * 2 + 1e-6, "body": ret,
               "activity": 100 + 8 * np.abs(rng.normal(0, 1, n)), "spread": np.full(n, 1e-4),
               "atr": np.abs(ret) * 3 + 1e-6, "vol": 0.001 + 0.0002 * np.abs(rng.normal(0, 1, n)),
               "flow": rng.normal(0, 1, n)}
    signal = np.nan_to_num(G.evaluate(["z", ["sub", ["rmean", "close", 5],
                                             ["rmean", "close", 24]], 240], columns, n))
    shock = rng.normal(0, 1, n)
    eps = np.zeros(n)
    for i in range(1, n):
        eps[i] = phi * eps[i - 1] + 0.4 * signal[i] + shock[i]
    factor = rng.normal(0, 1, n)
    peer_cols = {f"P{i}": common * factor + rng.normal(0, 1, n) for i in range(peers)}
    return Panel(target=target, times=np.arange(n, dtype=np.int64) * 3600 + 1_600_000_000,
                 epsilon=eps, columns=columns,
                 meta={k: Variable(k, f"bars:{target}", "bars", "the bar's own close")
                       for k in columns},
                 regime=np.asarray(["low", "mid", "high"])[(np.arange(n) // 40) % 3],
                 session=np.asarray(["asia", "london", "ny"])[(np.arange(n) // 8) % 3],
                 peers=peer_cols, horizon="4", source="test_store",
                 residual_discovery_id=f"disc_{target}")


def short_panel() -> Panel:
    p = make_panel(2)
    return Panel(target="X", times=p.times[:120], epsilon=p.epsilon[:120],
                 columns={k: v[:120] for k, v in p.columns.items()}, horizon="4")


# ------------------------------------------------------------------ every tradition, twice
@pytest.mark.parametrize("tradition", sorted(PHYSICS))
def test_each_physics_tradition_proposes_objects_of_the_five_kinds(tradition: str) -> None:
    scientist = PHYSICS[tradition]()
    objects = scientist.propose(make_panel(1), 20.0, np.random.default_rng(3))
    assert objects, (tradition, scientist.unmeasured)
    assert {o.kind for o in objects} <= set(KINDS)
    assert all(o.tradition == tradition for o in objects)
    assert all(o.statement for o in objects)
    assert scientist.evaluated >= len(objects) and scientist.distinct
    for obj in objects:
        values = G.evaluate(obj.expression, make_panel(1).columns | {
            name: np.zeros(N) for name in G.variables_in(obj.expression)
            if name not in make_panel(1).columns}, N)
        assert values.shape == (N,)


@pytest.mark.parametrize("tradition", sorted(PHYSICS))
def test_each_physics_tradition_says_unmeasured_on_a_short_panel(tradition: str) -> None:
    scientist = PHYSICS[tradition]()
    assert scientist.propose(short_panel(), 5.0, np.random.default_rng(1)) == []
    assert scientist.unmeasured and "fewer than" in scientist.unmeasured[0]


def test_physics_traditions_are_registered_beside_the_mathematics_not_inside_them() -> None:
    assert len(S.TRADITIONS) == 28
    assert set(PHYSICS) <= set(S.REGISTRY)
    assert not set(PHYSICS) & set(S.TRADITIONS)
    assert len(PHYSICS) == 19 and set(S.PHYSICS_TRADITIONS) == set(PHYSICS)
    assert all(isinstance(S.build(t), PHYSICS[t]) for t in PHYSICS)


# ------------------------------------------------------------------ planted structure
def test_anomalous_diffusion_reads_brownian_and_mean_reverting_paths_apart() -> None:
    rng = np.random.default_rng(7)
    walk = np.cumsum(rng.normal(0, 1, 3000))
    ar = np.zeros(3000)
    for i in range(1, 3000):
        ar[i] = 0.5 * ar[i - 1] + rng.normal()
    alpha_walk = P.AnomalousDiffusion.exponent(walk)
    alpha_ar = P.AnomalousDiffusion.exponent(np.cumsum(np.diff(ar, prepend=0.0)))
    assert alpha_walk is not None and 0.85 < alpha_walk[0] < 1.15
    assert alpha_ar is not None and alpha_ar[0] < alpha_walk[0]


def test_nonequilibrium_entropy_production_is_zero_for_a_reversible_chain() -> None:
    """A RATCHET is irreversible; iid noise is not; and a SINUSOID is not either.

    The last one is the physics that the estimator must not get wrong: a one-dimensional
    sinusoid is periodic but time-SYMMETRIC -- run the tape backwards and the same rise-and-fall
    transition counts come back -- so an estimator that called it driven would be reading
    periodicity as an arrow of time. The ratchet (slow linear rise, instant drop) is the
    canonical driven system and the estimator must separate it by orders of magnitude.
    """
    rng = np.random.default_rng(3)
    t = np.arange(4000)
    reversible = rng.normal(0, 1, 4000)
    sinusoid = np.sin(t * 0.7) + 0.2 * rng.normal(0, 1, 4000)
    ratchet = (t % 12) / 12.0 + 0.05 * rng.normal(0, 1, 4000)
    s_rev = P.Nonequilibrium.entropy_production(reversible)
    s_sin = P.Nonequilibrium.entropy_production(sinusoid)
    s_drv = P.Nonequilibrium.entropy_production(ratchet)
    assert s_rev is not None and s_sin is not None and s_drv is not None
    assert s_drv > 50 * max(s_rev, 1e-4)
    assert s_sin < 5 * max(s_rev, 1e-4), "a 1-D sinusoid is time-reversible, not driven"
    assert P.Nonequilibrium.entropy_production(np.ones(50)) is None


def test_criticality_power_law_mle_recovers_a_planted_exponent() -> None:
    rng = np.random.default_rng(11)
    sizes = 1.0 * (1 - rng.uniform(0, 1, 4000)) ** (-1.0 / 1.5)      # alpha = 2.5 Pareto
    fit = P.Criticality.power_law(sizes)
    assert fit is not None and 2.2 < fit["alpha"] < 2.8 and fit["llr_z"] > 1.0
    exponential = rng.exponential(1.0, 4000) + 1.0
    fit_exp = P.Criticality.power_law(exponential)
    assert fit_exp is not None and fit_exp["llr_z"] < 0.0


def test_takens_finds_the_delay_and_dimension_of_a_planted_oscillator() -> None:
    t = np.arange(1200) * 0.35
    x = np.sin(t) + 0.02 * np.random.default_rng(1).normal(0, 1, t.size)
    sci = P.TakensReconstruction()
    tau, _ = sci.delay(x)
    m, fnn = sci.false_neighbours(x[:400], tau)
    assert 2 <= tau <= 8
    assert m <= 3 and fnn[-1] < 0.1
    lam, curve = sci.lyapunov(x[:400], m, tau)
    assert lam is not None and lam < 0.3 and len(curve) == 9


def test_chaos_zero_one_test_separates_noise_from_a_regular_signal() -> None:
    rng = np.random.default_rng(5)
    noise = rng.normal(0, 1, 1500)
    regular = np.sin(np.arange(1500) * 0.31)
    k_noise, _ = P.ChaosTests.zero_one(noise, np.random.default_rng(1))
    k_reg, _ = P.ChaosTests.zero_one(regular, np.random.default_rng(1))
    assert k_noise > 0.7 and k_reg < 0.3
    p, _ = P.ChaosTests.surrogate_p(noise, np.random.default_rng(2))
    assert 0.0 < p <= 1.0


def test_renormalisation_hurst_is_one_half_for_iid_returns() -> None:
    panel = make_panel(4)
    objects = P.Renormalisation().propose(panel, 10.0, np.random.default_rng(1))
    law = next(o for o in objects if o.kind == "law")
    assert 0.35 < law.diagnostics["hurst"] < 0.65
    method = next(o for o in objects if o.kind == "search_method")
    assert method.expression[0] == "rmean" and method.expression[2] in G.WINDOWS


def test_random_matrix_counts_one_signal_eigenvalue_when_a_common_factor_is_planted() -> None:
    with_factor = make_panel(8, common=1.5)
    without = make_panel(8, common=0.0)
    law_f = next(o for o in PX.RandomMatrix().propose(with_factor, 10.0,
                                                       np.random.default_rng(1))
                 if o.kind == "law")
    law_n = next(o for o in PX.RandomMatrix().propose(without, 10.0, np.random.default_rng(1))
                 if o.kind == "law")
    assert law_f.diagnostics["signal_eigenvalues"] >= 1
    assert law_f.diagnostics["signal_eigenvalues"] >= law_n.diagnostics["signal_eigenvalues"]
    assert "eigenmode_1" in with_factor.columns


def test_network_physics_percolation_threshold_rises_with_a_common_factor() -> None:
    strong = make_panel(9, common=2.0)
    weak = make_panel(9, common=0.0)
    law_s = next(o for o in PX.NetworkPhysics().propose(strong, 10.0, np.random.default_rng(1))
                 if o.kind == "law")
    law_w = next(o for o in PX.NetworkPhysics().propose(weak, 10.0, np.random.default_rng(1))
                 if o.kind == "law")
    assert law_s.diagnostics["source"] == "peers"
    assert (law_s.diagnostics["percolation_threshold"] or 0.0) >= (
        law_w.diagnostics["percolation_threshold"] or 0.0)


def test_conservation_law_finds_the_least_moving_direction_and_names_exact_identities() -> None:
    panel = make_panel(10)
    sci = PX.ConservationLaws()
    objects = sci.propose(panel, 10.0, np.random.default_rng(1))
    law = next(o for o in objects if o.kind == "law")
    assert law.diagnostics["conservation_ratio"] <= law.diagnostics["least_conserved_ratio"]
    # ret and body are the same series on this panel: the exact identity is named, not minted
    assert any("exact linear identity" in u for u in sci.unmeasured)
    assert "conserved_quantity" in panel.columns


def test_dimensional_analysis_only_forms_dimensionless_groups() -> None:
    groups = PX.DimensionalAnalysis.groups(list(G.BAR_VARIABLES))
    assert groups
    for _tree, powers in groups:
        price = sum(PX.UNITS[c][0] * p for c, p in powers.items())
        ticks = sum(PX.UNITS[c][1] * p for c, p in powers.items())
        assert price == 0 and ticks == 0


def test_symmetry_reads_an_even_response_as_broken_sign_symmetry() -> None:
    panel = make_panel(12)
    y = np.nan_to_num(G.evaluate(["z", "ret", 24], panel.columns, N))
    panel.epsilon = 0.6 * np.abs(y) + np.random.default_rng(2).normal(0, 1, N)
    objects = PX.SymmetryInvariance().propose(panel, 10.0, np.random.default_rng(1))
    law = next(o for o in objects if o.kind == "law")
    assert law.diagnostics["even_share"] > 0.4
    rel = next(o for o in objects if o.kind == "relationship")
    assert rel.expression[0] == "abs"


def test_stochastic_physics_first_passage_scales_like_brownian_motion() -> None:
    rng = np.random.default_rng(3)
    z = rng.normal(0, 1, 6000)
    t1 = PX.StochasticPhysics.first_passage(z, 1.0)
    t2 = PX.StochasticPhysics.first_passage(z, 2.0)
    assert 2.0 < t2.mean() / t1.mean() < 6.0
    pot = PX.StochasticPhysics.potential(z)
    assert (pot["wells"] and pot["barrier"] is None) or pot["barrier"] >= 0.0


def test_monte_carlo_abm_matches_moments_and_names_the_agent_mix() -> None:
    panel = make_panel(13)
    objects = PX.MonteCarloABM().propose(panel, 10.0, np.random.default_rng(1))
    mech = next(o for o in objects if o.kind == "mechanism")
    assert mech.diagnostics["best"]["gain"] in PX.MonteCarloABM.GAINS
    assert len(mech.diagnostics["grid"]) == len(PX.MonteCarloABM.GAINS) * len(
        PX.MonteCarloABM.BETAS)
    assert any(o.kind == "search_method" for o in objects)


def test_inverse_problem_recovers_a_planted_kernel_sign_and_length() -> None:
    panel = make_panel(14)
    driver = np.nan_to_num(G.evaluate(["z", "activity", 24], panel.columns, N))
    kernel = np.exp(-np.arange(1, 25) / 4.0)
    lagged = np.column_stack([np.concatenate([np.zeros(k), driver[:-k]]) for k in range(1, 25)])
    panel.epsilon = lagged @ kernel + 0.5 * np.random.default_rng(1).normal(0, 1, N)
    sci = PX.InverseProblems()
    objects = sci.propose(panel, 10.0, np.random.default_rng(1))
    rep = next(o for o in objects if o.kind == "representation")
    assert rep.diagnostics["driver"] == "activity"
    assert rep.diagnostics["kernel_sum"] > 0 and rep.diagnostics["effective_length"] < 12
    assert rep.expression[0] == "rmean" and rep.notes


def test_information_physics_finds_the_lagged_driver() -> None:
    panel = make_panel(15)
    driver = np.nan_to_num(G.evaluate(["z", "flow", 24], panel.columns, N))
    panel.epsilon = 0.8 * np.concatenate([np.zeros(3), driver[:-3]]) + \
        np.random.default_rng(1).normal(0, 1, N)
    objects = PX.InformationPhysics().propose(panel, 10.0, np.random.default_rng(1))
    rel = next(o for o in objects if o.kind == "relationship")
    assert rel.diagnostics["best"]["column"] == "flow"
    assert rel.diagnostics["best"]["lag"] == 3
    assert rel.diagnostics["net_flow"] is not None


def test_linear_response_finds_the_lag_and_sign_of_a_planted_impulse() -> None:
    panel = make_panel(16)
    driver = np.nan_to_num(G.evaluate(["z", "vol", 24], panel.columns, N))
    panel.epsilon = -0.9 * np.concatenate([np.zeros(5), driver[:-5]]) + \
        np.random.default_rng(1).normal(0, 1, N)
    objects = P.LinearResponse().propose(panel, 10.0, np.random.default_rng(1))
    rel = next(o for o in objects if o.kind == "relationship")
    assert rel.diagnostics["best"]["driver"] == "vol" and rel.diagnostics["best"]["lag"] == 5
    assert rel.side_mode == "fade"


# ------------------------------------------------------------------ engines
def test_law_discovery_recovers_a_planted_polynomial_law_and_reports_pysindy_absent() -> None:
    panel = E.synthetic_panel(np.random.default_rng(1), planted="true")
    res = E.law_discovery(panel, budget_s=5.0)
    best = res.summary["best"]
    assert best["terms"]["y"] > 0.3 and best["terms"]["y*y"] > 0.15
    assert best["r2_test"] > 0.1
    assert any("pysindy" in u for u in res.unmeasured) or any("pysindy" in f for f in
                                                              res.findings)
    assert res.trials == len(E.LAMBDAS)


def test_abc_recovers_the_mean_reversion_of_an_ou_residual() -> None:
    panel = make_panel(21, phi=0.6)
    res = E.abc_inference(panel, budget_s=5.0, rng=np.random.default_rng(1), draws=1500)
    post = res.findings[0]["theta_posterior"]
    assert 0.2 < post["mean"] < 0.7
    assert res.counts["accepted"] >= 50
    assert any("sbi" in u for u in res.unmeasured)


def test_model_competition_prefers_the_ar1_when_it_is_planted() -> None:
    res = E.model_competition(make_panel(22, phi=0.7), budget_s=5.0)
    winners = res.summary["winners"]
    assert winners["bic"] in ("ar1", "ar2", "threshold_ar")
    assert "predictions" not in res.summary or isinstance(res.summary["predictions"], dict)
    assert {r["model"] for r in res.findings} >= {"constant", "ar1", "ar2", "threshold_ar"}


def test_ode_pde_discovery_writes_equations_for_state_and_field() -> None:
    res = E.ode_pde_discovery(make_panel(23, common=1.0), budget_s=5.0)
    assert res.counts["ode"] >= 2 and res.counts["pde"] == 1
    pde = next(f for f in res.findings if f["kind"] == "pde")
    assert set(pde["coefficients"]) == {"diffusion", "advection", "reaction"}


def test_latent_to_symbolic_counterfactual_and_discrimination_run() -> None:
    panel = make_panel(24)
    latent = E.latent_to_symbolic(panel, budget_s=2.0, rng=np.random.default_rng(1),
                                  max_candidates=60)
    assert latent.findings[0]["corr_train"] > 0 and latent.trials <= 60
    law = E.law_discovery(panel, budget_s=2.0)
    cf = E.counterfactual_simulator(panel, law.summary["best"])
    assert cf.counts["interventions"] >= 2
    comp = E.model_competition(panel)
    disc = E.experimental_discrimination(panel, comp.summary["predictions"])
    assert disc.summary["next_experiment"]["rows"] >= 20
    assert E.experimental_discrimination(panel, {}).status == "UNMEASURED"


def test_formal_maths_and_differentiable_science_fall_back_and_say_so() -> None:
    formal = E.formal_maths([["add", "ret", 0], ["mul", "close", 1]])
    assert [f["canonical"] for f in formal.findings] == ["ret", "close"]
    assert formal.findings[0]["engine"] in ("sympy", "grammar.simplify")
    diff = E.differentiable_science(make_panel(25), steps=50)
    assert diff.findings[0]["engine"] in ("jax.grad", "numpy analytic gradient")
    assert np.isfinite(diff.findings[0]["mse_test"])


def test_primitive_invention_proposes_recurring_subexpressions() -> None:
    panel = make_panel(26)
    objects = []
    for cls in (P.Turbulence, P.Renormalisation, PX.MonteCarloABM):
        objects += cls().propose(panel, 5.0, np.random.default_rng(1))
    res = E.primitive_invention(objects)
    assert res.findings and res.findings[0]["support"] >= 2
    assert res.findings[0]["name"].startswith("prim_")
    assert E.primitive_invention([]).status == "UNMEASURED"


def test_method_tournament_and_distributed_science_are_two_sided_and_floored() -> None:
    stats = {"a": {"trials": 100, "passed": 20, "forward": 1, "compute_s": 60},
             "b": {"trials": 100, "passed": 2, "forward": 0, "compute_s": 60},
             "c": {"trials": 0, "passed": 0, "forward": 0, "compute_s": 0}}
    tour = E.method_tournament(stats)
    assert [r["method"] for r in tour.findings][:2] == ["a", "b"]
    assert next(r for r in tour.findings if r["method"] == "c")["status"] == "UNMEASURED"
    split = E.distributed_science(600.0, {"physics": 2.0, "mathematics": -2.0, "engines": None})
    shares = split.summary["shares"]
    assert shares["physics"] > shares["engines"] > shares["mathematics"]
    assert all(v >= split.summary["floor"] for v in shares.values())
    assert sum(shares.values()) == pytest.approx(1.0, abs=1e-6)


def test_independent_civilizations_need_disjoint_seeds_and_compare_by_the_judge() -> None:
    panel = make_panel(27)
    pops = {"A": [P.Renormalisation()], "B": [P.Renormalisation()]}
    same = E.independent_civilizations(panel, pops, seeds={"A": 1, "B": 1}, budget_s=4.0,
                                       permutations=20)
    assert same.status == "FAILED"
    res = E.independent_civilizations(panel, pops, seeds={"A": 1, "B": 2}, budget_s=4.0,
                                      permutations=20)
    assert res.counts["civilizations"] == 2 and res.trials > 0
    assert res.summary["compared_by"].startswith("the judge only")


# ------------------------------------------------------------------ acceptance J and A
def test_J_adversarial_synthetic_world_rejects_the_planted_fake_law() -> None:
    res = E.synthetic_calibration(budget_s=5.0, rng=np.random.default_rng(3), permutations=40)
    fake = next(f for f in res.findings if f["world"] == "adversarial_fake_law")
    assert abs(fake["ic_in_sample"]) > 0.3, "the fake law must LOOK real in-sample"
    assert abs(fake["ic_held_out"]) < 0.15
    assert fake["rejected"] is True and res.summary["fake_law_rejected"] is True
    assert res.summary["true_law_recovered"] is True and res.status == "OK"


def test_A_no_llm_end_to_end_pass_runs_on_synthetic_data(tmp_path: Path,
                                                        monkeypatch: pytest.MonkeyPatch) -> None:
    from libs.moat import registry as R
    from research import math_lab as ML
    from research import physics_lab as PL
    monkeypatch.setattr(R, "BACKUP", tmp_path / "no_backup", raising=False)
    R.set_path(tmp_path / "alpha_registry.sqlite")
    try:
        panels = [make_panel(31), make_panel(32, target="GBPUSD")]
        monkeypatch.setattr(ML, "build_panels", lambda max_targets=4: (
            panels, {"unmeasured": [], "targets": ["EURUSD", "GBPUSD"]}))
        monkeypatch.setattr(PL, "OUT", tmp_path / "reports" / "PHYSICS_LAB.json")
        monkeypatch.setattr(PL, "METHODS", tmp_path / "data" / "method_allocation.json")
        monkeypatch.setattr(PL, "DONATED", tmp_path / "data" / "donated.json")
        monkeypatch.setattr(PL, "MEMORY_DIR", tmp_path / "data" / "mathlab")
        from libs.ops import events
        monkeypatch.setattr(events, "PATH", tmp_path / "events.jsonl")
        from research import proposer_common as PC
        donated: list[dict[str, Any]] = []

        def fake_donate(source: str, candidates: list[dict], tests_run: int) -> Path:
            donated.extend(candidates)
            path = tmp_path / "intel" / source / "d.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(candidates, default=str), "utf-8")
            return path

        monkeypatch.setattr(PC, "donate", fake_donate)
        monkeypatch.setattr(PC, "donation_counts", lambda: {"donated": len(donated)})
        report = PL.run(budget_s=30.0, permutations=20,
                        physics=["renormalisation", "turbulence", "symmetry_invariance"],
                        maths=["spectral"])
        assert report["cards"]["total"] > 0
        assert report["cards"]["with_falsifier"] == report["cards"]["total"]
        assert report["lockbox"]["untouched"] is True
        assert report["wiring_proof"]["complete"] is True
        assert set(report["engines"]) == set(E.ENGINE_NAMES)
        assert report["allocates_capital"] is False
        assert PL.OUT.exists() and PL.METHODS.exists()
        written = json.loads(PL.OUT.read_text("utf-8"))
        assert written["civilizations"]["A"]["seed"] != written["civilizations"]["B"]["seed"]
        assert (tmp_path / "data" / "mathlab" / "lineage.jsonl").exists()
        assert (tmp_path / "events.jsonl").exists()
        ok, n = R.verify_trial_chain()
        assert ok and n >= 1
        assert all(row["kind"] == "hypothesis" and row["source"] == "physics_lab"
                   for row in donated)
    finally:
        R.set_path(None)


def test_math_lab_report_carries_the_physics_department_engines_and_wiring_proof(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from libs.moat import registry as R
    from research import math_lab as ML
    monkeypatch.setattr(R, "BACKUP", tmp_path / "no_backup", raising=False)
    R.set_path(tmp_path / "alpha_registry.sqlite")
    try:
        monkeypatch.setattr(ML, "OUT", tmp_path / "MATH_LAB.json")
        monkeypatch.setattr(ML, "ALLOCATION", tmp_path / "alloc.json")
        monkeypatch.setattr(ML, "DONATED", tmp_path / "donated.json")
        monkeypatch.setattr(ML, "MATHLAB_REPRESENTATIONS", tmp_path / "repr")
        monkeypatch.setattr(ML, "build_panels", lambda max_targets=4: (
            [make_panel(41)], {"unmeasured": [], "targets": ["EURUSD"]}))
        assert set(ML.all_traditions()) == set(S.TRADITIONS) | set(PHYSICS)
        report = ML.run(budget_s=20.0, dry_run=True, permutations=20,
                        traditions=["spectral", "criticality", "field_continuum"])
        assert report["departments"]["physics"] == ["criticality", "field_continuum"]
        assert report["departments"]["mathematics"] == ["spectral"]
        shares = report["departments"]["shares"]
        assert set(shares) == {"mathematics", "physics"} and sum(shares.values()) == \
            pytest.approx(1.0)
        assert set(report["engines"]) == set(ML.MATHLAB_ENGINES)
        assert report["wiring_proof"]["complete"] is True
        assert report["per_tradition"]["criticality"]["status"] == "OK"
        assert report["allocation"]["traditions"]["criticality"]["department"] == "physics"
        assert report["allocation"]["traditions"]["criticality"]["budget_share"] > 0
        plan = ML.department_plan(dict.fromkeys(ML.all_traditions()), None, 1000.0)
        assert plan["departments"]["shares"]["physics"] == pytest.approx(0.5)
        assert sum(v["budget_share"] for v in plan["traditions"].values()) == \
            pytest.approx(1.0 - ML.ENGINE_SHARE, abs=1e-3)
    finally:
        R.set_path(None)


def test_judge_still_refuses_a_physics_object_with_no_held_out_evidence() -> None:
    panel = E.synthetic_panel(np.random.default_rng(9), planted="fake")
    objects = P.FieldContinuum().propose(panel, 5.0, np.random.default_rng(1))
    obj = next(o for o in objects if o.kind == "relationship")
    obj.expression = ["z", "range", 24]
    verdict = B.judge(obj, panel, distinct_forms=3, rng=np.random.default_rng(1),
                      permutations=40)
    assert not obj.passed and verdict.value < 0

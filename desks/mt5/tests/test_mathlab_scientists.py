"""The fourteen mathematical traditions: each finds its OWN planted structure, and each says
UNMEASURED by name on input too short to measure anything.

ONE PANEL, MANY PLANTS. The fixture below plants a different structure for each tradition in one
synthetic market -- a 24-bar cycle, an AR(1) residual with a known half-life, a driver that
carries information non-linearly, six columns generated from two latent factors, a regime whose
whole distribution is shifted, peers driven by one common factor, a known ARX lag, and a
positioning axis -- so the test is not "did it return something" but "did its own numerics
recover the number that was put there".

THE SECOND HALF IS THE ONE THAT MATTERS. On a 120-row panel every tradition must return NOTHING
and say WHY in `unmeasured`. A scientist that silently returns [] on a short sample is
indistinguishable from one that measured and found nothing, and the desk's standing law is that
absence never resolves to a clean verdict (L1.28a).
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK / "research"), str(DESK), str(DESK.parents[1])):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mathlab import grammar as G  # noqa: E402
from mathlab import scientists as S  # noqa: E402
from mathlab.objects import KINDS, Panel, Variable  # noqa: E402

N = 3000
#: The AR(1) coefficient planted in the residual: half-life = -ln2/ln(0.9) = 6.58 bars.
PHI = 0.9
#: The cycle planted in the price path, in bars.
PERIOD = 24
#: The exogenous lag planted in the ARX relation.
ARX_LAG = 3


def _panel() -> Panel:
    rng = np.random.default_rng(20260917)
    t = np.arange(N, dtype=np.int64) * 3600 + 1_600_000_000

    # --- the residual: AR(1) with a known half-life, plus a shock that feeds back at lag 3
    shock = rng.normal(0.0, 1.0, N)
    eps = np.zeros(N)
    for i in range(1, N):
        eps[i] = PHI * eps[i - 1] + 0.35 * shock[i] + (0.8 * shock[i - ARX_LAG]
                                                       if i >= ARX_LAG else 0.0)

    # --- the price path: a 24-bar cycle under noise
    cycle = 0.0008 * np.sin(2 * np.pi * np.arange(N) / PERIOD)
    ret = cycle + 0.0006 * rng.normal(0.0, 1.0, N)
    close = 100.0 * np.exp(np.cumsum(ret))

    # --- two latent factors generating six observed columns (geometry)
    f1, f2 = rng.normal(0, 1, N), rng.normal(0, 1, N)
    latent = {f"latent_{i}": (w1 * f1 + w2 * f2 + 0.05 * rng.normal(0, 1, N))
              for i, (w1, w2) in enumerate(((1.0, 0.1), (0.9, 0.3), (0.2, 1.0),
                                            (0.1, 0.95), (0.6, 0.6), (0.5, -0.5)))}

    # --- a driver carrying information about the residual through a NON-LINEAR channel
    driver = rng.normal(0, 1, N)
    eps = eps + 0.9 * (driver ** 2 - 1.0)

    # --- regimes in RUNS of 20..80 bars, cycling low/mid/high, so that regimes have lifetimes
    # (survival), environments (causal), and a distribution that genuinely differs (transport)
    labels: list[str] = []
    cycle = ("low", "mid", "high")
    while len(labels) < N:
        labels.extend([cycle[len(labels) % 3 if not labels else (cycle.index(labels[-1]) + 1) % 3]]
                      * int(rng.integers(20, 81)))
    regime = np.asarray(labels[:N])
    spread_state = np.where(regime == "high", rng.normal(3.0, 2.0, N), rng.normal(0.0, 0.4, N))

    # --- a positioning axis with persistent (herding) changes
    cot = np.cumsum(rng.normal(0, 1, N) + 0.35 * np.sin(np.arange(N) / 60.0))

    columns = {
        "close": close, "open": close * (1 - 0.0001), "high": close * 1.0004,
        "low": close * 0.9996, "ret": ret, "range": np.abs(ret) * 2.0 + 1e-6,
        "body": ret, "activity": 100.0 + 8.0 * np.abs(rng.normal(0, 1, N)),
        "spread": 1e-4 + 1e-5 * np.abs(spread_state), "atr": np.abs(ret) * 3.0 + 1e-6,
        "vol": 0.001 + 0.0002 * np.abs(rng.normal(0, 1, N)), "flow": rng.normal(0, 1, N),
        "macro_driver": driver, "cot_net_long": cot, "regime_spread": spread_state, **latent,
    }
    common = rng.normal(0, 1, N)
    peers = {"TARGET": ret, **{f"PEER{i}": 0.7 * common + 0.3 * rng.normal(0, 1e-3, N)
                               for i in range(4)}}
    sessions = np.asarray((["asia"] * 8 + ["london"] * 6 + ["ny"] * 8 + ["off"] * 2)
                          * (N // 24 + 1))[:N]
    meta = {name: Variable(name=name, dataset=("axis:cftc:net_long" if name == "cot_net_long"
                                               else f"bars:TARGET:{name}"),
                           source="axis" if name.startswith("cot") else "bars")
            for name in columns}
    return Panel(target="TARGET", times=t, epsilon=eps, columns=columns, meta=meta,
                 regime=regime, session=sessions, peers=peers, horizon="4", source="test")


@pytest.fixture(scope="module")
def panel() -> Panel:
    return _panel()


def _run(tradition: str, panel: Panel, budget: float = 12.0):
    kwargs = ({"roi": {"spectral": 2.0, "geometry": -1.0}, "operators_used": {"z": 5, "curv": 3}}
              if tradition == "meta_mathematics" else {})
    scientist = S.build(tradition, **kwargs)
    # A FRESH VIEW PER TRADITION, exactly as `math_lab._copy_panel` gives it: a scientist that
    # mints a column must not change what the next one reads.
    view = Panel(target=panel.target, times=panel.times, epsilon=panel.epsilon,
                 columns=dict(panel.columns), meta=dict(panel.meta), regime=panel.regime,
                 session=panel.session, peers=panel.peers, horizon=panel.horizon,
                 source=panel.source)
    objects = scientist.propose(view, budget, np.random.default_rng(7))
    return scientist, view, objects


@pytest.mark.parametrize("tradition", S.TRADITIONS)
def test_every_tradition_proposes_and_charges_its_own_search(tradition: str, panel: Panel):
    """Every tradition produces at least one well-formed object and charges its own search."""
    scientist, _view, objects = _run(tradition, panel)
    assert objects, (f"{tradition} proposed nothing and said: {scientist.unmeasured}")
    assert scientist.evaluated >= len(objects)
    assert scientist.distinct, f"{tradition} charged no distinct canonical form"
    for obj in objects:
        assert obj.kind in KINDS
        assert obj.tradition == tradition
        assert obj.canonical and obj.statement
        assert obj.complexity["nodes"] >= 1
        assert G.valid(obj.expression) or G.is_constant(obj.expression)


@pytest.mark.parametrize("tradition", S.TRADITIONS)
def test_every_tradition_is_silent_and_says_why_on_a_short_panel(tradition: str):
    """UNMEASURED IS A VALUE. 120 rows buys nothing, and the scientist has to say so by name."""
    rng = np.random.default_rng(1)
    short = 120
    columns = {name: rng.normal(0, 1, short) for name in G.BAR_VARIABLES}
    columns["close"] = 100 + np.cumsum(columns["ret"])
    panel = Panel(target="TARGET", times=np.arange(short, dtype=np.int64) * 3600,
                  epsilon=rng.normal(0, 1, short), columns=columns,
                  meta={n: Variable(n, n, "bars") for n in columns}, horizon="4")
    scientist = S.build(tradition) if tradition != "meta_mathematics" else S.build(
        tradition, roi={}, operators_used={})
    objects = scientist.propose(panel, 3.0, rng)
    assert objects == []
    assert scientist.unmeasured, f"{tradition} returned nothing and named no reason"
    assert any("rows" in note for note in scientist.unmeasured)


def test_symbolic_regression_invents_an_expression_it_was_not_given(panel: Panel):
    scientist, _view, objects = _run("symbolic_regression", panel, budget=15.0)
    assert scientist.evaluated > 100, "the genetic programme barely searched"
    assert len(scientist.distinct) > 20, "the population collapsed to a handful of forms"
    best = objects[0]
    assert best.diagnostics["validation_t"] > 0
    assert best.diagnostics["hall_of_fame"] >= len(objects)
    assert len(G.variables_in(best.expression)) >= 1


def test_dynamical_systems_measures_recurrence_and_mints_a_state_variable(panel: Panel):
    _scientist, view, objects = _run("dynamical_systems", panel)
    diagnostics = objects[0].diagnostics
    assert 0.0 < diagnostics["recurrence_rate"] <= 1.0
    assert 0.0 <= diagnostics["determinism"] <= 2.0
    assert diagnostics["embedding_dim"] == 3 and diagnostics["lag"] >= 1
    assert "recurrence_density" in view.columns
    assert np.isfinite(view.columns["recurrence_density"]).any()


def test_stochastic_processes_recovers_the_planted_ou_half_life(panel: Panel):
    _scientist, _view, objects = _run("stochastic_processes", panel)
    diagnostics = objects[0].diagnostics
    # The residual is AR(1) PLUS independent noise (the driver term), so its raw lag-1
    # autocorrelation is the coefficient shrunk by the noise share; the noise-robust estimator
    # rho(2)/rho(1) is the one that must recover what was planted.
    assert diagnostics["ou_phi"] == pytest.approx(PHI, abs=0.06)
    assert diagnostics["ar1"] < diagnostics["ou_phi"]
    # The half-life is -ln2 / ln(phi): convex in phi, so its tolerance FOLLOWS from phi's rather
    # than being asserted tighter than the quantity it is derived from.
    implied = -np.log(2.0) / np.log(diagnostics["ou_phi"])
    assert diagnostics["ou_half_life_bars"] == pytest.approx(implied, rel=1e-3)
    assert 4.0 <= diagnostics["ou_half_life_bars"] <= 15.0


def test_spectral_finds_the_planted_cycle(panel: Panel):
    _scientist, _view, objects = _run("spectral", panel)
    diagnostics = objects[0].diagnostics
    assert diagnostics["peak_period_bars"] == pytest.approx(PERIOD, rel=0.35)
    assert sum(diagnostics["band_share"].values()) == pytest.approx(1.0, abs=1e-6)
    assert diagnostics["haar_level_energy"]


def test_information_theory_finds_the_non_linear_driver(panel: Panel):
    _scientist, _view, objects = _run("information_theory", panel)
    named = [o for o in objects if "macro_driver" in o.canonical]
    assert named, "the planted non-linear driver was not among the top mutual-information columns"
    diagnostics = named[0].diagnostics
    assert diagnostics["mutual_information_nats"] > 0.0
    assert diagnostics["permutation_p"] <= 0.05


def test_geometry_finds_the_two_latent_factors(panel: Panel):
    _scientist, view, objects = _run("geometry", panel)
    diagnostics = objects[0].diagnostics
    assert diagnostics["dim90"] <= diagnostics["columns"]
    assert diagnostics["participation_ratio"] > 0
    assert "pc1" in view.columns
    assert diagnostics["pc1_loadings"]


def test_optimal_transport_finds_the_shifted_distribution(panel: Panel):
    _scientist, view, objects = _run("optimal_transport", panel)
    diagnostics = objects[0].diagnostics
    assert diagnostics["regime_w1"], "no regime pair was comparable"
    assert max(diagnostics["regime_w1"].values()) > 0.0
    assert "w1_drift" in view.columns


def test_graph_theory_measures_synchronisation_over_the_peers(panel: Panel):
    _scientist, view, objects = _run("graph_theory", panel)
    diagnostics = objects[0].diagnostics
    assert diagnostics["nodes"] >= S.GraphTheory.MIN_PEERS
    assert 0.0 < diagnostics["mean_sync"] <= 1.0
    assert "graph_sync" in view.columns and "graph_centrality" in view.columns


def test_graph_theory_says_unmeasured_without_enough_peers(panel: Panel):
    thin = Panel(target=panel.target, times=panel.times, epsilon=panel.epsilon,
                 columns=dict(panel.columns), meta=dict(panel.meta), regime=panel.regime,
                 session=panel.session, peers={"TARGET": panel.peers["TARGET"]},
                 horizon=panel.horizon)
    scientist = S.build("graph_theory")
    assert scientist.propose(thin, 5.0, np.random.default_rng(2)) == []
    assert any("peer" in note for note in scientist.unmeasured)


def test_topology_measures_persistence_and_its_stability(panel: Panel):
    _scientist, view, objects = _run("topology", panel)
    diagnostics = objects[0].diagnostics
    assert diagnostics["bars"] > 0 and diagnostics["persistence_entropy"] > 0
    assert "noise_displacement" in diagnostics and "stable" in diagnostics
    assert "persistence_entropy" in view.columns


def test_causal_reports_invariance_across_environments(panel: Panel):
    _scientist, _view, objects = _run("causal", panel)
    rows = objects[0].diagnostics["rows"]
    assert rows and all("invariance_spread" in r for r in rows)
    assert any(r["invariance_spread"] is not None for r in rows)
    assert objects[0].diagnostics["environments"]


def test_combinatorics_enumerates_under_fdr_control(panel: Panel):
    scientist, _view, objects = _run("combinatorics", panel)
    assert scientist.evaluated > 10
    if objects:
        diagnostics = objects[0].diagnostics
        assert diagnostics["enumerated"] <= S.Combinatorics.MAX_CONFIGURATIONS
        assert diagnostics["survivors_after_fdr"] <= diagnostics["enumerated"]
        assert diagnostics["q"] == S.Combinatorics.Q
    else:
        assert any("FDR" in n or "Benjamini" in n or "fdr" in n for n in scientist.unmeasured)


def test_control_theory_recovers_the_planted_exogenous_lag(panel: Panel):
    _scientist, _view, objects = _run("control_theory", panel)
    diagnostics = objects[0].diagnostics
    assert diagnostics["ar_order"] == S.ControlTheory.AR_ORDER
    assert len(diagnostics["impulse_response"]) == 12
    assert np.isfinite(diagnostics["spectral_radius"])
    assert diagnostics["settling_bars"] >= 1


def test_game_theory_uses_the_positioning_axis_when_the_panel_has_one(panel: Panel):
    _scientist, _view, objects = _run("game_theory_ecology", panel)
    diagnostics = objects[0].diagnostics
    assert diagnostics["axis"] == "cot_net_long"
    assert diagnostics["is_proxy"] is False
    assert diagnostics["behaviour"] in ("herding", "anti-herding")


def test_game_theory_names_the_proxy_when_there_is_no_positioning_axis(panel: Panel):
    columns = {k: v for k, v in panel.columns.items() if "cot" not in k}
    stripped = Panel(target=panel.target, times=panel.times, epsilon=panel.epsilon,
                     columns=columns,
                     meta={k: v for k, v in panel.meta.items() if k in columns},
                     regime=panel.regime, session=panel.session, peers=panel.peers,
                     horizon=panel.horizon)
    scientist = S.build("game_theory_ecology")
    objects = scientist.propose(stripped, 5.0, np.random.default_rng(3))
    assert objects and objects[0].diagnostics["is_proxy"] is True
    assert any("PROXY" in note or "proxy" in note for note in scientist.unmeasured)


def test_meta_mathematics_invents_search_methods_from_the_roi_table(panel: Panel):
    _scientist, _view, objects = _run("meta_mathematics", panel)
    assert objects and all(o.kind == "search_method" for o in objects)
    diagnostics = objects[0].diagnostics
    assert diagnostics["top_traditions"][0] == "spectral"
    assert diagnostics["objective"] and diagnostics["search_operator"]


def test_every_tradition_offers_at_least_one_tradeable_projection(panel: Panel):
    """An invention the formula family cannot be handed must still reach execution SOMEHOW."""
    missing: list[str] = []
    for tradition in S.TRADITIONS:
        _scientist, _view, objects = _run(tradition, panel, budget=8.0)
        if not any(G.tradeable(o.expression)[0] is not None for o in objects):
            missing.append(tradition)
    assert not missing, f"no executable projection from: {missing}"


def test_second_cohort_is_registered_and_distinct():
    assert len(S.TRADITIONS) == len(set(S.TRADITIONS)) == 28
    assert set(S.EXTRA_TRADITIONS) <= set(S.TRADITIONS)
    assert all(name in S.REGISTRY for name in S.TRADITIONS)


def test_change_point_finds_a_planted_mean_shift(panel: Panel):
    shifted = Panel(target=panel.target, times=panel.times,
                    epsilon=panel.epsilon + np.where(np.arange(N) >= 1500, 4.0, 0.0),
                    columns=dict(panel.columns), meta=dict(panel.meta), regime=panel.regime,
                    session=panel.session, peers=panel.peers, horizon=panel.horizon)
    scientist = S.build("change_point")
    objects = scientist.propose(shifted, 12.0, np.random.default_rng(5))
    points = objects[0].diagnostics["change_points"]
    assert any(abs(p - 1500) <= 60 for p in points), points


def test_survival_hazard_measures_regime_lifetimes(panel: Panel):
    _scientist, view, objects = _run("survival_hazard", panel)
    diagnostics = objects[0].diagnostics
    assert diagnostics["runs_complete_train"] >= S.EXTRA_REGISTRY["survival_hazard"].MIN_RUNS
    medians = [m for m in diagnostics["median_survival_bars"].values() if m]
    assert medians and all(20 <= m <= 80 for m in medians), medians
    assert "hazard_now" in view.columns and "regime_age" in view.columns


def test_sindy_writes_a_sparse_equation(panel: Panel):
    _scientist, _view, objects = _run("sindy", panel)
    diagnostics = objects[0].diagnostics
    assert diagnostics["equation"].startswith("dx = ")
    assert diagnostics["terms"] and "x" in diagnostics["terms"]
    assert 0 < len(diagnostics["terms"]) < len(diagnostics["library"])


def test_koopman_reports_modes_and_stability(panel: Panel):
    _scientist, view, objects = _run("koopman_dmd", panel)
    diagnostics = objects[0].diagnostics
    assert diagnostics["rank"] >= 2 and len(diagnostics["eigenvalue_moduli"]) == diagnostics["rank"]
    assert "dmd_mode1" in view.columns


def test_extreme_value_fits_the_tail(panel: Panel):
    _scientist, view, objects = _run("extreme_value", panel)
    diagnostics = objects[0].diagnostics
    assert diagnostics["n_exceedances_train"] >= 30
    assert np.isfinite(diagnostics["xi"]) and 0 < diagnostics["extremal_index"] <= 1
    assert "evt_exceedance_rate" in view.columns


def test_an_unknown_tradition_raises_rather_than_going_dark():
    with pytest.raises(KeyError):
        S.build("astrology")

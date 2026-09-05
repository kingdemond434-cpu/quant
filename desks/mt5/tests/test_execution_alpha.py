"""Alpha capture, the sample-size gate, the conditional execution choice and the meta-labeler.

Pinned here, in the order the discipline runs:

  * the POWER GATE is arithmetic, not opinion: n scales with (sigma/delta)^2 and grows with the
    number of cells the search will look at, so a wide table costs more evidence than a narrow
    one and the price is charged before the model is fitted, never after;
  * ALPHA CAPTURE is realised edge over predicted FRICTIONLESS edge; it refuses to divide by a
    near-zero denominator, refuses below MIN_N, decomposes the leakage into spread, slippage,
    commission and a NAMED residual, and measures adverse selection separately because the
    post-fill markout is not a component of a trade's realised R;
  * the CONDITIONAL EXECUTION CHOICE returns the caller's fallback whenever its gate is shut, and
    names a winner only when the cell has its required sample AND the advantage interval clears
    zero;
  * the META-LABELER can NEVER re-admit a signal a gate refused -- gate_passed=False is SKIP at
    0.0x on a fitted model, an unfitted one, any feature, any bucket -- it is a no-op on the
    upside while UNMEASURED, it refuses a non-monotone feature outright rather than keeping its
    significant cells, and its multiplier is capped.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.execution import alpha_capture as ac  # noqa: E402
from libs.execution import execution_choice_model as ecm  # noqa: E402
from libs.execution import meta_label as ml  # noqa: E402
from libs.execution import sample_power as sp  # noqa: E402
from libs.execution.fill_corpus import FillRecord  # noqa: E402


# --------------------------------------------------------------------------- the gate
def test_the_normal_quantile_is_right_where_every_gate_reads_it() -> None:
    assert sp.norm_ppf(0.975) == pytest.approx(1.959964, abs=1e-6)
    assert sp.norm_ppf(0.80) == pytest.approx(0.8416212, abs=1e-6)
    assert sp.norm_ppf(0.5) == pytest.approx(0.0, abs=1e-9)
    assert sp.norm_ppf(1e-6) == pytest.approx(-4.753424, abs=1e-5)
    with pytest.raises(ValueError):
        sp.norm_ppf(0.0)


def test_the_sample_scales_with_the_square_of_noise_over_signal() -> None:
    base = sp.required_n(0.10, 0.04)
    assert sp.required_n(0.20, 0.04) == pytest.approx(4 * base, rel=0.01)
    assert sp.required_n(0.10, 0.08) == pytest.approx(base / 4, rel=0.02)
    # the textbook constant: 2 (1.96 + 0.8416)^2 ~= 15.7
    assert base == math.ceil(15.7 * (0.10 / 0.04) ** 2) or base == math.ceil(
        2 * (1.959964 + 0.8416212) ** 2 * (0.10 / 0.04) ** 2)


def test_looking_at_more_cells_costs_more_evidence() -> None:
    """Bonferroni, charged at PLANNING time. A 180-cell table scanned at 5% finds nine winners
    from pure noise, and this desk has paid for exactly that error before."""
    one = sp.required_n(0.25, 0.04, n_comparisons=1)
    many = sp.required_n(0.25, 0.04, n_comparisons=540)
    assert many > 2.5 * one


def test_a_verdict_says_whether_its_sigma_was_measured_or_declared() -> None:
    v = sp.verdict(n_have=5, delta_target=0.04, sigma=None, reference_sigma=0.25)
    assert v.status == sp.UNMEASURED and v.sigma_measured is False and v.shortfall > 0
    w = sp.verdict(n_have=10**9, delta_target=0.04, sigma=0.01, reference_sigma=0.25)
    assert w.status == sp.MEASURED and w.sigma_measured is True and w.shortfall == 0
    assert w.delta_detectable is not None and w.delta_detectable < 0.04


def test_sigma_of_refuses_a_single_observation() -> None:
    assert sp.sigma_of([1.0]) is None
    assert sp.sigma_of([1.0, 1.0, 1.0]) is None          # zero dispersion is not a sigma
    assert sp.sigma_of([1.0, 2.0, 3.0]) == pytest.approx(1.0)


# --------------------------------------------------------------------------- alpha capture
def _fill(i: int, *, realized: float, predicted: float = 0.25, sleeve: str = "gold",
          session: str = "asia", symbol: str = "XAUUSD", **over) -> FillRecord:
    kw = {"intent_id": f"i{i}", "symbol": symbol, "sleeve": sleeve, "session": session,
          "status": "FILLED", "account_kind": "live", "realized_r": realized,
          "posterior_edge_r": predicted, "stop_frac": 0.01, "slip_r": 0.03,
          "spread_frac_at_decision": 0.0001, "commission_r": 0.01, "algo": "market",
          "direction": 1}
    kw.update(over)
    return FillRecord(**kw)                                  # type: ignore[arg-type]


def test_capture_is_unmeasured_below_min_n_and_never_a_zero() -> None:
    cap = ac.capture([_fill(i, realized=0.2) for i in range(5)])
    assert cap.status == ac.UNMEASURED and cap.ratio is None
    assert "needs" in cap.why or "capture ratio needs" in cap.why


def test_capture_is_realised_over_frictionless_and_the_leakage_decomposes() -> None:
    recs = [_fill(i, realized=0.17, predicted=0.25) for i in range(40)]
    cap = ac.capture(recs)
    assert cap.status == ac.MEASURED
    assert cap.ratio == pytest.approx(0.17 / 0.25, abs=1e-6)
    assert cap.leakage_r == pytest.approx(0.08, abs=1e-6)
    # spread 0.0001/0.01 = 0.01R, slippage 0.03R, commission 0.01R -> residual 0.03R
    assert cap.leakage["spread"] == pytest.approx(0.01, abs=1e-6)
    assert cap.leakage["slippage"] == pytest.approx(0.03, abs=1e-6)
    assert cap.leakage["residual"] == pytest.approx(0.03, abs=1e-6)
    assert sum(v for v in cap.leakage.values() if v is not None) == pytest.approx(0.08, abs=1e-6)
    assert cap.denominator_basis == {"posterior_edge_r": 40}


def test_a_near_zero_predicted_edge_is_refused_rather_than_divided_by() -> None:
    cap = ac.capture([_fill(i, realized=0.05, predicted=0.001) for i in range(40)])
    assert cap.status == ac.UNMEASURED and cap.ratio is None
    assert "division by noise" in cap.why


def test_the_denominator_is_grossed_back_up_when_it_came_net_of_a_modelled_cost() -> None:
    r = FillRecord(intent_id="i", stop_frac=0.01, signal_bps=8.0, modelled_cost_bps=2.0)
    v, basis = ac.frictionless_edge_r(r)
    assert v == pytest.approx((8.0 + 2.0) * 1e-4 / 0.01)
    assert basis == "signal_bps+modelled_cost/stop"


def test_a_ratio_interval_uses_the_pairing_it_actually_has() -> None:
    """Realised and predicted come from the SAME trades. Treating them as independent reports an
    interval narrower than the evidence, so the covariance term is in the variance."""
    recs = [_fill(i, realized=0.1 + 0.01 * (i % 7), predicted=0.2 + 0.01 * (i % 7))
            for i in range(60)]
    cap = ac.capture(recs)
    assert cap.status == ac.MEASURED and cap.ratio_ci95 is not None
    lo, hi = cap.ratio_ci95
    assert lo < cap.ratio < hi


def test_measured_is_not_the_same_as_usable_and_the_report_says_which() -> None:
    """A capture ratio of 1.36 with an interval of [0.69, 2.03] is MEASURED and worthless: that
    interval contains 'execution costs a third of the edge' and 'execution doubles it'. The
    precision block is what stops the first number being read without the second."""
    import random
    random.seed(11)
    noisy = [_fill(i, realized=random.gauss(0.17, 1.0), predicted=0.25) for i in range(120)]
    cap = ac.capture(noisy)
    assert cap.status == ac.MEASURED                     # the ratio exists ...
    assert cap.precision["status"] == ac.UNMEASURED      # ... and is far too wide to steer by
    assert cap.precision["half_width"] > ac.TARGET_HALF_WIDTH
    assert cap.precision["n_for_target"] > 1000 and cap.precision["shortfall"] > 0
    # a tight numerator settles the same question on a fraction of the sample
    tight = [_fill(i, realized=0.17 + 0.001 * (i % 3), predicted=0.25) for i in range(40)]
    assert ac.capture(tight).precision["status"] == ac.MEASURED


def test_the_report_splits_by_sleeve_session_and_symbol_and_keeps_the_thin_cells() -> None:
    recs = ([_fill(i, realized=0.17, sleeve="gold", session="asia") for i in range(40)]
            + [_fill(100 + i, realized=0.05, sleeve="fx", session="london") for i in range(3)])
    rep = ac.report(recs)
    assert rep["by_sleeve"]["gold"]["status"] == ac.MEASURED
    # the thin sleeve is REPORTED, not dropped: a sleeve that cannot be measured is a fact
    assert rep["by_sleeve"]["fx"]["status"] == ac.UNMEASURED and rep["by_sleeve"]["fx"]["n"] == 3
    assert set(rep["by_session"]) == {"asia", "london"}
    assert rep["n_live"] == 43 and rep["population"].startswith("live fills")


def test_demo_fills_do_not_get_averaged_into_a_live_capture_ratio() -> None:
    recs = [_fill(i, realized=0.17, account_kind="demo") for i in range(40)]
    rep = ac.report(recs)
    assert rep["n_live"] == 0 and "NO LIVE FILLS" in rep["population"]


def test_adverse_selection_is_signed_so_positive_is_a_cost() -> None:
    recs = [_fill(i, realized=0.1, markout_1s_r=-0.02, markout_5m_r=-0.05) for i in range(40)]
    a = ac.adverse_selection(recs)
    assert a["horizons"]["markout_1s_r"]["adverse_selection_r"] == pytest.approx(0.02)
    assert a["transient_r"] == pytest.approx(-0.03)          # it kept going: information, not us
    assert "selected against" in a["interpretation"]
    back = ac.adverse_selection([_fill(i, realized=0.1, markout_1s_r=-0.05, markout_5m_r=-0.01)
                                 for i in range(40)])
    assert back["transient_r"] == pytest.approx(0.04)        # it came back: our own footprint
    assert "footprint" in back["interpretation"]


def test_the_trend_needs_points_before_it_reports_a_direction() -> None:
    assert ac.trend([{"ratio": 0.6}, {"ratio": 0.7}])["status"] == ac.UNMEASURED
    up = ac.trend([{"ratio": 0.6}, {"ratio": 0.7}, {"ratio": 0.8}])
    assert up["status"] == ac.MEASURED and up["direction"] == "improving"
    down = ac.trend([{"ratio": 0.8}, {"ratio": 0.7}, {"ratio": 0.6}])
    assert down["direction"] == "deteriorating"


# --------------------------------------------------------------------------- style choice
def _styled(i: int, style: str, slip: float) -> FillRecord:
    return FillRecord(intent_id=f"s{i}", symbol="XAUUSD", sleeve="gold", session="asia",
                      status="FILLED", algo=style, slip_r=slip, stop_frac=0.01,
                      spread_frac_at_decision=0.00005, vol_frac=0.001, momentum_z=0.0,
                      direction=1)


def test_a_thin_sample_yields_no_policy_and_choose_returns_the_fallback() -> None:
    recs = [_styled(i, "market", 0.03) for i in range(4)]
    recs += [_styled(100 + i, "pullback", 0.01) for i in range(4)]
    surf = ecm.fit(recs)
    assert surf.status == ecm.UNMEASURED and not surf.usable
    assert "NOT fitted" in surf.why
    style, why = surf.choose(ecm.condition_of(recs[0]), fallback="market")
    assert style == "market" and why.startswith(ecm.UNMEASURED)


def test_a_cell_with_no_observed_variance_is_still_refused_below_the_floor() -> None:
    """The trap the floor exists for. Four identical slippages per arm give a sigma of zero, an
    infinitely tight interval and a confident winner. The power number alone would clear it."""
    thin = ecm.MIN_CELL_N - 1
    recs = [_styled(i, "market", 0.03) for i in range(thin)]
    recs += [_styled(100 + i, "pullback", 0.01) for i in range(thin)]
    surf = ecm.fit(recs)
    assert surf.status == ecm.UNMEASURED
    cell = surf.verdicts[ecm.condition_of(recs[0])]
    assert cell["n_needed_per_arm"] >= ecm.MIN_CELL_N and cell["shortfall_per_arm"] >= 1
    assert str(ecm.MIN_CELL_N) in cell["why"]


def test_a_real_and_well_sampled_advantage_is_named_and_routed_to() -> None:
    recs = [_styled(i, "market", 0.0300 + 0.0001 * (i % 5)) for i in range(60)]
    recs += [_styled(100 + i, "pullback", 0.0100 + 0.0001 * (i % 5)) for i in range(60)]
    surf = ecm.fit(recs)
    assert surf.basis == "slip_r" and surf.usable
    cell = ecm.condition_of(recs[0])
    v = surf.verdicts[cell]
    assert v["best"] == "pullback" and v["advantage_r"] == pytest.approx(0.02, abs=2e-4)
    assert v["advantage_ci95"][0] > 0
    style, why = surf.choose(cell, fallback="market")
    assert style == "pullback" and why.startswith(ecm.MEASURED)
    # ... but never to a style this order cannot use
    style, why = surf.choose(cell, available=("market", "twap"), fallback="market")
    assert style == "market" and "not available" in why


def test_a_cost_basis_is_flipped_so_bigger_is_always_better() -> None:
    r = FillRecord(intent_id="i", slip_r=0.02, markout_5m_r=-0.01)
    assert ecm.post_fill_alpha(r, "slip_r") == pytest.approx(-0.02)
    assert ecm.post_fill_alpha(r, "markout_5m_r") == pytest.approx(-0.01)


def test_the_requirements_table_prices_every_tier_and_orders_the_bases_by_cost() -> None:
    req = ecm.requirements()
    tiers = req["tiers"]
    assert set(tiers) == {"unconditional", "session", "session_x_spread", "full"}
    unc = tiers["unconditional"]["by_basis"]
    assert unc["slip_r"]["n_per_arm"] < unc["markout_5m_r"]["n_per_arm"]
    assert unc["markout_5m_r"]["n_per_arm"] < unc["realized_r"]["n_per_arm"]
    # conditioning costs sample: the full cross is strictly dearer than the unconditional one
    assert (tiers["full"]["by_basis"]["slip_r"]["n_total_fills"]
            > tiers["unconditional"]["by_basis"]["slip_r"]["n_total_fills"])


def test_only_filled_rows_teach_the_style_model() -> None:
    recs = [_styled(i, "market", 0.03) for i in range(30)]
    for r in recs[:10]:
        object.__setattr__(r, "status", "REJECTED")
    surf = ecm.fit(recs)
    assert surf.n_observations == 20


# --------------------------------------------------------------------------- meta-labeler
def _labelled(i: int, feature: float, realized: float) -> FillRecord:
    return FillRecord(intent_id=f"m{i}", symbol="XAUUSD", sleeve="gold", status="FILLED",
                      posterior_edge_r=feature, realized_r=realized, stop_frac=0.01)


def _monotone_corpus(n: int = 200, span: float = 0.25) -> list[FillRecord]:
    """A feature that genuinely orders the outcome, with enough rows to clear the gate."""
    return [_labelled(i, float(i), span * i / (n - 1)) for i in range(n)]


def test_an_unfitted_labeler_is_a_no_op_on_the_upside() -> None:
    m = ml.fit([], features=("posterior_edge_r",))
    assert m.status == ml.UNMEASURED and not m.usable
    label, mult, why = m.label(_labelled(0, 1.0, 0.5), gate_passed=True)
    assert label == ml.BASE and mult == 1.0 and ml.UNMEASURED in why
    assert m.power["n_required_per_bucket"] > 0


def test_a_refused_signal_is_skip_at_zero_on_a_FITTED_model_too() -> None:
    """THE LAW. The meta-labeler is a sizing refinement strictly downstream of admission. There is
    no argument, flag or fitted state that lets it talk a gated-out signal back into the book."""
    m = ml.fit(_monotone_corpus(), features=("posterior_edge_r",))
    assert m.usable                                   # fitted, and still refuses
    top = _labelled(0, 199.0, 0.25)
    assert m.label(top, gate_passed=True)[1] > 1.0
    label, mult, why = m.label(top, gate_passed=False)
    assert label == ml.SKIP and mult == 0.0 and "never re-admits" in why


def test_a_bucket_below_the_floor_is_refused_however_clean_its_numbers_look() -> None:
    n = ml.MIN_BUCKET_N * ml.N_BUCKETS - 5          # just under the floor, perfectly separable
    m = ml.fit(_monotone_corpus(n), features=("posterior_edge_r",))
    assert m.status == ml.UNMEASURED
    assert m.label(_labelled(0, float(n - 1), 0.25), gate_passed=True)[1] == 1.0


def test_a_fitted_labeler_upsizes_only_where_the_evidence_clears_the_base_bucket() -> None:
    m = ml.fit(_monotone_corpus(), features=("posterior_edge_r",))
    assert m.status == ml.MEASURED and m.feature == "posterior_edge_r"
    assert len(m.buckets) == ml.N_BUCKETS
    mults = [b["multiplier"] for b in m.buckets]
    assert mults[0] == 0.0 and mults[1] == 0.5 and mults[2] == 1.0
    assert mults[-1] == pytest.approx(ml.MULTIPLIERS[ml.MAX])
    assert all(mu <= ml.MAX_MULTIPLIER for mu in mults)
    # and the bucket a fresh occurrence lands in is the one its feature says
    assert m.label(_labelled(0, 5.0, 0.0), gate_passed=True)[0] == ml.SKIP
    assert m.label(_labelled(0, 195.0, 0.0), gate_passed=True)[0] == ml.MAX


def test_a_non_monotone_feature_is_refused_whole_not_pruned_to_its_winners() -> None:
    n = 200
    recs = [_labelled(i, float(i), 0.25 * abs(i - n / 2) / (n / 2)) for i in range(n)]
    m = ml.fit(recs, features=("posterior_edge_r",))
    assert m.status == ml.UNMEASURED and not m.usable
    assert "not monotone" in m.why
    assert m.label(recs[-1], gate_passed=True)[1] == 1.0


def test_scanning_two_features_picks_the_one_with_evidence_and_pays_for_looking() -> None:
    """The winner is chosen on the LOWER BOUND of its claim, not on how far apart its bucket
    means happen to sit -- extreme means are what noise produces, and picking on them after
    scanning several columns is the multiplicity error twice over."""
    import random
    random.seed(3)
    n = 400
    noise = list(range(n))
    random.shuffle(noise)
    recs = [FillRecord(intent_id=f"m{i}", status="FILLED", stop_frac=0.01,
                       posterior_edge_r=float(i), vol_frac=float(noise[i]),
                       realized_r=0.25 * i / (n - 1))
            for i in range(n)]
    m = ml.fit(recs, features=("posterior_edge_r", "vol_frac"))
    assert m.status == ml.MEASURED and m.feature == "posterior_edge_r"
    assert m.features_tried == ["posterior_edge_r", "vol_frac"]
    # looking at two columns is charged as eight comparisons, not one
    assert m.power["comparisons_charged"] == 2 * (ml.N_BUCKETS - 1)


def test_a_feature_the_corpus_does_not_carry_never_sizes_on_an_imputed_value() -> None:
    m = ml.fit(_monotone_corpus(), features=("posterior_edge_r",))
    blank = FillRecord(intent_id="x", status="FILLED")
    label, mult, why = m.label(blank, gate_passed=True)
    assert label == ml.BASE and mult == 1.0 and "not populated" in why


def test_scanning_more_features_raises_the_bar_rather_than_lowering_it() -> None:
    one = ml.requirements(n_features=1)["n_per_bucket"]
    many = ml.requirements(n_features=20)["n_per_bucket"]
    assert many > one
    assert ml.requirements(n_features=1)["n_total_labelled_outcomes"] == one * ml.N_BUCKETS


def test_the_labels_and_their_multipliers_are_the_five_the_principal_named() -> None:
    assert ml.LABELS == ("SKIP", "HALF", "BASE", "UP", "MAX")
    assert [ml.MULTIPLIERS[k] for k in ml.LABELS] == [0.0, 0.5, 1.0, 1.5, 2.0]
    assert ml.label_of_multiplier(1.45) == ml.UP

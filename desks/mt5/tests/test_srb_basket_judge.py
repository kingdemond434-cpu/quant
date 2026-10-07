"""The basket judge's honesty properties, pinned.

These tests do not check that the basket WINS -- it does not. They check the three things that
would make a favourable basket worthless if they broke: that membership rules which select on
in-sample performance are labelled and charged rather than promoted, that the portfolio series is
the per-leg-costed sum rather than a netted fiction, and that the effective-independent-bets
figure is measured off the same window the judge reads.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

BASE = Path(__file__).resolve().parents[3]
for _p in (str(BASE), str(BASE / "desks" / "mt5")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

sbj = pytest.importorskip("research.srb_basket_judge")


def _leg(name: str, block: int | None, days: int, sharpe: float,
         values: np.ndarray, index: pd.DatetimeIndex) -> dict[str, object]:
    s1 = pd.Series(values, index=index)
    return {
        "row": {"arm": "arm1_session_onset", "symbol": name, "block": block,
                "days": days, "sharpe_is": sharpe,
                "params": {"range_start": 1, "range_end": 5, "signal_at": 5}},
        "ds1": s1, "ds3": s1 - 0.01,
        "cost": {"cost_basis": "pooled_median_spread"},
    }


@pytest.fixture
def panel() -> object:
    rng = np.random.default_rng(7)
    idx = pd.date_range("2020-01-01", periods=400, freq="D")
    legs = {}
    for i in range(6):
        legs[f"k{i}"] = _leg(f"SYM{i}", None if i == 5 else i % 3, 400 - i,
                             0.1 if i % 2 == 0 else -0.1,
                             rng.normal(0.01 if i % 2 == 0 else -0.01, 1.0, 400), idx)
    return sbj.Panel(legs)


def test_unblocked_legs_are_excluded_from_block_rules(panel) -> None:
    """A leg the sweep could not cluster must NOT become a block of its own.

    Admitting it would count an UNMEASURED independence as a measured one, in the direction that
    flatters the basket -- the exact error class this organ exists to refuse.
    """
    chosen = sbj._one_per_block(panel, list(range(len(panel.names))), lambda j: -j)
    syms = {panel.legs[panel.names[j]]["row"]["symbol"] for j in chosen}
    assert "SYM5" not in syms, "a block=None leg was admitted as a singleton block"
    assert len(chosen) == 3, "one member per distinct block, and only per DISTINCT block"


def test_every_rule_declares_its_selection_class(panel) -> None:
    rules = sbj.membership_rules(panel, {})
    allowed = {"none", "non_performance", "sign_in_sample", "ranked_in_sample",
               "sign_out_of_sample", "ranked_out_of_sample"}
    assert rules, "no membership rule was produced"
    for r in rules:
        assert r["selection"] in allowed, f"{r['name']} has no declared selection class"
        assert r["rule"], f"{r['name']} states no rule text"
    names = {r["name"] for r in rules}
    assert {"all_judged", "block_longest_history", "block_most_liquid"} <= names, (
        "the three genuinely-one-trial rules must always be run, including when they lose")
    assert any(r["selection"] == "ranked_in_sample" for r in rules), (
        "the argmax control must be run and published, not quietly dropped")


def test_in_sample_rules_are_never_promotable(panel) -> None:
    """A basket chosen on the data the judge then reads cannot be promoted, whatever it scores."""
    rules = sbj.membership_rules(panel, {})
    honest = {"none", "non_performance", "sign_out_of_sample", "ranked_out_of_sample"}
    for r in rules:
        if r["window"] == "full" and r["selection"].endswith("in_sample"):
            assert r["selection"] not in honest


def test_split_sample_rules_judge_only_the_test_window(panel) -> None:
    rules = sbj.membership_rules(panel, {})
    split = panel.index[int(len(panel.index) * sbj.TRAIN_FRACTION)]
    for r in rules:
        if r["window"] != "test":
            continue
        b1, _ = panel.series(r["members"], r["mask"])
        if len(b1):
            assert b1.index.min() >= split, (
                f"{r['name']} judged a day its membership was chosen on")


def test_basket_is_the_summed_per_leg_series_not_a_netted_fiction(panel) -> None:
    """Costs are paid per leg: the basket's 3x arm must be the sum of the members' 3x arms."""
    mask = np.ones(len(panel.index), bool)
    members = [0, 2, 4]
    b1, b3 = panel.series(members, mask)
    expect1 = panel.a1[np.ix_(mask, members)].sum(axis=1)
    expect3 = panel.a3[np.ix_(mask, members)].sum(axis=1)
    assert np.allclose(b1.to_numpy(float), expect1)
    assert np.allclose(b3.to_numpy(float), expect3)
    assert (b3 <= b1 + 1e-12).all(), "the stress arm must never be cheaper than the base arm"


def test_effective_independent_bets_is_bounded_by_the_member_count(panel) -> None:
    mask = np.ones(len(panel.index), bool)
    for members in ([0, 1], [0, 1, 2, 3], [0, 1, 2, 3, 4]):
        rep = sbj.correlation_report(panel, members, mask)
        enb = rep["effective_independent_bets"]
        assert 1.0 - 1e-9 <= enb <= len(members) + 1e-9, (
            f"ENB {enb} outside [1, {len(members)}]: the participation ratio is broken")


def test_perfectly_correlated_legs_are_one_bet() -> None:
    idx = pd.date_range("2020-01-01", periods=300, freq="D")
    v = np.random.default_rng(3).normal(0, 1, 300)
    legs = {f"k{i}": _leg(f"S{i}", 1, 300, 0.1, v.copy(), idx) for i in range(4)}
    p = sbj.Panel(legs)
    rep = sbj.correlation_report(p, [0, 1, 2, 3], np.ones(300, bool))
    assert rep["effective_independent_bets"] == pytest.approx(1.0, abs=1e-6), (
        "four copies of one series must read as ONE independent bet, never four")


def test_inverse_variance_weights_never_use_the_mean(panel) -> None:
    """A weighting that reads the mean would weight a member for having WON. This one cannot."""
    rules = sbj.membership_rules(panel, {})
    r = next(x for x in rules if x["weighting"] == "inverse_variance")
    w = sbj.weights_for(panel, r)
    assert w is not None and len(w) == len(r["members"])
    shifted = sbj.Panel({k: {**v, "ds1": v["ds1"] + 5.0} for k, v in panel.legs.items()})
    r2 = next(x for x in sbj.membership_rules(shifted, {}) if x["name"] == r["name"])
    r2["members"] = r["members"]
    r2["train_mask"] = r["train_mask"]
    assert np.allclose(w, sbj.weights_for(shifted, r2)), (
        "shifting every leg's mean changed the weights: the rule reads performance")


def test_every_basket_is_charged_once_to_the_trial_census(tmp_path) -> None:
    """Nothing is judged for free, and re-judging the same basket is the same trial."""
    ledger = tmp_path / "srb_basket_trials.jsonl"
    rule = {"name": "oos_top8", "weighting": "equal_risk_R", "window": "test"}
    a = sbj.basket_identity(rule, ["k1", "k2"])
    b = sbj.basket_identity(rule, ["k2", "k3"])
    assert a != b, "a different member set is a different trial"
    assert a == sbj.basket_identity(rule, ["k2", "k1"]), "member order is not identity"
    first = sbj.charge_trials([a, b, a], path=ledger)
    assert first["status"] == "CHARGED" and first["charged_now"] == 2
    again = sbj.charge_trials([a, b], path=ledger)
    assert again["charged_now"] == 0 and again["lifetime"] == 2
    assert len(ledger.read_text("utf-8").splitlines()) == 2


def test_the_lifetime_ledger_charges_baskets_to_their_family(tmp_path, monkeypatch) -> None:
    from libs.research import experiment_ledger as el

    (tmp_path / "data").mkdir()
    sbj.charge_trials(["BASKET:x|1", "BASKET:y|2"],
                      path=tmp_path / "data" / "srb_basket_trials.jsonl")
    monkeypatch.setattr(el, "DESK", tmp_path)
    total, by_fam = el._proposer_counts()
    assert total == 2
    assert by_fam == {sbj.FAMILY: 2}

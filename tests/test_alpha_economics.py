"""Alpha Economics gate: encode the desk's hard-won lessons -> reject low-EV ideas cheap."""

from __future__ import annotations

from libs.research.alpha_economics import Idea, ev_score, p_survive, rank


def test_funding_family_beats_price_only():
    # the desk's #1 meta-learning: funding/carry survives, price-only mostly dies
    funding = Idea("carry_variant", tags=["funding_family"])
    price = Idea("mom_variant", tags=["price_only"])
    assert p_survive(funding) > p_survive(price)


def test_no_economic_mechanism_is_hard_killed():
    s = ev_score(Idea("data_mined", est_sharpe=3.0, tags=["no_economic_mechanism"]))
    assert s["verdict"].startswith("REJECT")           # even a fat backtest Sharpe can't save it


def test_price_only_narrow_breadth_hard_killed():
    # options VRP taught us: good IC + breadth 2 = starved -> reject before wasting hours
    s = ev_score(Idea("vrp_2asset", breadth=2, est_sharpe=0.6,
                      tags=["price_only", "narrow_breadth"]))
    assert s["verdict"].startswith("REJECT")


def test_new_orthogonal_data_lifts_ev():
    base = Idea("x", tags=[])
    withdata = Idea("x", tags=["new_orthogonal_data"])
    assert ev_score(withdata)["ev"] > ev_score(base)["ev"]


def test_rank_orders_by_ev_and_queues_top():
    ideas = [
        Idea("strong_funding", est_sharpe=1.0, breadth=40, orthogonality=0.8,
             effort_h=4, tags=["funding_family", "new_orthogonal_data"]),
        Idea("weak_price", est_sharpe=0.3, breadth=30, orthogonality=0.2,
             effort_h=12, tags=["price_only"]),
    ]
    ranked = rank(ideas)
    assert ranked[0]["name"] == "strong_funding"
    assert ranked[0]["verdict"].startswith("QUEUE")
    assert ranked[-1]["ev"] <= ranked[0]["ev"]


def test_ev_rewards_low_effort():
    cheap = Idea("cheap", effort_h=2.0, tags=["funding_family"])
    dear = Idea("dear", effort_h=40.0, tags=["funding_family"])
    assert ev_score(cheap)["ev"] > ev_score(dear)["ev"]   # EV per hour -> cheap tests win

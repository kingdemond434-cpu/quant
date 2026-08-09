"""R0198 -- costs are the growth lever available before any edge is proven.

These pin the two things that make the cost hunt worth having: that funding's SIGN is read
correctly (getting it backwards would systematically pick the paying side), and that an absent
feed degrades the veto rather than the sleeve.
"""
from __future__ import annotations

import json

import pytest
from scripts.run_conviction_trader import COST_REFUSE_R, trade_cost_view, validate
from scripts.run_cost_hunt import (
    EXTREME_FUNDING_8H,
    build_report,
    fetch_funding,
    signed_funding_8h,
)

_SYMS = ("BTCUSDT", "ETHUSDT")


def _http(binance=None, okx=None):
    def f(url, timeout=15):
        if "binance" in url:
            if binance is None:
                raise OSError("451 from this egress region")
            return binance
        if okx is None:
            raise OSError("okx down")
        return okx
    return f


# ---- the sign, which is the whole mechanism ---------------------------------------------------

def test_positive_funding_means_longs_pay_shorts_get_paid():
    """Binance convention. Reading this backwards would make the organ prefer the paying side
    on every instrument -- an anti-edge applied universally, which is worse than no organ."""
    assert signed_funding_8h(0.0003, "LONG") == pytest.approx(0.0003)      # long PAYS
    assert signed_funding_8h(0.0003, "SHORT") == pytest.approx(-0.0003)    # short is PAID
    # and negative funding flips both
    assert signed_funding_8h(-0.0003, "LONG") == pytest.approx(-0.0003)
    assert signed_funding_8h(-0.0003, "SHORT") == pytest.approx(0.0003)


def test_ranking_puts_the_paid_side_first_and_flags_only_extreme_payers():
    rows = [{"symbol": "BTCUSDT", "lastFundingRate": "0.0008"},     # extreme: longs bleed
            {"symbol": "ETHUSDT", "lastFundingRate": "-0.0001"}]    # mild: shorts pay a little
    rep = build_report(_SYMS, http=_http(binance=rows))
    assert rep["status"] == "MEASURED"
    assert rep["sides_ranked"][0] == {"symbol": "BTCUSDT", "direction": "SHORT",
                                      "pays_8h": -0.0008, "stance": "PAID", "extreme": False}
    # EXTREME marks only the side that PAYS it -- the counterparty is being paid, not endangered
    ex = rep["extreme_paying"]
    assert [(x["symbol"], x["direction"]) for x in ex] == [("BTCUSDT", "LONG")]
    assert all(x["pays_8h"] >= EXTREME_FUNDING_8H for x in ex)


def test_unfetchable_symbol_is_no_data_never_zero():
    """An assumed-zero rate on an extreme-funding perp is the silent flattery this fences."""
    rates = fetch_funding(_SYMS, http=_http(binance=None, okx=None))
    assert {r["state"] for r in rates.values()} == {"NO-DATA"}
    assert all(r["funding_8h"] is None for r in rates.values())
    rep = build_report(_SYMS, http=_http(binance=None, okx=None))
    assert rep["status"] == "NO-DATA" and rep["sides_ranked"] == []


def test_okx_fallback_covers_what_binance_missed():
    rows = [{"symbol": "BTCUSDT", "lastFundingRate": "0.0001"}]      # ETH absent from bulk
    rates = fetch_funding(_SYMS, http=_http(
        binance=rows, okx={"data": [{"fundingRate": "0.0002"}]}))
    assert rates["BTCUSDT"]["source"] == "binance"
    assert rates["ETHUSDT"]["source"] == "okx" and rates["ETHUSDT"]["funding_8h"] == 0.0002


# ---- the consumer: cost in R, priced before sizing ---------------------------------------------

def _write_hunt(tmp_path, symbol, rate):
    (tmp_path / "data").mkdir(exist_ok=True)
    (tmp_path / "data/cost_hunt.json").write_text(json.dumps({
        "generated": __import__("datetime").datetime.now(
            tz=__import__("datetime").UTC).isoformat(),
        "rates": {symbol: {"state": "MEASURED", "funding_8h": rate}},
    }), "utf-8")


def test_cost_in_r_is_size_independent_and_signed(tmp_path):
    """Leverage cancels: cost/notional over stop/price. That is what lets the veto price a
    trade BEFORE it is sized, which is the only moment refusing it is free."""
    _write_hunt(tmp_path, "BTCUSDT", 0.0003)
    long_ = trade_cost_view(tmp_path, "BTCUSDT", "LONG", 2.0, 24.0)
    short = trade_cost_view(tmp_path, "BTCUSDT", "SHORT", 2.0, 24.0)
    assert long_["state"] == "MEASURED"
    assert long_["carry"] == "PAYS" and short["carry"] == "PAID"
    # same magnitude, opposite sign -- the fee half is identical, only funding flips
    assert long_["funding_R"] == pytest.approx(-short["funding_R"])
    assert long_["fees_R"] == pytest.approx(short["fees_R"])
    # a WIDER stop makes the same funding cost proportionally LESS of the risk unit
    wide = trade_cost_view(tmp_path, "BTCUSDT", "LONG", 4.0, 24.0)
    assert wide["expected_cost_R"] < long_["expected_cost_R"]


def test_absent_feed_stands_the_veto_down_rather_than_the_sleeve(tmp_path):
    """Fail-open is deliberate HERE and the direction matters: marking still charges costs
    pessimistically either way, so a dead feed must idle the veto, never the trading."""
    out = trade_cost_view(tmp_path, "BTCUSDT", "LONG", 2.0, 24.0)   # no cost_hunt.json at all
    assert out["state"] == "ABSENT"
    assert "veto stands down" in out["why"]
    assert out["fees_R"] > 0        # the known half is still priced


def test_stale_snapshot_is_not_used(tmp_path):
    """A rate older than one 8h funding stamp is a different regime's rate (L1.44)."""
    import datetime as dt
    (tmp_path / "data").mkdir(exist_ok=True)
    (tmp_path / "data/cost_hunt.json").write_text(json.dumps({
        "generated": (dt.datetime.now(tz=dt.UTC) - dt.timedelta(hours=30)).isoformat(),
        "rates": {"BTCUSDT": {"state": "MEASURED", "funding_8h": 0.003}},
    }), "utf-8")
    assert trade_cost_view(tmp_path, "BTCUSDT", "LONG", 2.0, 24.0)["state"] == "ABSENT"


# ---- the veto ----------------------------------------------------------------------------------

def _call(**kw):
    c = {"symbol": "BTCUSDT", "direction": "LONG", "probability": 0.6, "entry_ref": 100.0,
         "invalidation": 99.0, "structure": "prior-session swing low shelf",
         "expected_move_pct": 3.0, "horizon_hours": 24, "driver": "x" * 25,
         "falsifier": "y" * 20}
    c.update(kw)
    return c


def test_extreme_carry_is_refused_with_its_arithmetic():
    ok, why = validate(_call(), costs={"state": "MEASURED",
                                       "expected_cost_R": COST_REFUSE_R + 0.2,
                                       "why": "funding +0.70R over 24h"})
    assert not ok
    assert "expected cost" in why and "break even" in why


def test_a_cheap_trade_and_an_absent_reading_both_pass():
    assert validate(_call(), costs={"state": "MEASURED", "expected_cost_R": 0.02})[0]
    assert validate(_call(), costs={"state": "ABSENT", "why": "no feed"})[0]
    assert validate(_call(), costs=None)[0]          # the veto is additive, never load-bearing


def test_the_paid_side_of_the_same_thesis_is_never_refused(tmp_path):
    """The refusal is of a COST, not of a view. The same conviction arriving on the side that
    gets paid must always survive -- otherwise the veto is quietly a directional filter."""
    _write_hunt(tmp_path, "BTCUSDT", 0.004)          # brutal for longs, a gift for shorts
    long_ = trade_cost_view(tmp_path, "BTCUSDT", "LONG", 1.0, 24.0)
    short = trade_cost_view(tmp_path, "BTCUSDT", "SHORT", 1.0, 24.0)
    assert not validate(_call(), costs=long_)[0]
    assert validate(_call(direction="SHORT", invalidation=101.0), costs=short)[0]


def test_unlisted_contract_is_distinguished_from_an_outage():
    """A venue returning EMPTY is saying it does not list the contract -- permanent, and a
    different answer from a transient failure. Verified 2026-07-31: OKX lists no gold swap, so
    PAXGUSDT is single-venue and its NO-DATA never heals by retrying. Conflating the two sends
    the operator chasing a network fault that does not exist."""
    unlisted = fetch_funding(("PAXGUSDT",), http=_http(binance=None, okx={"data": []}))["PAXGUSDT"]
    assert unlisted["state"] == "NO-DATA" and unlisted["fallback_exists"] is False
    assert "SINGLE-VENUE" in unlisted["why"]

    outage = fetch_funding(("BTCUSDT",), http=_http(binance=None, okx=None))["BTCUSDT"]
    assert outage["state"] == "NO-DATA" and outage["fallback_exists"] is True
    assert "SINGLE-VENUE" not in outage["why"]

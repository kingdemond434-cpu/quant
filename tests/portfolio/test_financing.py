"""The collateral / settlement / balance-sheet layer: margin distance under stress, borrow
UNMEASURED by construction, the EUR account's USD funding priced off the EURUSD swap."""
from __future__ import annotations

from datetime import UTC, datetime

import pytest

from libs.portfolio import financing as F

RATES = {"EURUSD": 1.10, "EURJPY": 160.0, "EURGBP": 0.85}
ACCOUNT = "EUR"

US500 = F.InstrumentTerms.from_row({
    "symbol": "US500", "asset_class": "Indices", "contract_size": 1.0, "digits": 2,
    "tick_size": 0.01, "tick_value": 0.0090909, "currency_margin": "USD",
    "currency_profit": "USD", "swap_long": -5.90, "swap_short": 1.54, "swap_mode": 5,
    "swap_rollover3days": 5, "margin_initial": 0.0}, leverage=100.0)
EURUSD = F.InstrumentTerms.from_row({
    "symbol": "EURUSD", "asset_class": "Forex", "contract_size": 100000.0, "digits": 5,
    "tick_size": 0.00001, "tick_value": 0.90909, "currency_margin": "EUR",
    "currency_profit": "USD", "swap_long": -5.66, "swap_short": 2.01, "swap_mode": 1,
    "swap_rollover3days": 3, "margin_initial": 100000.0}, leverage=500.0)
USDJPY = F.InstrumentTerms.from_row({
    "symbol": "USDJPY", "asset_class": "Forex", "contract_size": 100000.0, "digits": 3,
    "tick_size": 0.001, "tick_value": 0.5625, "currency_margin": "USD",
    "currency_profit": "JPY", "swap_long": 5.95, "swap_short": -15.71, "swap_mode": 1,
    "swap_rollover3days": 3, "margin_initial": 100000.0}, leverage=500.0)
TERMS = {"US500": US500, "EURUSD": EURUSD, "USDJPY": USDJPY}


def _sheet(equity: float, margin: float) -> F.BalanceSheet:
    return F.BalanceSheet(ACCOUNT, equity, equity, F.measured(margin, "test"))


def test_margin_distance_falls_under_the_2020_03_stress_and_the_venue_would_deleverage():
    # Long the index with the margin nearly fully used: a leveraged long-equity book.
    pos = [F.OpenPosition("US500", "LONG", 1.0, 5000.0, price=5000.0, sleeve="idx_long")]
    sheet = _sheet(equity=120.0, margin=45.45)   # 5000 USD / 100 leverage / 1.10 -> 45.45 EUR
    before = F.margin_call_distance(sheet, 5000.0 / 1.10)
    out = F.stress(sheet, pos, TERMS, RATES, F.SCENARIO_2020_03)
    assert out["status"] == F.DECLARED and out["pnl"] < 0
    assert before.known and before.value is not None
    after = out["distance_to_margin_call_after"]
    assert out["equity_after"] < out["equity_before"]
    # a -34% move on 4,545 EUR of notional wipes 120 EUR of equity many times over
    assert out["margin_call"] is True
    assert out["forced_deleveraging"]["triggered"] is True
    assert out["forced_deleveraging"]["closed_in_order"][0]["symbol"] == "US500"
    assert after["value"] is None or after["value"] < before.value
    # the stop-out line is UNMEASURED off the terminal, so the 100% margin-call line was used
    assert "UNMEASURED" in out["forced_deleveraging"]["line_source"]


def test_a_favourable_scenario_leaves_the_distance_intact_and_no_forced_sale():
    pos = [F.OpenPosition("US500", "SHORT", 0.1, 5000.0, price=5000.0)]
    sheet = _sheet(equity=600.0, margin=4.55)
    out = F.stress(sheet, pos, TERMS, RATES, F.SCENARIO_2020_03)
    assert out["pnl"] > 0 and out["margin_call"] is False
    assert out["forced_deleveraging"]["triggered"] is False


def test_borrow_is_unmeasured_by_construction_and_never_a_number():
    b = F.borrow("Apple")
    assert b["status"] == "UNMEASURED_BY_CONSTRUCTION" and b["value"] is None
    assert "swap_short" in b["why"]


def test_the_eur_accounts_usd_funding_is_priced_off_the_eurusd_swap():
    # Long EURUSD: the account is long EUR and SHORT USD -- it has borrowed USD.
    pos = [F.OpenPosition("EURUSD", "LONG", 1.0, 1.10, price=1.10)]
    doc = F.funding_by_currency(pos, TERMS, RATES, ACCOUNT, funding_pairs={"EURUSD": EURUSD},
                                prices={"EURUSD": 1.10})
    usd = doc["legs"]["USD"]
    assert usd["net_notional_account_ccy"] == pytest.approx(-100000.0, rel=1e-6)
    fp = usd["funding_price"]
    assert fp["status"] == F.MEASURED and fp["pair"] == "EURUSD" and fp["side"] == "LONG"
    # -5.66 points x 0.90909 EUR/tick per lot per night on 100,000 EUR of notional
    assert fp["per_lot_night"] == pytest.approx(-5.66 * 0.90909, rel=1e-4)
    assert fp["value"] < 0     # a debit, annualised in bp
    assert doc["legs"]["EUR"]["funding_price"]["status"] == F.MEASURED
    # JPY funding with no EURJPY contract terms supplied is UNMEASURED, never borrowed
    pos2 = [F.OpenPosition("USDJPY", "LONG", 1.0, 150.0, price=150.0)]
    doc2 = F.funding_by_currency(pos2, TERMS, RATES, ACCOUNT, funding_pairs={"EURUSD": EURUSD})
    assert doc2["legs"]["JPY"]["funding_price"]["status"] == F.UNMEASURED


def test_swap_units_follow_the_mt5_mode_table_and_unknown_modes_are_unmeasured():
    pts = F.swap_per_lot_night(EURUSD, "LONG")
    assert pts.known and pts.value == pytest.approx(-5.66 * 0.90909, rel=1e-4)
    pct = F.swap_per_lot_night(US500, "LONG", price=5000.0)
    assert pct.known and pct.value == pytest.approx(-0.059 * 5000.0 * 0.90909 / 360.0, rel=1e-4)
    assert not F.swap_per_lot_night(US500, "LONG").known            # mode 5 needs a price
    odd = F.InstrumentTerms.from_row({"symbol": "X", "swap_long": 1.0, "swap_mode": 3,
                                      "tick_value": 1.0, "tick_size": 1.0})
    assert F.swap_per_lot_night(odd, "LONG").status == F.UNMEASURED
    assert F.swap_per_lot_night(EURUSD, "SIDEWAYS").status == F.UNMEASURED


def test_rollover_nights_charge_three_on_the_triple_night_and_none_at_the_weekend():
    # Wednesday 2026-09-16 10:00 -> Monday 2026-09-21 10:00 across a 22:00 UTC rollover:
    # Wed (triple, 3) + Thu (1) + Fri (1) + Sat/Sun (0) = 5
    entry = datetime(2026, 9, 16, 10, tzinfo=UTC)
    exit_at = datetime(2026, 9, 21, 10, tzinfo=UTC)
    assert F.rollover_nights(entry, exit_at, rollover_hour_utc=22, triple_weekday=2) == 5
    assert F.rollover_nights(entry, entry, rollover_hour_utc=22, triple_weekday=2) == 0
    assert F.triple_swap_weekday(EURUSD) == 2 and F.triple_swap_weekday(US500) == 4
    cal = F.settlement_calendar(entry, EURUSD, rollover_hour_utc=22)
    assert cal["nights_charged_at_next"] == 3 and cal["hours_to_next_rollover"] == 12.0


def test_margin_required_uses_the_leverage_tier_and_is_unmeasured_without_one():
    m = F.margin_required(US500, 1.0, 5000.0, RATES, ACCOUNT)
    assert m.known and m.value == pytest.approx(5000.0 / 100.0 / 1.10, rel=1e-6)
    no_tier = F.InstrumentTerms.from_row({"symbol": "US500", "contract_size": 1.0,
                                          "currency_profit": "USD", "margin_initial": 0.0})
    assert F.margin_required(no_tier, 1.0, 5000.0, RATES, ACCOUNT).status == F.UNMEASURED
    fx = F.margin_required(EURUSD, 1.0, 1.10, RATES, ACCOUNT)
    assert fx.known and fx.value == pytest.approx(100000.0 * 1.10 / 500.0 / 1.10, rel=1e-6)


def test_after_financing_growth_charges_measured_sleeves_and_counts_the_unmeasured():
    out = F.after_financing_growth(0.01, {"a": 0.10, "b": 0.10},
                                   {"a": 0.02, "b": None})
    assert out["financing_drag_log_per_day"] == pytest.approx(0.002)
    assert out["after_financing_log_per_day"] == pytest.approx(0.008)
    assert out["n_sleeves_unmeasured"] == 1 and out["status"] == F.UNMEASURED
    credit = F.after_financing_growth(0.01, {"a": 0.10}, {"a": -0.02})
    assert credit["after_financing_log_per_day"] > 0.01     # a carry credit raises growth


def test_the_2026_tape_scenario_is_measured_from_closes():
    closes = [100.0, 101.0, 99.0, 95.0, 97.0, 98.0]
    worst = F.worst_adverse_move(closes, "LONG", 1)
    assert worst.known and worst.value == pytest.approx(95.0 / 99.0 - 1.0)
    sc = F.tape_scenario("2026 tape", {"US500": worst.value or 0.0}, horizon_days=1.0,
                         provenance="desk bars")
    assert sc.status == F.MEASURED and sc.move_for(US500).value == pytest.approx(worst.value)
    assert F.worst_adverse_move(closes[:1], "LONG", 1).status == F.UNMEASURED


# --------------------------------------------------------------- the counterparty leg (2026-09-23)
def test_the_counterparty_leg_names_the_exposure_and_refuses_to_charge_it() -> None:
    """The mandate's fourth friction. A CFD account holds cash AND positions at ONE broker, so
    the exposure is the whole account and the share is 1.0 by the structure of the instrument.
    It is REPORTED: charging a haircut would shrink the book by an unmeasured constant, which
    Rule 1 forbids, and the two-sided answer to concentration is a second venue."""
    from libs.portfolio import financing as F

    out = F.counterparty(None, [], venue="FusionMarkets-Live", account_kind="live")
    assert out["venue"] == "FusionMarkets-Live" and out["n_venues"] == 1
    assert out["capital_share_at_venue"] == 1.0
    assert out["capital_share_status"] == F.DECLARED_STATUS
    assert out["priced_into_elog"] is False and "Rule 1" in out["why_not_priced"]
    assert out["segregation_status"] == F.UNMEASURED_STATUS
    assert out["equity_at_risk"] is None and out["unmeasured"]

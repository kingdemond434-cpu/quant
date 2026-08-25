"""R0522 -- per-symbol lifetime fee-vs-funding net, and the economic re-entry condition."""
from __future__ import annotations

from libs.research import fee_attribution
from libs.research.carry_symbol_ledger import (
    TAKER_RATE,
    lifetime_net,
    reentry_rate,
    veto_candidates,
)


def _fee(sym: str, n: int, each: float) -> list[dict]:
    return [{"symbol": sym, "time": 1_700_000_000_000 + i, "commission": each} for i in range(n)]


def _fund(sym: str, amounts: list[float]) -> list[dict]:
    return [{"symbol": sym, "incomeType": "FUNDING_FEE", "income": str(a),
             "time": 1_700_000_000_000 + i} for i, a in enumerate(amounts)]


def test_the_taker_rate_matches_the_fee_attribution_constant():
    """A named duplicate is tolerable; a DRIFTING one is not -- the two modules price the same
    bill and a silent divergence would make their artifacts disagree (L1.61)."""
    assert TAKER_RATE == fee_attribution.TAKER_RATE


def test_an_empty_venue_read_is_UNMEASURED_never_a_costless_book():
    out = lifetime_net([], [])
    assert out["measured"] is False
    assert "UNMEASURED" in out["note"]
    assert "net_usd" not in out                      # no totals invented from nothing


def test_the_two_sign_conventions_are_not_mixed():
    """commission is POSITIVE-MEANS-PAID; FUNDING_FEE income is SIGNED. Reading them through one
    convention flips the sign of the entire finding."""
    out = lifetime_net(_fee("A", 2, 5.0), _fund("A", [3.0, -1.0]))
    row = out["by_symbol"][0]
    assert row["funding_usd"] == 2.0                 # +3 received, -1 paid
    assert row["commission_usd"] == 10.0             # both fills PAID
    assert row["net_usd"] == -8.0


def test_the_measured_concentration_reproduces(monkeypatch):
    """The R0522 shape, in miniature: a high-funding name can still be the worst loser, because
    the mechanism is turnover and not rate."""
    fees = _fee("TSTUSDT", 100, 2.2) + _fee("XVGUSDT", 4, 4.5)
    fund = _fund("TSTUSDT", [20.6]) + _fund("XVGUSDT", [21.5])
    out = lifetime_net(fees, fund)
    by = {r["symbol"]: r for r in out["by_symbol"]}
    assert by["TSTUSDT"]["funding_usd"] > by["XVGUSDT"]["funding_usd"] - 1.0  # comparable harvest
    assert by["TSTUSDT"]["net_usd"] < 0 < by["XVGUSDT"]["net_usd"]            # opposite outcomes
    assert out["by_symbol"][0]["symbol"] == "TSTUSDT"                         # sorted worst-first
    assert out["n_net_positive"] == 1


def test_never_held_through_a_settlement_is_its_own_state_not_zero_carry():
    """A name billed but never present when funding paid says something about our HOLD TIME, not
    about the name's carry. Collapsing the two would veto a name for the desk's own behaviour."""
    out = lifetime_net(_fee("Z", 6, 1.0), [])
    row = out["by_symbol"][0]
    assert row["held_through_settlement"] is False
    assert row["n_settlements"] == 0
    assert row["fee_to_funding"] is None             # no meaningful ratio against a zero
    assert out["never_held_symbols"] == ["Z"]


def test_a_zero_funding_settlement_is_an_observation_not_a_missing_row():
    """Held through a stamp at a zero rate is EVIDENCE the name is reachable by carry."""
    out = lifetime_net(_fee("Z", 2, 1.0), _fund("Z", [0.0]))
    row = out["by_symbol"][0]
    assert row["held_through_settlement"] is True
    assert row["n_settlements"] == 1


def test_unusable_rows_are_counted_never_dropped_in_silence():
    fees = [*_fee("A", 3, 1.0), {"symbol": "", "commission": 5.0}, "not-a-mapping"]
    out = lifetime_net(fees, [*_fund("A", [1.0]), {"symbol": "A"}])
    assert out["fee_events_attempted"] == 5
    assert out["fee_events_unusable"] == 2
    assert out["funding_events_unusable"] == 1       # the income-less row


def test_reentry_rate_is_an_economic_condition_scaled_by_our_own_hold_time():
    """Held through 4 settlements over 1 round trip -> a quarter of the round-trip cost per
    settlement. Re-traded every trip -> the full cost, which is the implausible one."""
    patient = {"n_settlements": 4, "n_fee_events": 2}
    churned = {"n_settlements": 1, "n_fee_events": 2}
    assert reentry_rate(patient) == 2 * TAKER_RATE / 4
    assert reentry_rate(churned) == 2 * TAKER_RATE
    assert reentry_rate(patient) < reentry_rate(churned)


def test_reentry_rate_refuses_rather_than_defaults_when_unmeasurable():
    """None is a refusal. A name never held has an UNKNOWN required rate, not a small one, and
    the two must not read alike (L1.28a)."""
    assert reentry_rate({"n_settlements": 0, "n_fee_events": 8}) is None
    assert reentry_rate({"n_settlements": 3, "n_fee_events": 0}) is None


def test_every_veto_carries_a_way_back(monkeypatch):
    """L1.45 -- an exclusion whose only exit is the trading it forbids is a cycle. Forward funding
    must be able to clear it with no position taken."""
    led = lifetime_net(_fee("BAD", 20, 3.0) + _fee("GOOD", 2, 0.1),
                       _fund("BAD", [0.5] * 4) + _fund("GOOD", [9.0]))
    vet = veto_candidates(led)
    assert vet["measured"] is True
    assert [c["symbol"] for c in vet["candidates"]] == ["BAD"]      # GOOD is net-positive
    cand = vet["candidates"][0]
    assert cand["reentry_funding_rate"] is not None
    assert "funding >=" in cand["reentry_condition"]
    assert "RE-ENTRY ONLY" in vet["scope"]


def test_a_veto_without_a_measured_way_back_says_so_out_loud():
    led = lifetime_net(_fee("NEVERHELD", 10, 2.0), [])
    cand = veto_candidates(led)["candidates"][0]
    assert cand["reentry_funding_rate"] is None
    assert "UNKNOWN" in cand["reentry_condition"]
    assert cand["reentry_condition"].endswith("the missing evidence is a hold, not a rate")
    assert veto_candidates(led)["n_without_measured_reentry"] == 1


def test_veto_on_an_unmeasured_ledger_vetoes_nothing():
    out = veto_candidates(lifetime_net([], []))
    assert out["measured"] is False
    assert out["candidates"] == []

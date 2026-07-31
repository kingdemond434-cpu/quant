"""R0137 mechanism attribution -- no sleeve reads as survived on P&L its mechanism cannot explain.

Produced by a live near-miss: the dashboard showed funding carry as a survivor on +24.5% / Sharpe
13.13, while the funding harvest behind it was $113 of $3,669. The desk's own two-sided carry
fence already called that a naked leg -- and its verdict gated nothing.
"""
from __future__ import annotations

import json

from scripts.check_mechanism_attribution import UNATTRIBUTED_FRAC, attribute, build_report

_SPEC = {"mechanism": "funding harvest, delta-neutral", "total_key": "net_pnl",
         "mechanism_key": "funding"}


def test_a_sleeve_earning_from_its_mechanism_is_attributed():
    r = attribute("cash_and_carry", _SPEC, {"net_pnl": 120.0, "funding": 113.06})
    assert r["state"] == "ATTRIBUTED" and r["mechanism_share"] > 0.9


def test_the_live_near_miss_is_caught():
    # The exact numbers off the dashboard: $113 of funding behind $3,669 of P&L.
    r = attribute("cash_and_carry", _SPEC, {"net_pnl": 3669.55, "funding": 113.06})
    assert r["state"] == "UNATTRIBUTED"
    assert r["unexplained_pnl"] == 3556.49
    assert "NOT survived" in r["why"]


def test_an_unexplained_WIN_is_as_disqualifying_as_a_loss():
    # THE POINT. On a delta-neutral book the price legs cancel, so a windfall means a naked leg.
    # A one-sided fence would call that state clean and let the exposure keep running.
    win = attribute("cash_and_carry", _SPEC, {"net_pnl": 3669.55, "funding": 113.06})
    loss = attribute("cash_and_carry", _SPEC, {"net_pnl": -3400.0, "funding": 113.06})
    assert win["state"] == loss["state"] == "UNATTRIBUTED"
    assert "WIN" in win["why"] and "LOSS" in loss["why"]


def test_the_tolerance_is_the_boundary_it_claims_to_be():
    mech = 100.0
    inside = attribute("cash_and_carry", _SPEC,
                       {"net_pnl": mech + mech * (UNATTRIBUTED_FRAC - 0.01), "funding": mech})
    outside = attribute("cash_and_carry", _SPEC,
                        {"net_pnl": mech + mech * (UNATTRIBUTED_FRAC + 0.01), "funding": mech})
    assert inside["state"] == "ATTRIBUTED" and outside["state"] == "UNATTRIBUTED"


def test_a_missing_mechanism_term_is_undecidable_never_clean():
    # A failed venue income read makes attribution UNDECIDABLE. Passing it as clean would let an
    # outage certify a sleeve.
    r = attribute("cash_and_carry", _SPEC, {"net_pnl": 3669.55})
    assert r["state"] == "UNMEASURED" and "UNDECIDABLE" in r["why"]
    r = attribute("cash_and_carry", _SPEC, {"net_pnl": 3669.55, "funding": "n/a"})
    assert r["state"] == "UNMEASURED"


def test_zero_mechanism_with_nonzero_pnl_is_unattributed():
    # Zero harvest and real P&L is the purest version: 100% of it came from somewhere else.
    r = attribute("cash_and_carry", _SPEC, {"net_pnl": 500.0, "funding": 0.0})
    assert r["state"] == "UNATTRIBUTED"
    r = attribute("cash_and_carry", _SPEC, {"net_pnl": 0.0, "funding": 0.0})
    assert r["state"] == "ATTRIBUTED"                 # nothing earned, nothing to explain


def test_no_readable_state_reports_unmeasured_not_ok(tmp_path):
    rep = build_report(tmp_path)
    assert rep["status"] == "UNMEASURED" and "UNDECIDABLE" in rep["detail"]


def test_the_report_fails_the_run_when_unattributed(tmp_path):
    (tmp_path / "research_state.json").write_text(json.dumps(
        {"deployed": {"sleeves": ["cash_and_carry (real)"], "net_pnl": 3669.55, "funding": 113.06}}))
    rep = build_report(tmp_path)
    assert rep["status"] == "UNATTRIBUTED" and rep["n_unattributed"] == 1


def test_sleeves_with_no_measurable_mechanism_are_named_not_silently_passed(tmp_path):
    (tmp_path / "research_state.json").write_text(json.dumps(
        {"deployed": {"sleeves": ["some_new_sleeve (real)"], "net_pnl": 100.0, "funding": 1.0}}))
    rep = build_report(tmp_path)
    assert "some_new_sleeve (real)" in rep["mechanism_unjudgeable"]
    assert "no mechanism term to judge" in rep["detail"]

"""The survival envelope's margin clause is fed from the broker, or carries no clause at all.

`kelly_surface.envelope` has taken a `margin_use` map and a MAX_MARGIN_USE since it was written,
`test_survival_envelope` covers both, and `pf_allocator` never passed the argument -- so the one
clause that is a fact about the VENUE rather than about the desk's own sampled worlds was inert.
It is now measured from `mt5.account_info()`: margin over equity at the heat currently deployed,
extrapolated linearly across the sampled heats (lots scale with heat, so margin use is linear
through the origin).

WHAT MUST NOT REGRESS, and it is the whole safety property: an unmeasured margin carries NO
clause. No terminal, no account, no equity, no open position -> the envelope is called exactly
as it was called before this existed, and its ceiling is byte-identical. A measured account with
headroom changes nothing either. The clause can only bind where the BROKER would liquidate,
which is the integrity carve-out `survival_ceiling` is registered under.
"""
from __future__ import annotations

import inspect
import sys
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.portfolio.kelly_surface import MAX_MARGIN_USE, MEASURED, envelope  # noqa: E402

pa = pytest.importorskip("research.pf_allocator", reason="the allocator ships with the desk")

ALPHA = 0.20
FALLBACK = 0.30
#: The healthy surface from test_survival_envelope: feasible to 40%, ruin at 45%.
HEALTHY = [{"heat": h, "p_ruin": r, "p_dd_over_tolerance": d} for h, r, d in
           ((0.10, 0.0, 0.04), (0.20, 0.0, 0.09), (0.30, 0.0, 0.15),
            (0.40, 0.0, 0.19), (0.45, 0.02, 0.41))]
HEATS = [r["heat"] for r in HEALTHY]


# ------------------------------------------------------------------------------ the arithmetic
def test_margin_use_is_linear_in_heat_through_the_measured_point() -> None:
    mu, why = pa.margin_use_from(margin=2000.0, equity=20000.0, deployed_heat=0.20, heats=HEATS)
    assert mu is not None
    # 10% of the account at 20% heat -> 0.5 of margin per unit of heat.
    assert mu[0.20] == pytest.approx(0.10)
    assert mu[0.40] == pytest.approx(0.20)
    assert mu[0.10] == pytest.approx(0.05)
    assert all(mu[h] == pytest.approx(0.5 * h) for h in HEATS)
    assert "0.5000 of margin per unit of heat" in why


def test_an_unmeasurable_margin_is_no_clause_and_says_which_input_was_missing() -> None:
    for kwargs, token in (
            ({"margin": 2000.0, "equity": 0.0, "deployed_heat": 0.2}, "no denominator"),
            ({"margin": 2000.0, "equity": 20000.0, "deployed_heat": 0.0}, "0/0"),
            ({"margin": 0.0, "equity": 20000.0, "deployed_heat": 0.2}, "no margin in use"),
            ({"margin": float("nan"), "equity": 2e4, "deployed_heat": 0.2}, "not finite"),
            ({"margin": "x", "equity": 2e4, "deployed_heat": 0.2}, "not numbers")):
        mu, why = pa.margin_use_from(heats=HEATS, **kwargs)
        assert mu is None, kwargs
        assert token in why, why
    empty, why = pa.margin_use_from(margin=2e3, equity=2e4, deployed_heat=0.2, heats=[])
    assert empty is None and "no sampled heat" in why
    # A flat book is the common case on this desk and must never read as "margin is free".
    _, why = pa.margin_use_from(margin=0.0, equity=2e4, deployed_heat=0.2, heats=HEATS)
    assert "never licenses heat" in why


def test_a_host_without_a_terminal_measures_nothing_and_never_raises() -> None:
    margin, equity, why = pa.account_margin()
    assert (margin is None) == (equity is None)
    if margin is None:
        assert why and isinstance(why, str)


# ------------------------------------------------------- the clause: absent, or a broker fact
def test_an_unmeasured_margin_leaves_the_envelope_byte_identical() -> None:
    """THE PROPERTY THE STANDING ORDER TURNS ON. No terminal on this host, so the argument is
    omitted and the ceiling is exactly what it was before the clause was fed."""
    before = envelope(HEALTHY, alpha=ALPHA, fallback=FALLBACK)
    after = envelope(HEALTHY, alpha=ALPHA, fallback=FALLBACK, margin_use=None)
    assert after == before
    assert before["ceiling"] == pytest.approx(0.40) and before["status"] == MEASURED
    assert "margin" not in before["why"]


def test_an_account_with_headroom_does_not_move_the_ceiling() -> None:
    """"Can only license more heat where headroom exists" in arithmetic: at 5% of the account
    per 20% of heat, even 45% of heat uses 11% of margin -- far under the 50% bar -- so the
    measured clause holds and the ceiling is the one the worlds gave."""
    mu, _ = pa.margin_use_from(margin=1000.0, equity=20000.0, deployed_heat=0.20, heats=HEATS)
    assert max(mu.values()) < MAX_MARGIN_USE
    with_margin = envelope(HEALTHY, alpha=ALPHA, fallback=FALLBACK, margin_use=mu)
    without = envelope(HEALTHY, alpha=ALPHA, fallback=FALLBACK)
    assert with_margin["ceiling"] == without["ceiling"] == pytest.approx(0.40)
    assert "margin" in with_margin["why"], "the clause held and the artifact should say so"


def test_a_margin_starved_account_binds_where_the_broker_would_liquidate() -> None:
    """The direction this clause exists for: at 30% of the account per 20% of heat, 40% of heat
    would consume 60% of margin -- past the broker's feasibility -- and the envelope stops at
    the last heat that is fundable. This is a venue fact, not a growth preference."""
    mu, _ = pa.margin_use_from(margin=6000.0, equity=20000.0, deployed_heat=0.20, heats=HEATS)
    e = envelope(HEALTHY, alpha=ALPHA, fallback=FALLBACK, margin_use=mu)
    assert e["stopped_by"] == ["margin_use"]
    assert e["ceiling"] == pytest.approx(0.30)
    assert e["max_margin_use"] == pytest.approx(MAX_MARGIN_USE)


# -------------------------------------------------------------------------------- the wiring
def test_the_allocator_feeds_the_clause_and_omits_it_when_unmeasured() -> None:
    src = inspect.getsource(pa.run)
    assert "margin_use=_mu," in src, "the envelope is still called without the argument"
    assert "_acc_margin, _acc_equity, _acc_why = account_margin()" in src
    assert "margin_use_from(_acc_margin, _acc_equity, _free_total, _mu_heats)" in src, (
        "the map must be built from the DEPLOYED heat, not from a constant")
    assert '_mu, _mu_why = (None, "not measured")' in src, "unmeasured must stay the default"
    assert 'survival["margin_use"]' in src, "the artifact must record what was measured"
    # And the audit slot that has always been None is fed from the same reading.
    assert "margin_headroom=_headroom" in src


def test_the_margin_headroom_audit_slot_stops_being_a_permanent_gap() -> None:
    from libs.portfolio.aggression import explain
    common = {"floor": 0.20, "ceiling": 0.30, "total_heat": 0.20, "free_optimum": 0.12,
              "readiness": 0.4, "proof_passed": True, "surface": {}, "book": {}, "ev": []}
    assert "margin_headroom" in explain(**common)["gaps"]
    fed = explain(**common, margin_headroom=0.9)
    assert "margin_headroom" not in fed["gaps"]
    assert fed["components"]["margin_headroom"] == pytest.approx(0.9)

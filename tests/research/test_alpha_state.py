"""GOVERNANCE AN ORGAN CANNOT ROUTE AROUND.

Before this module, nothing in the code made `DISCOVERED -> LIVE` impossible. It was merely undone,
and an undone thing looks identical to an impossible one right up until the morning it does not.
These tests are the difference: each one asserts a REFUSAL, because a state machine that only
records where an alpha sits is a log, not a control.
"""

from __future__ import annotations

from libs.research.alpha_state import (
    ORDER,
    RUNGS,
    TERMINAL,
    AlphaRecord,
    advance,
    next_rung,
    render,
    requirements,
    retreat,
)

_FULL = {
    "expression": "e", "data_source": "d", "n_observations": "500", "result": "r",
    "t_stat": "6.1", "deflated_hurdle": "5.236", "trials_declared": "898560",
    "oos_result": "held", "split_rule_preregistered": "yes",
    "mechanism_cluster": "c3", "correlation_to_book": "0.11",
    "marginal_contribution": "+0.4", "capacity": "9000",
    "shadow_started_at": "2026-08-08", "forward_observations": "60",
    "forward_result": "+1.1bp", "risk_review": "done",
    "principal_authorisation": "TOKEN", "size_quote_units": "200",
    "monitor_since": "2026-09-01",
}


def _climb(stop_before: str | None = None) -> AlphaRecord:
    rec = AlphaRecord(alpha_id="a1")
    for state in ORDER[1:]:
        if state == stop_before:
            break
        rec, _ = advance(rec, state, _FULL)
    return rec


def test_A_SKIPPED_RUNG_IS_REFUSED_EVEN_WITH_THE_HIGHER_EVIDENCE_IN_HAND() -> None:
    """THE CENTRAL PROPERTY. 'We already know it would pass' is exactly the reasoning that never
    gets written down, so the machine refuses the jump rather than merely discouraging it."""
    rec = AlphaRecord(alpha_id="a1")
    out, why = advance(rec, "LIVE", _FULL)
    assert out.state == "DISCOVERED", "an alpha jumped from DISCOVERED to LIVE"
    assert "REFUSED" in why and "the only legal next rung is IMPLEMENTED" in why


def test_EVERY_SINGLE_RUNG_IS_REFUSED_AS_A_SKIP_FROM_THE_BOTTOM() -> None:
    """Not just LIVE. A machine that guarded only the last rung would let an alpha arrive at
    CAPITAL_ELIGIBLE with no evidence and then need one more authorisation to trade."""
    rec = AlphaRecord(alpha_id="a1")
    for target in ORDER[2:]:
        out, why = advance(rec, target, _FULL)
        assert out.state == "DISCOVERED", f"skipped straight to {target}"
        assert "REFUSED" in why


def test_THE_FULL_LADDER_IS_WALKABLE_WITH_COMPLETE_EVIDENCE() -> None:
    """The refusals must not make the machine unusable -- a control nobody can satisfy gets
    deleted or bypassed, which is worse than not having it."""
    rec = _climb()
    assert rec.state == "MONITORED"
    assert [h[0] for h in rec.history] == list(ORDER[1:])


def test_MISSING_EVIDENCE_BLOCKS_A_LEGAL_STEP() -> None:
    rec = AlphaRecord(alpha_id="a1")
    out, why = advance(rec, "IMPLEMENTED", {"expression": "e"})
    assert out.state == "DISCOVERED"
    assert "missing evidence ['data_source']" in why


def test_AN_EMPTY_EVIDENCE_VALUE_COUNTS_AS_MISSING() -> None:
    """An empty string is how a checkbox gets ticked by a script with nothing to say. Accepting it
    would make every requirement satisfiable by an organ that measured nothing."""
    rec = AlphaRecord(alpha_id="a1")
    out, why = advance(rec, "IMPLEMENTED", {"expression": "e", "data_source": "   "})
    assert out.state == "DISCOVERED" and "data_source" in why


def test_LIVE_REQUIRES_A_TOKEN_NO_ORGAN_CAN_SYNTHESISE() -> None:
    """The one rung the machine refuses to reason its way onto. Arming live trading is the
    principal's act; every other rung is evidence the desk can produce for itself."""
    assert "principal_authorisation" in requirements("LIVE")
    rec = _climb(stop_before="LIVE")
    assert rec.state == "CAPITAL_ELIGIBLE"
    ev = {k: v for k, v in _FULL.items() if k != "principal_authorisation"}
    out, why = advance(rec, "LIVE", ev)
    assert out.state == "CAPITAL_ELIGIBLE"
    assert "principal_authorisation" in why


def test_CAPITAL_ELIGIBLE_IS_A_STATEMENT_ABOUT_EVIDENCE_NOT_A_GRANT() -> None:
    rung = next(r for r in RUNGS if r.name == "CAPITAL_ELIGIBLE")
    assert "never a grant" in rung.why


def test_RETREAT_IS_ALWAYS_LEGAL_FROM_ANY_STATE() -> None:
    """A machine that only ratchets forward turns a decayed edge into a permanent one, which is
    worse than having no machine at all."""
    for state in ORDER:
        rec = AlphaRecord(alpha_id="a1", state=state)
        for term in TERMINAL:
            out, _ = retreat(rec, term, reason="decayed")
            assert out.state == term, f"could not retreat from {state} to {term}"


def test_RETREAT_NEEDS_NO_EVIDENCE_BUT_DOES_NEED_A_REASON() -> None:
    """Requiring evidence to retreat would make the SAFE direction the expensive one -- the desk
    would keep a decaying alpha live because retiring it needed a study. A reason is required
    because a silent retirement discards what the failure knows."""
    rec = AlphaRecord(alpha_id="a1", state="LIVE")
    out, why = retreat(rec, "RETIRED", reason="")
    assert out.state == "LIVE" and "needs a stated reason" in why
    out2, _ = retreat(rec, "RETIRED", reason="edge decayed, t fell to 0.8")
    assert out2.state == "RETIRED" and "decayed" in out2.note


def test_RETREAT_CANNOT_BE_USED_TO_CLIMB() -> None:
    """Otherwise it is a promotion path with no evidence requirement -- the bypass, wearing the
    name of the safety valve."""
    rec = AlphaRecord(alpha_id="a1", state="TESTED")
    out, why = retreat(rec, "LIVE", reason="shortcut")
    assert out.state == "TESTED"
    assert "is ABOVE" in why and "use advance() to climb" in why


def test_RETREAT_DOWN_THE_LADDER_IS_ALLOWED() -> None:
    """Monitoring must be able to push an alpha back to SHADOW rather than only to RETIRED --
    all-or-nothing retirement loses the middle case, which is the common one."""
    rec = AlphaRecord(alpha_id="a1", state="LIVE")
    out, _ = retreat(rec, "SHADOW", reason="execution degraded; back to zero capital")
    assert out.state == "SHADOW"


def test_A_TERMINAL_STATE_IS_NOT_A_PAUSE() -> None:
    """Re-entry starts a new record, so the retired history stays readable as evidence instead of
    being overwritten by the next attempt at the same mechanism."""
    rec = AlphaRecord(alpha_id="a1", state="RETIRED")
    out, why = advance(rec, "DISCOVERED", _FULL)
    assert out.state == "RETIRED"
    assert "terminal state is not a pause" in why


def test_ADVANCE_TO_A_TERMINAL_STATE_ROUTES_THROUGH_RETREAT() -> None:
    """One code path decides what a downward move means, so the two cannot drift apart."""
    rec = AlphaRecord(alpha_id="a1", state="TESTED")
    out, _ = advance(rec, "DEGRADED", _FULL)
    assert out.state == "DEGRADED"


def test_THE_TOP_OF_THE_LADDER_REFUSES_POLITELY() -> None:
    rec = AlphaRecord(alpha_id="a1", state=ORDER[-1])
    assert next_rung(ORDER[-1]) is None
    out, why = advance(rec, "ANYTHING", _FULL)
    assert out.state == ORDER[-1] and "no rung above it" in why


def test_A_REFUSAL_LEAVES_THE_RECORD_BYTE_IDENTICAL() -> None:
    """A partial mutation on a refused transition would be the worst of both: the alpha neither
    advanced nor stayed where the report says it is."""
    rec = AlphaRecord(alpha_id="a1", state="TESTED", evidence={"a": "b"})
    out, _ = advance(rec, "LIVE", _FULL)
    assert out == rec


def test_EVERY_RUNG_EXPLAINS_WHY_IT_IS_A_SEPARATE_STEP() -> None:
    """Without it, the next session collapses two rungs to save a call and the reason is gone."""
    for r in RUNGS:
        assert r.why.strip(), r.name


def test_RENDER_NAMES_WHAT_THE_NEXT_RUNG_COSTS() -> None:
    """A line that says only where an alpha sits gives the reader nothing to do."""
    rec = AlphaRecord(alpha_id="a1", state="TESTED")
    line = render(rec)
    assert "TESTED -> STATISTICALLY_VALID" in line
    assert "t_stat" in line and "trials_declared" in line


def test_RENDER_OF_A_TERMINAL_RECORD_SHOWS_THE_REASON() -> None:
    rec, _ = retreat(AlphaRecord(alpha_id="a1", state="LIVE"), "RETIRED", reason="cost drag")
    assert "cost drag" in render(rec)


def test_TRIALS_DECLARED_IS_REQUIRED_BY_NAME() -> None:
    """Deflating on the executed count rather than the declared one is the most respectable route
    to a manufactured survivor, so the count is evidence rather than an assumption."""
    assert "trials_declared" in requirements("STATISTICALLY_VALID")

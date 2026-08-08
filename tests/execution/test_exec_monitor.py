"""EXECUTION MONITORING -- the tests are about MEMORY, because that is what makes it a control.

The forensics already work: on 2026-08-07 they returned three specific defects from 27 real
closes. What was missing is memory. A monitor that re-derives the same flags every morning is a
complaint -- after a week nobody reads it, and the morning a NEW defect appears it looks exactly
like the six before.
"""

from __future__ import annotations

from libs.execution.exec_monitor import (
    MIN_CLEAN_OBSERVATIONS,
    ExecHealth,
    churn_efficiency,
    classify,
    hold_class_report,
    leg_asymmetry,
    render,
    sharpe_of_net,
    update,
)

# --------------------------------------------------------------- regression is the point


def test_A_DEFECT_RETURNING_AFTER_RESOLVED_IS_A_REGRESSION_NOT_A_REPEAT() -> None:
    """THE DESK ALREADY HAS ONE: '4 opens below the funding floor AFTER the gate shipped'. A fix
    that did not hold is worse than one never made, because everything downstream was sized as
    though that leak were closed."""
    prev = {"status": "RESOLVED", "times_regressed": 0}
    status, _streak, regressed = classify(prev, present_today=True)
    assert status == "REGRESSED" and regressed == 1


def test_A_REGRESSION_STAYS_A_REGRESSION_RATHER_THAN_DECAYING_TO_PERSISTING() -> None:
    """Otherwise a fix that failed quietly becomes an ordinary long-standing defect by day two,
    and the fact that someone believed it fixed is lost."""
    prev = {"status": "REGRESSED", "times_regressed": 1}
    status, _s, regressed = classify(prev, present_today=True)
    assert status == "REGRESSED" and regressed == 1


def test_REGRESSIONS_LEAD_THE_HEADLINE() -> None:
    states = update({"gate": {"status": "RESOLVED"}}, {"gate": "not filtering"})
    h = ExecHealth(defects=tuple(states))
    assert "REGRESSION" in h.headline and "spent the desk's belief" in h.headline


# ------------------------------------------------------------------ a clean day is not a fix


def test_ONE_QUIET_DAY_DOES_NOT_RESOLVE_A_DEFECT() -> None:
    """A book that trades sporadically produces quiet days for free. Letting absence close a
    defect is WS-005 aimed at the money path."""
    prev = {"status": "PERSISTING", "clean_streak": 0}
    status, streak, _r = classify(prev, present_today=False, change_recorded=True)
    assert status == "PERSISTING" and streak == 1


def test_RESOLVED_NEEDS_BOTH_A_CLEAN_STREAK_AND_A_RECORDED_CHANGE() -> None:
    """Either alone is not evidence: a streak without a change is a lull, a change without a
    streak is a hope."""
    streak_only = {"status": "PERSISTING", "clean_streak": MIN_CLEAN_OBSERVATIONS}
    assert classify(streak_only, False, change_recorded=False)[0] != "RESOLVED"
    assert classify(streak_only, False, change_recorded=True)[0] == "RESOLVED"


def test_A_KNOWN_DEFECT_ABSENT_TODAY_IS_CARRIED_FORWARD_NOT_DROPPED() -> None:
    """A monitor showing only today's flags reports an empty screen on a quiet day, which reads
    as health."""
    states = update({"old": {"status": "PERSISTING", "occurrences": 3}}, {})
    assert [s.key for s in states] == ["old"]
    assert states[0].is_open


def test_A_NEW_DEFECT_IS_LABELLED_NEW() -> None:
    states = update({}, {"maker_asym": "spot 41.7% vs fut 100%"})
    assert states[0].status == "NEW" and states[0].occurrences == 1


# ------------------------------------------------------------------------- churn


def test_CHURN_IS_JUDGED_AGAINST_NET_AND_NEVER_MINIMISED() -> None:
    """Zero churn is achieved by not trading. A monitor rewarding low turnover would steer the
    desk into holding losers -- which is the >24h bleed already on this tape."""
    good, gmsg = churn_efficiency(net_bps=5.0, turnover=2.0)
    bad, bmsg = churn_efficiency(net_bps=-8.0, turnover=4.0)
    assert good > 0 and "pays" in gmsg
    assert bad < 0 and "COSTS" in bmsg
    assert "slower version" in bmsg, "the cost verdict names no remedy"


def test_NO_TURNOVER_IS_NOT_EFFICIENCY() -> None:
    eff, msg = churn_efficiency(1.0, 0.0)
    assert eff == 0.0 and "not the same as nothing wasted" in msg


# -------------------------------------------------------------------- holding period


def test_HOLD_CLASSES_ARE_REPORTED_SEPARATELY_BECAUSE_THE_SHAPE_IS_THE_FIX() -> None:
    """The live tape: >24h bled -37.54 bps over 23 trades while shorter classes did not. A blended
    P&L shows a modest loss and hides WHICH SHAPE of trade caused it."""
    out = hold_class_report({"<1h": (2.0, 4), ">24h": (-37.54, 23), "1-24h": (0.0, 0)})
    joined = " ".join(out)
    assert "bleeding" in joined and "-37.54" in joined
    assert "NO TRADES -- unmeasured, not clean" in joined


# ------------------------------------------------------------------ leg asymmetry


def test_LEG_ASYMMETRY_IS_REPORTED_PER_LEG_NOT_BLENDED() -> None:
    """The live numbers: futures 100%, spot 41.7%, blend 71%. The blend implies 'nudge the quote';
    the split implies 're-peg the spot quote to the touch', which is a different fix."""
    bad, msg = leg_asymmetry({"fut": 1.0, "spot": 0.417})
    assert bad
    assert "LEG-ASYMMETRIC" in msg and "spot" in msg
    assert "re-peg to the touch" in msg
    assert "blended rate is 70.9%" in msg, "the misleading blend is not shown for contrast"


def test_BOTH_LEGS_HEALTHY_IS_NOT_FLAGGED() -> None:
    assert leg_asymmetry({"fut": 0.95, "spot": 0.88})[0] is False


def test_ONE_LEG_IS_UNDEFINED_RATHER_THAN_CLEAN() -> None:
    ok, msg = leg_asymmetry({"fut": 0.2})
    assert ok is False and "not defined, not absent" in msg


# ---------------------------------------------------------------------- honesty


def test_A_THIN_SAMPLE_SHARPE_IS_NONE_NOT_ZERO() -> None:
    """0.0 reads as 'no edge'; None reads as 'not measured yet'. On 27 closes the second is true."""
    assert sharpe_of_net([1.0]) is None
    assert sharpe_of_net([2.0, 2.0, 2.0]) is None      # zero variance
    assert sharpe_of_net([1.0, -1.0, 2.0]) is not None


def test_NO_OPEN_DEFECTS_IS_NOT_A_CLEAN_BILL_OF_HEALTH() -> None:
    """It is a statement about the flags that RAN. Paths nobody measured are unmeasured, not
    clean -- the distinction this desk keeps having to re-make."""
    assert "flags that RAN" in ExecHealth().headline


def test_THE_RENDER_HIDES_RESOLVED_BUT_SHOWS_REGRESSION_COUNTS() -> None:
    states = tuple(update({"a": {"status": "RESOLVED", "clean_streak": 9}},
                          {"b": "still broken"}))
    text = render(ExecHealth(defects=states))
    assert "b" in text and "[RESOLVED]" not in text

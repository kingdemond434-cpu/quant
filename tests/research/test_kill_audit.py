"""750 CELLS DYING AT ONE GATE POINTS AT THE GATE AS READILY AS AT THE CELLS.

First complete sweep, 2026-08-08: 898,560 evaluated, 762 cleared, 2 independent mechanisms, and
F3 WALK-FORWARD SIGN 750. A counter cannot distinguish "the gate is correctly killing noise" from
"the gate is destroying real alpha", and the two fail asymmetrically -- a validator that is too
loose is caught by the rails, one that is too harsh is silent while every gate reports green.
"""

from __future__ import annotations

from libs.research.kill_audit import (
    SIGN_NOISE_BP,
    STATES,
    THIN_ARM,
    KillRecord,
    classify,
    summarise,
)


def _k(**kw) -> KillRecord:
    base = {"key": "c", "kill": "F3 WALK-FORWARD SIGN", "hurdle": 5.236}
    return KillRecord(**{**base, **kw})


def test_A_THIN_ARM_IS_INSUFFICIENT_EVIDENCE_NOT_A_HARD_KILL() -> None:
    """The gate fired on a sample too thin to establish a sign, which shows the desk cannot tell
    rather than that the cell is wrong. Ruling it HARD_KILL converts absence of evidence into a
    verdict -- this desk's most-repeated defect, aimed where it is least visible."""
    state, why = classify(_k(is_net_bps=0.5, oos_net_bps=-0.4, is_n=THIN_ARM - 1, oos_n=5000))
    assert state == "INSUFFICIENT_EVIDENCE"
    assert "too thin" in why


def test_AN_ARM_INSIDE_THE_NOISE_BAND_MAKES_THE_VALIDATOR_SUSPECT() -> None:
    """The SIGN that decided the kill is a coin flip, so the verdict would plausibly reverse on a
    different but equally reasonable split."""
    state, why = classify(_k(is_net_bps=SIGN_NOISE_BP / 2, oos_net_bps=-0.4,
                             is_n=5000, oos_n=5000))
    assert state == "VALIDATOR_SUSPECT"
    assert "coin flip" in why


def test_ARMS_DISAGREEING_WITH_COMPARABLE_MAGNITUDE_IS_REGIME_CONDITIONAL() -> None:
    """F3 requires BOTH arms positive, so a genuinely conditional mechanism is indistinguishable
    from noise at this gate. That is a false-negative CLASS, not a bug, and naming it is the whole
    contribution."""
    state, why = classify(_k(is_net_bps=0.6, oos_net_bps=-0.55, is_n=4500, oos_n=4500))
    assert state == "REGIME_CONDITIONAL"
    assert "missing variable is the research object" in why


def test_GROSS_POSITIVE_AND_NET_NEGATIVE_IS_EXECUTION_LIMITED() -> None:
    state, why = classify(_k(is_net_bps=-0.3, oos_net_bps=-0.4, is_n=4500, oos_n=4500,
                             gross_bps=0.8, net_bps=-0.2))
    assert state == "EXECUTION_LIMITED"
    assert "round trip eats the edge" in why


def test_A_DECISIVE_DISAGREEMENT_ON_ADEQUATE_SAMPLES_IS_A_HARD_KILL() -> None:
    """The audit must still be able to say a cell is dead, or it is not an audit.

    The failing arm must sit BELOW the conditional floor: `+1.0 / -0.2` is one arm carrying the
    result and the other contradicting it weakly. Comparable magnitudes (`+0.9 / -0.8`) are the
    CONDITIONAL shape and are deliberately not hard -- an earlier version of this test asserted
    the opposite and the classifier was right.
    """
    state, _ = classify(_k(is_net_bps=1.0, oos_net_bps=-0.2, is_n=6000, oos_n=6000,
                           gross_bps=1.4, net_bps=0.2))
    assert state == "HARD_KILL"


def test_COMPARABLE_MAGNITUDES_ARE_CONDITIONAL_AND_NOT_HARD() -> None:
    """The boundary the previous test pins from the other side."""
    assert classify(_k(is_net_bps=0.9, oos_net_bps=-0.8, is_n=6000,
                       oos_n=6000))[0] == "REGIME_CONDITIONAL"


def test_BOTH_ARMS_POSITIVE_MEANS_IT_DIED_ON_MAGNITUDE_NOT_SIGN() -> None:
    """A decaying-but-real edge and an overfit one look the same here, so it is a SOFT kill."""
    state, why = classify(_k(kill="F4 OOS MAGNITUDE", is_net_bps=0.9, oos_net_bps=0.2,
                             is_n=6000, oos_n=6000))
    assert state == "SOFT_KILL"
    assert "not on sign" in why


def test_F5_IS_ALWAYS_A_SPAN_PROBLEM() -> None:
    state, why = classify(_k(kill="F5 SAMPLE FLOOR"))
    assert state == "INSUFFICIENT_EVIDENCE"
    assert "no harness change creates observations" in why


def test_A_SIGN_FLIP_UNDER_ONE_BAR_OF_LAG_IS_CONFIRMED_LEAKAGE() -> None:
    state, why = classify(_k(kill="F6 LEAKAGE", net_bps=1.2, leak_net_bps=-0.9))
    assert state == "LEAKAGE_CONFIRMED"
    assert "timing violation, not decay" in why


def test_A_SHRINK_WITHOUT_A_SIGN_FLIP_IS_ONLY_SUSPECT() -> None:
    """One-bar sensitivity alone does not establish that the information was unavailable at
    decision time -- a genuinely short-lived contemporaneous effect looks identical."""
    state, why = classify(_k(kill="F6 LEAKAGE", net_bps=1.2, leak_net_bps=0.4))
    assert state == "LEAKAGE_SUSPECT"
    assert "Reconstruct the timestamp chain" in why


def test_AN_UNMEASURED_LAG_PROBE_CANNOT_CONFIRM_LEAKAGE() -> None:
    state, why = classify(_k(kill="F6 LEAKAGE PROBE", net_bps=1.0, leak_net_bps=None))
    assert state == "LEAKAGE_SUSPECT" and "UNVERIFIED" in why


def test_A_LEAKAGE_CALL_ON_A_NOISE_BAND_NET_IS_VALIDATOR_SUSPECT() -> None:
    """'Collapses under lag' is a statement about a number never distinguishable from zero."""
    state, _ = classify(_k(kill="F6 LEAKAGE", net_bps=SIGN_NOISE_BP / 3, leak_net_bps=-0.01))
    assert state == "VALIDATOR_SUSPECT"


def test_AN_UNKNOWN_GATE_IS_CLASSIFIED_CONSERVATIVELY_NOT_GUESSED() -> None:
    state, why = classify(_k(kill="F99 SOMETHING NEW"))
    assert state == "SOFT_KILL"
    assert "gap in THIS module, not evidence about the cell" in why


def test_EVERY_VERDICT_IS_A_DECLARED_STATE() -> None:
    for rec in (_k(), _k(kill="F5 SAMPLE FLOOR"), _k(kill="F6 LEAKAGE", net_bps=1.0),
                _k(is_net_bps=0.5, oos_net_bps=0.1, is_n=900, oos_n=900)):
        assert classify(rec)[0] in STATES


def test_NO_RETAINED_CELLS_MEANS_THE_VALIDATOR_IS_UNFALSIFIABLE() -> None:
    """The state the sweep was in until `killed_cells` existed: counts only, nothing to examine."""
    rep = summarise([])
    assert "UNAUDITABLE" in str(rep["headline"])
    assert rep["false_kill_exposure"] is None


def test_EXPOSURE_IS_AN_UPPER_BOUND_AND_MAY_NOT_LOWER_A_BAR() -> None:
    """The number must never become an argument for loosening a gate, so the artifact says so."""
    rep = summarise([_k(is_net_bps=0.6, oos_net_bps=-0.55, is_n=4500, oos_n=4500)])
    assert rep["false_kill_exposure"] == 1.0
    note = str(rep["note"])
    assert "UPPER BOUND" in note
    assert "never be cited as a reason to lower a bar" in note
    assert "A SOFT_KILL is still a kill" in note


def test_VALIDATOR_SUSPECT_LEADS_THE_RANKING() -> None:
    """A problem with the gate outranks a problem with any single cell."""
    rows = summarise([
        _k(key="hard", is_net_bps=0.9, oos_net_bps=-0.8, is_n=6000, oos_n=6000),
        _k(key="susp", is_net_bps=0.001, oos_net_bps=-0.4, is_n=6000, oos_n=6000),
    ])["rows"]
    assert rows[0]["key"] == "susp"


def test_NOTHING_IN_THE_MODULE_PROMOTES() -> None:
    from pathlib import Path
    src = Path("libs/research/kill_audit.py").read_text("utf-8").lower()
    for token in ("def promote", "admit(", "place_order", "size_position"):
        assert token not in src

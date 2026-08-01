"""The promotion gate must fail CLOSED -- an unchecked gate is not a passed gate.

libs/stage15/governance.alpha_governance_gate is the hard barrier into promotion and was
imported by nothing, so the barrier was assembled implicitly per screen. These tests pin the
one property that makes it worth wiring: missing evidence rejects. A safety gate whose
ambiguous branch ALLOWS the action is the defect class this codebase's auditor prompt ranks
first in its own measured history.
"""

from __future__ import annotations

from scripts.promotion_gate import _GATES, evidence_to_gates, judge

_ALL = [k for _, k in _GATES]


def _full(**over):
    return {**dict.fromkeys(_ALL, True), **over}


def test_all_eight_gates_passing_accepts():
    assert judge("ok", _full())["accepted"] is True


def test_any_single_failure_rejects():
    for key in _ALL:
        d = judge(key, _full(**{key: False}))
        assert d["accepted"] is False, key


def test_missing_evidence_rejects_and_is_named():
    """The critical property: unchecked must never read as passed."""
    ev = {k: True for k in _ALL if k != "capacity"}
    d = judge("unchecked", ev)
    assert d["accepted"] is False
    assert "capacity" in d["missing_evidence"]
    assert "not passed" in d["note"]


def test_non_true_values_do_not_pass():
    """Truthy-but-not-True (1, 'yes') must not satisfy a safety gate."""
    for bad in (1, "yes", "true", [1]):
        assert evidence_to_gates(_full(dsr=bad))["dsr_passed"] is False


def test_empty_evidence_rejects_every_gate():
    d = judge("nothing", {})
    assert d["accepted"] is False
    assert len(d["rejected_reasons"]) == len(_ALL)

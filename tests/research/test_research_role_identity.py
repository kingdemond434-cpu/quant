"""A passed falsifier receipt belongs to one hypothesis and real Boolean controls."""
from dataclasses import replace

import pytest

from libs.research import agents as a


@pytest.fixture
def hypothesis():
    observation = a.Observation("rollover volume rises", "owned receipt", ("USDJPY",))
    mechanism = a.Mechanism("rollover", "hedgers", "mandated hedge", "rollover",
                            "settlement", "liquidity providers", "capacity", "signed volume",
                            (observation,))
    return a.Hypothesis("owned", "volume change", mechanism, "fx/rollover", "conditional return",
                        ("effect remains after shuffle",), "session seasonality", "matched clock",
                        "receipt available before decision")


def test_foreign_hypothesis_receipt_cannot_freeze_owned_claim(hypothesis):
    receipt = a.FalsifierReport("foreign", a.REQUIRED_CONTROLS, True)
    with pytest.raises(a.RoleViolation, match="identity"):
        a.to_artifact(hypothesis, receipt)


@pytest.mark.parametrize("value", [None, "false", "true", 1, [], {}])
def test_nonboolean_control_is_never_a_pass(hypothesis, value):
    report = a.falsify(hypothesis, lambda *_: value)
    assert not report.survived and "Boolean" in report.detail


def test_valid_controls_deliver_specified_artifact(hypothesis):
    calls = []

    def control(hyp, name):
        calls.append((hyp.hypothesis_id, name))
        return True

    result = a.research_cycle(list(hypothesis.mechanism.evidence), lambda _: hypothesis.mechanism,
                              lambda _: hypothesis, control)
    assert result.stage == "SPECIFIED" and result.artifact is not None
    assert calls == [("owned", name) for name in a.REQUIRED_CONTROLS]
    assert result.falsifier.survived


@pytest.mark.parametrize("stage", ["MECHANISM", "HYPOTHESIS", "FALSIFIER"])
def test_failure_stage_is_named_and_no_artifact_survives(hypothesis, stage):
    def failure(_):
        raise a.RoleViolation("owned failure")

    result = a.research_cycle(list(hypothesis.mechanism.evidence),
        failure if stage == "MECHANISM" else lambda _: hypothesis.mechanism,
        failure if stage == "HYPOTHESIS" else lambda _: hypothesis,
        lambda *_: stage != "FALSIFIER")
    assert result.stage == stage and result.artifact is None
    assert a.research_cycle([], failure, failure, lambda *_: True).stage == "EVIDENCE"


def test_invalid_role_payloads_and_unrun_controls_are_refused(hypothesis):
    with pytest.raises(a.RoleViolation):
        a.Observation("volume", "")
    with pytest.raises(a.RoleViolation):
        a.Observation("buy now", "receipt")
    with pytest.raises(a.RoleViolation):
        replace(hypothesis.mechanism, why_forced="")
    with pytest.raises(a.RoleViolation):
        replace(hypothesis.mechanism, evidence=())
    with pytest.raises(a.RoleViolation):
        replace(hypothesis, falsifiers=())
    with pytest.raises(a.RoleViolation):
        replace(hypothesis, distinguishing_test="")
    with pytest.raises(a.RoleViolation):
        a.to_artifact(hypothesis, a.FalsifierReport("owned", (), True))
    with pytest.raises(a.RoleViolation):
        a.to_artifact(hypothesis, a.FalsifierReport("owned", (), False, "control"))


def test_control_exception_is_explicit_unmeasured_failure(hypothesis):
    def failure(*_):
        raise TimeoutError("owned clock")

    report = a.falsify(hypothesis, failure)
    assert not report.survived and report.controls_run == ()
    assert "TimeoutError" in report.detail

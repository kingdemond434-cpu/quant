"""A HORIZON NOBODY WROTE DOWN CANNOT HAVE BEEN REACHED (R0430, the prerequisite for R0265's
paired half).

`slot_displacement` has always protected a healthy incumbent because it "ends on its own
pre-registered terms" -- and `tests/research/test_slot_displacement.py` pins that exact phrase,
while NO FIELD anywhere on the desk carried the terms. The one field that looked like it did,
`need`, is recomputed every run from the current effect size, so a decision rule keyed on it
would let the data set its own bar: optional stopping with extra steps.

Two properties are pinned here and they are the whole point:
  1. a pre-registered value SURVIVES the next run unchanged (otherwise it is a target, not a
     pre-registration, however it is labelled), and
  2. an UNDECLARED decision point never resolves to reached OR not-reached.
"""

from __future__ import annotations

import ast
import inspect
import json

import pytest
import scripts.run_axis_shadows as ras

from libs.research.evidence_clock import MIN_OBS
from libs.research.slot_displacement import at_decision_point, classify_slot


def _slot(**kw):
    base = {"name": "ax", "state": "ACCRUING", "evidence": "ACCRUING", "days": 10}
    base.update(kw)
    return base


class TestTheDecisionPointIsPreRegisteredNotRecomputed:
    def test_a_declared_point_is_carried_forward_verbatim(self):
        """The one property that makes it a pre-registration rather than a moving target."""
        assert ras._decision_point(37) == (37, "DECLARED")

    def test_a_clock_that_never_had_one_is_stamped_from_a_constant(self):
        """MIN_OBS does not depend on the sample, which is what makes stamping it honest."""
        point, provenance = ras._decision_point(None)
        assert (point, provenance) == (MIN_OBS, "STAMPED")

    def test_a_declared_point_is_never_replaced_by_the_current_default(self):
        """Even when MIN_OBS itself moves, a clock keeps the terms it was born under."""
        assert ras._decision_point(MIN_OBS + 11)[0] == MIN_OBS + 11

    def test_it_is_an_observation_count_not_a_date(self):
        """L1.48: a calendar gate holds a fast clock back and lets a near-idle one through."""
        point, _ = ras._decision_point(None)
        assert isinstance(point, int)


class TestCarryForwardReadsTheLastArtifact:
    def test_reads_declared_points_off_the_state_file(self, tmp_path, monkeypatch):
        state = tmp_path / "axis_shadow_state.json"
        state.write_text(json.dumps({"axes": [
            {"axis": "alpha", "decision_at_obs": 44},
            {"axis": "beta", "decision_at_obs": 20},
        ]}), "utf-8")
        monkeypatch.setattr(ras, "_STATE", state)
        assert ras._declared_decision_points() == {"alpha": 44, "beta": 20}

    def test_a_row_without_the_field_declares_nothing(self, tmp_path, monkeypatch):
        """A legacy row must not inherit a neighbour's terms, nor invent its own."""
        state = tmp_path / "s.json"
        state.write_text(json.dumps({"axes": [{"axis": "legacy", "need": 31}]}), "utf-8")
        monkeypatch.setattr(ras, "_STATE", state)
        assert ras._declared_decision_points() == {}

    def test_an_absent_artifact_declares_nothing_rather_than_crashing(self, tmp_path, monkeypatch):
        monkeypatch.setattr(ras, "_STATE", tmp_path / "never-written.json")
        assert ras._declared_decision_points() == {}

    def test_corrupt_artifact_declares_nothing(self, tmp_path, monkeypatch):
        bad = tmp_path / "bad.json"
        bad.write_text("{not json", "utf-8")
        monkeypatch.setattr(ras, "_STATE", bad)
        assert ras._declared_decision_points() == {}

    @pytest.mark.parametrize("bad", [0, -5, True, "20", 20.5, None])
    def test_a_non_positive_or_non_int_point_is_not_a_declaration(self, bad, tmp_path, monkeypatch):
        """`True` is the trap: bool is an int subclass and would declare a decision at 1."""
        state = tmp_path / "s.json"
        state.write_text(json.dumps({"axes": [{"axis": "ax", "decision_at_obs": bad}]}), "utf-8")
        monkeypatch.setattr(ras, "_STATE", state)
        assert ras._declared_decision_points() == {}


class TestEveryExitFromEvaluateCarriesTheField:
    """A FIFTH RETURN SITE MUST NOT BE ABLE TO DROP IT IN SILENCE.

    Caught live while building this: `_evaluate` has four return sites and the first patch wired
    two, so `cny_premium` and `walcl_reserve_impulse` published `decision_at_obs: null` while the
    other axes carried a value -- a partial wiring that reads as complete from any single row.
    Diligence found it once; this test is the mechanism, so the next branch cannot repeat it.
    """

    def _return_dicts(self):
        fn = ast.parse(inspect.getsource(ras._evaluate)).body[0]
        return [n.value for n in ast.walk(fn)
                if isinstance(n, ast.Return) and isinstance(n.value, ast.Dict)]

    def test_the_scan_found_the_real_return_sites(self):
        """L1.57: a pass over an empty set of returns proves nothing."""
        assert len(self._return_dicts()) >= 4

    def test_every_axis_row_declares_a_decision_point_and_its_provenance(self):
        for i, node in enumerate(self._return_dicts()):
            keys = {k.value for k in node.keys if isinstance(k, ast.Constant)}
            assert "decision_at_obs" in keys, f"return site #{i} drops decision_at_obs"
            assert "decision_point_provenance" in keys, f"return site #{i} drops its provenance"


class TestUndeclaredNeverResolvesToReachedOrNotReached:
    def test_no_field_is_unknown_not_false(self):
        reached, why = at_decision_point(_slot())
        assert reached is None
        assert "nobody wrote down" in why

    def test_no_observation_count_is_unknown_not_false(self):
        """A declared point with no progress reading is UNMEASURED, never "not yet"."""
        reached, why = at_decision_point(_slot(decision_at_obs=20, days=None))
        assert reached is None and "UNMEASURED" in why

    def test_reached_when_observations_meet_the_declared_point(self):
        reached, why = at_decision_point(_slot(decision_at_obs=20, days=20))
        assert reached is True and "20/20" in why

    def test_short_of_the_point_is_false_with_the_shortfall_in_observations(self):
        reached, why = at_decision_point(_slot(decision_at_obs=20, days=13))
        assert reached is False
        assert "7 observation(s) short" in why, "L1.48: report shortfalls in observations"

    def test_reaching_the_point_is_not_a_verdict(self):
        """The distinction that stops this becoming a promotion gate by accident."""
        _, why = at_decision_point(_slot(decision_at_obs=20, days=25))
        assert "not itself a verdict" in why


class TestDisplacementBehaviourIsUnchanged:
    """The prerequisite ships WITHOUT the paired swap. A healthy incumbent is still untouchable.

    R0430 is explicit that the field comes first and the paired comparison second; wiring the
    swap in the same change would be the thing it exists to prevent.
    """

    def test_a_healthy_incumbent_at_its_decision_point_is_still_protected(self):
        status, why = classify_slot(_slot(decision_at_obs=20, days=25))
        assert status == "PROTECTED"
        assert "reached its pre-registered decision point" in why

    def test_a_healthy_incumbent_short_of_it_is_still_protected(self):
        status, _ = classify_slot(_slot(decision_at_obs=20, days=3))
        assert status == "PROTECTED"

    def test_an_undeclared_incumbent_is_still_protected(self):
        status, why = classify_slot(_slot())
        assert status == "PROTECTED" and "nobody wrote down" in why

    def test_a_degenerate_clock_is_still_reclaimable_whatever_it_declared(self):
        """Instrument faults outrank the decision point -- a broken clock has no terms to serve."""
        status, _ = classify_slot(_slot(state="DEGENERATE", decision_at_obs=999))
        assert status == "RECLAIMABLE"

    def test_a_source_gone_clock_is_reclaimable_not_permanently_blocked(self):
        """The exact source identity vanished, so the clock cannot produce another observation."""
        status, why = classify_slot(_slot(evidence="SOURCE-GONE", days=None))
        assert status == "RECLAIMABLE"
        assert "cannot accrue another observation" in why

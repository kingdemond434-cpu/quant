"""R0241a -- H8 was structurally unreachable because the bar was not part of a candidate's identity.

``Hypothesis`` carries no timeframe and ``planned_hypotheses`` takes none, so the H8 plan is the
SAME (family, subtype, symbol, params) tuples as the D1 plan. ``content_hash`` hashed exactly
those four fields and ``CandidateStore.exists`` matched on the hash alone, globally, across every
campaign ever run -- so once a D1 campaign had banked a hypothesis, its H8 twin was counted
``skipped_duplicate`` forever. Nothing failed; the H8 campaign simply reported that it had already
done the work.

The fix has TWO properties that must both hold, and they pull against each other:
  * a non-D1 bar gets its own identity, or H8 stays unreachable;
  * D1 keeps its LEGACY payload byte-for-byte, or the 1,244 candidates already stored stop
    resolving and the factory re-tests its entire history -- inflating the cumulative trial count
    that deflates every future DSR.
"""
from __future__ import annotations

import pytest

from libs.autodiscovery.generators import planned_hypotheses
from libs.autodiscovery.memory import content_hash
from libs.data.timeframe import Timeframe
from libs.store.hashchain import canonical_json, sha256_hex


def _legacy_hash(hyp) -> str:
    """The pre-R0241a payload, spelled out. If this file ever needs editing to keep the D1 test
    green, that edit IS the re-keying event and must be a deliberate migration."""
    return sha256_hex(canonical_json(
        [hyp.family.value, hyp.subtype, hyp.symbol, sorted(hyp.params.items())]))


@pytest.fixture(scope="module")
def plan():
    return [h for h, _ in planned_hypotheses(["BTCUSDT", "ETHUSDT"])]


def test_the_plan_really_is_bar_blind(plan) -> None:
    """The premise. planned_hypotheses takes no timeframe, so if the hash does not carry one
    there is no other field anywhere that could tell a D1 candidate from its H8 twin."""
    assert plan, "no hypotheses generated -- the rest of this file proves nothing"
    assert not hasattr(plan[0], "timeframe")
    assert not hasattr(plan[0], "bar")


def test_d1_hashes_are_byte_identical_to_the_legacy_payload(plan) -> None:
    for hyp in plan:
        assert content_hash(hyp, Timeframe.D1) == _legacy_hash(hyp)
        assert content_hash(hyp) == _legacy_hash(hyp), "the default must stay D1"


@pytest.mark.parametrize("bar", [Timeframe.H8, Timeframe.H4, Timeframe.H1, Timeframe.M15])
def test_every_other_bar_gets_its_own_namespace(plan, bar) -> None:
    d1 = {content_hash(h, Timeframe.D1) for h in plan}
    other = {content_hash(h, bar) for h in plan}
    assert len(other) == len(plan), f"{bar} hashes collide with each other"
    assert not (d1 & other), f"{bar} still collides with D1 -- the campaign remains unreachable"


def test_two_non_d1_bars_do_not_collide_with_each_other(plan) -> None:
    h8 = {content_hash(h, Timeframe.H8) for h in plan}
    h4 = {content_hash(h, Timeframe.H4) for h in plan}
    assert not (h8 & h4)


def test_a_string_bar_hashes_the_same_as_the_enum(plan) -> None:
    """Callers reach this through a StrEnum, a str, or a value off a JSON config. All three must
    land on one identity or the same hypothesis gets two rows on the same bar."""
    for hyp in plan[:20]:
        assert content_hash(hyp, "H8") == content_hash(hyp, Timeframe.H8)
        assert content_hash(hyp, "D1") == content_hash(hyp, Timeframe.D1)


class TestTheStoreDedupsPerBar:
    def test_a_d1_row_does_not_mark_its_h8_twin_a_duplicate(self, db) -> None:
        """The defect itself, end to end, at the seam the orchestrator actually calls."""
        from libs.autodiscovery.memory import CandidateStore
        from libs.autodiscovery.models import CandidateStatus, ValidationMetrics

        store = CandidateStore(db)
        hyp = planned_hypotheses(["BTCUSDT"])[0][0]
        store.record(campaign_id="camp_d1", hyp=hyp, status=CandidateStatus.REJECTED,
                     metrics=ValidationMetrics(), survived=False, rejection_reason="x",
                     bar=Timeframe.D1)
        assert store.exists(hyp, Timeframe.D1) is True
        assert store.exists(hyp, Timeframe.H8) is False, (
            "the D1 campaign just made every H8 twin unreachable again")

    def test_recording_on_h8_does_not_shadow_d1_either(self, db) -> None:
        from libs.autodiscovery.memory import CandidateStore
        from libs.autodiscovery.models import CandidateStatus, ValidationMetrics

        store = CandidateStore(db)
        hyp = planned_hypotheses(["BTCUSDT"])[0][0]
        store.record(campaign_id="camp_h8", hyp=hyp, status=CandidateStatus.REJECTED,
                     metrics=ValidationMetrics(), survived=False, rejection_reason="x",
                     bar=Timeframe.H8)
        assert store.exists(hyp, Timeframe.H8) is True
        assert store.exists(hyp, Timeframe.D1) is False


def test_the_orchestrator_passes_its_own_bar_to_both_dedup_rungs() -> None:
    """`exists` and the capacity-bank hash are two separate rungs and BOTH gate the same skip.
    Fixing one and not the other leaves H8 blocked by whichever was missed."""
    src = (__import__("pathlib").Path(__file__).resolve().parents[2]
           / "libs/autodiscovery/orchestrator.py").read_text("utf-8")
    assert "self.store.exists(hyp, self.bar)" in src
    assert "content_hash(hyp, self.bar) in _banked" in src
    assert "content_hash(hyp)," not in src, "a bar-blind hash call is left in the orchestrator"

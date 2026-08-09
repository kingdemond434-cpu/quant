"""NAMING A TERRITORY IS NOT HUNTING IT.

`kimi_hunter` stamped every territory its model NAMED into a coverage file and then excluded
everything in that file for 45 days. Its Wave 1 is mapping only -- `if w == 1: continue`, findings
are not even permitted -- so **the ground the mapping wave had just judged most interesting was
locked out before any hunt ran against it.** The coverage file recorded that as progress.

Four states were collapsed into one mark. These tests keep them apart:

    YIELDED     hunted, produced findings              -> picked over, exclude
    EMPTY       hunted, nothing there                  -> picked over, exclude (negative knowledge)
    NAMED_ONLY  named by mapping, never hunted         -> FRONTIER, chase first
    BLOCKED     hunt attempted, could not complete     -> FRONTIER, the blocker may have lifted

The load-bearing test is `test_LEGACY_HISTORY_MIGRATES_AS_UNHUNTED`: the existing coverage file
carries only `first_seen`, and migrating those as covered would preserve the bug across the whole
history while looking like a clean upgrade.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from libs.research import hunt_frontier as hf


def _ago(days: float) -> str:
    return (datetime.now(tz=UTC) - timedelta(days=days)).isoformat()


class TestVector:
    def test_unknown_outcome_is_refused(self) -> None:
        with pytest.raises(ValueError, match="unknown outcome"):
            hf.Vector(name="x", outcome="SORT_OF_LOOKED")

    def test_only_a_completed_hunt_covers_ground(self) -> None:
        assert hf.Vector(name="a", outcome="YIELDED").covered
        assert hf.Vector(name="b", outcome="EMPTY").covered
        assert not hf.Vector(name="c", outcome="NAMED_ONLY").covered
        assert not hf.Vector(name="d", outcome="BLOCKED").covered

    def test_NAMED_ONLY_IS_ALWAYS_HUNTABLE(self) -> None:
        """The whole defect in one assertion: a mapping wave's output is frontier, not coverage."""
        v = hf.Vector(name="korean forums", outcome="NAMED_ONLY", first_seen=_ago(1))
        ok, why = v.huntable(datetime.now(tz=UTC))
        assert ok is True
        assert "NAMED but never hunted" in why

    def test_a_blocker_expires_but_a_mine_does_not(self) -> None:
        now = datetime.now(tz=UTC)
        fresh_block = hf.Vector(name="a", outcome="BLOCKED", last_attempt=_ago(2))
        old_block = hf.Vector(name="b", outcome="BLOCKED", last_attempt=_ago(30))
        mined = hf.Vector(name="c", outcome="YIELDED", last_attempt=_ago(30))
        assert fresh_block.huntable(now)[0] is False
        assert old_block.huntable(now)[0] is True, "a blocker is a fact about a moment"
        assert mined.huntable(now)[0] is False, "30d < the 45d cooldown"
        assert mined.huntable(now, cooldown_d=10)[0] is True

    def test_A_DAMAGED_TIMESTAMP_ALLOWS_THE_HUNT(self) -> None:
        """The safe direction is asymmetric: re-hunting costs one pass, wrongly excluding costs
        the finding permanently and silently."""
        v = hf.Vector(name="a", outcome="YIELDED", last_attempt="not-a-date")
        ok, why = v.huntable(datetime.now(tz=UTC))
        assert ok is True
        assert "permanently and silently" in why


class TestMigration:
    def test_LEGACY_HISTORY_MIGRATES_AS_UNHUNTED(self, tmp_path: Path) -> None:
        """THE ONE THAT MATTERS. The old file recorded only `first_seen` -- no outcome, because
        outcomes were never tracked. Reading those as covered would carry the bug forward across
        the entire history while looking like a clean upgrade."""
        f = tmp_path / "cov.json"
        f.write_text(json.dumps({"vectors": {
            "korean algo forums": {"first_seen": _ago(2)},
            "japanese quant blogs": {"first_seen": _ago(40)},
        }}), "utf-8")
        st = hf.load(f)
        assert {v.outcome for v in st.vectors.values()} == {"NAMED_ONLY"}
        assert all(not v.covered for v in st.vectors.values())
        fr = hf.frontier(st)
        assert len(fr["unhunted"]) == 2 and not fr["picked_over"]

    def test_a_missing_or_broken_file_is_an_empty_state(self, tmp_path: Path) -> None:
        assert hf.load(tmp_path / "nope.json").vectors == {}
        bad = tmp_path / "bad.json"
        bad.write_text("{not json", "utf-8")
        assert hf.load(bad).vectors == {}

    def test_round_trip(self, tmp_path: Path) -> None:
        f = tmp_path / "c.json"
        st = hf.VectorState()
        hf.record(st, "a", outcome="YIELDED", findings=3)
        hf.record(st, "b", outcome="BLOCKED", blocker="paywall")
        hf.save(st, f)
        back = hf.load(f)
        assert back.vectors["a"].outcome == "YIELDED" and back.vectors["a"].findings == 3
        assert back.vectors["b"].blocker == "paywall"


class TestRecord:
    def test_naming_does_not_count_as_an_attempt(self) -> None:
        st = hf.VectorState()
        v = hf.record(st, "a", outcome="NAMED_ONLY")
        assert v.attempts == 0 and v.last_attempt == ""

    def test_a_real_hunt_counts(self) -> None:
        st = hf.VectorState()
        hf.record(st, "a", outcome="BLOCKED", blocker="rate limit")
        v = hf.record(st, "a", outcome="YIELDED", findings=2)
        assert v.attempts == 2
        assert v.findings == 2
        assert v.first_seen, "first_seen must survive a re-record"


class TestTheFreeGate:
    def test_AN_EMPTY_FILE_ALWAYS_HUNTS(self) -> None:
        """A gate that refused on no evidence would guarantee the file stayed empty forever."""
        go, why = hf.should_hunt(hf.VectorState())
        assert go is True
        assert "run #1 bootstraps" in why

    def test_it_closes_when_everything_is_genuinely_mined(self) -> None:
        st = hf.VectorState()
        hf.record(st, "a", outcome="YIELDED", findings=1)
        go, why = hf.should_hunt(st)
        assert go is False
        assert "rediscover what the desk already has" in why
        assert "Next opens in" in why

    def test_ONE_UNHUNTED_TERRITORY_IS_ENOUGH_TO_FIRE(self) -> None:
        st = hf.VectorState()
        for i in range(20):
            hf.record(st, f"mined{i}", outcome="YIELDED", findings=1)
        assert hf.should_hunt(st)[0] is False
        hf.record(st, "new ground", outcome="NAMED_ONLY")
        go, why = hf.should_hunt(st)
        assert go is True
        assert "1 NAMED-but-never-hunted" in why

    def test_a_lifted_blocker_reopens_the_gate(self) -> None:
        st = hf.VectorState()
        hf.record(st, "a", outcome="YIELDED", findings=1)
        st.upsert(hf.Vector(name="b", outcome="BLOCKED", last_attempt=_ago(30)))
        go, why = hf.should_hunt(st)
        assert go is True
        assert "1 BLOCKED past retry" in why


class TestPromptSections:
    def test_frontier_is_CHASED_not_excluded(self) -> None:
        st = hf.VectorState()
        hf.record(st, "russian telegram quant", outcome="NAMED_ONLY")
        sec = hf.prompt_sections(st)
        assert "HUNT THESE FIRST" in sec["priority"]
        assert "russian telegram quant" in sec["priority"]
        assert "russian telegram quant" not in sec["exclude"]

    def test_A_BLOCKED_TERRITORY_IS_NEVER_CALLED_MINED(self) -> None:
        """The same conflation, relocated into the prompt -- which is where a wrong label actually
        changes behaviour."""
        st = hf.VectorState()
        hf.record(st, "mined one", outcome="YIELDED", findings=2)
        hf.record(st, "walled one", outcome="BLOCKED", blocker="no transcripts")
        ex = hf.prompt_sections(st)["exclude"]
        mined_block = ex.split("BLOCKED AND RETRIED")[0]
        assert "walled one" not in mined_block, "a blocked territory must not read as picked over"
        assert "they are not mined" in ex
        assert "no transcripts" in ex

    def test_no_history_tells_the_hunter_to_decide(self) -> None:
        sec = hf.prompt_sections(hf.VectorState())
        assert "Generate NEW vectors" in sec["priority"]
        assert sec["exclude"] == ""

    def test_blocked_past_retry_is_priority_not_exclusion(self) -> None:
        st = hf.VectorState()
        st.upsert(hf.Vector(name="old wall", outcome="BLOCKED", last_attempt=_ago(30),
                            blocker="paywall", attempts=1))
        sec = hf.prompt_sections(st)
        assert "old wall" in sec["priority"]
        assert "may have lifted" in sec["priority"]


class TestSummarise:
    def test_report_shape(self) -> None:
        st = hf.VectorState()
        hf.record(st, "a", outcome="YIELDED", findings=4)
        hf.record(st, "b", outcome="NAMED_ONLY")
        hf.record(st, "c", outcome="EMPTY")
        r = hf.summarise(st)
        assert r["vectors"] == 3
        assert r["unhunted"] == 1
        assert r["total_findings"] == 4
        assert r["yield_rate"] == pytest.approx(1 / 3, abs=1e-3)  # summarise rounds to 3dp
        assert r["should_hunt"] is True
        assert "never hunted" in str(r["headline"])

    def test_empty_state_has_no_yield_rate_rather_than_zero(self) -> None:
        assert hf.summarise(hf.VectorState())["yield_rate"] is None

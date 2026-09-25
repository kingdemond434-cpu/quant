"""THE SEMANTIC LEAK THAT SILENCED ITS OWN ALARM.

Until 2026-08-09 `classify()` returned `"survivor"` for any decision-ledger row whose PROSE
contained "wired". On a desk whose ledger is largely about wiring modules that fired 82 times
against a true confirmed count of 0 -- and because `prior_dominated` was computed from that same
tally, the phantom survivors switched OFF the warning that says *do not present this as
data-driven*. The leak did not merely mislabel a column; it disabled its own alarm.

The identical bug had already been found and fixed in `scripts/research_alpha_optimizer.py`, whose
source still carries the note that it counted 63 when the truth was 0. Nobody swept for siblings.
That is what these tests are for: they pin the invariant in the sibling, so the next instance of
this defect class cannot reopen quietly in either file.

THE INVARIANT, in one line: **a number that a keyword can raise must never be able to lower a
disclaimer.**
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import scripts.research_allocator as ra


class TestClassifyNeverInventsASurvivor:
    def test_THE_WORD_WIRED_IS_NOT_A_SURVIVOR(self) -> None:
        """The exact string that produced 82 phantom survivors."""
        assert ra.classify("wired the funding collector into the cycle") == "claimed_progress"

    @pytest.mark.parametrize("prose", [
        "forward clock started for kimchi premium",
        "screen-interesting candidate found in liquidity",
        "replicated the stablecoin result on a second venue",
    ])
    def test_no_prose_reaches_the_survivor_label(self, prose: str) -> None:
        assert ra.classify(prose) == "claimed_progress"

    def test_THERE_IS_NO_SURVIVOR_BUCKET_AT_ALL(self) -> None:
        """The strongest form of the guarantee: the label cannot be produced or paid.

        Deleting the bucket rather than down-weighting it means a future edit cannot restore the
        1.00 reward by changing one number -- it would have to reintroduce the concept, which is
        a visible act rather than a tweak.
        """
        assert "survivor" not in ra.REWARD
        corpus = [
            "wired", "forward clock", "replicat", "screen-interesting",
            "refuted at power", "built a new validator rail", "underpowered and data-blocked",
            "nothing wired yet", "killed, zero predictive value", "",
        ]
        assert all(ra.classify(t) != "survivor" for t in corpus)

    def test_a_claim_is_never_paid_more_than_a_method_upgrade(self) -> None:
        assert ra.REWARD["claimed_progress"] <= ra.REWARD["method"]
        assert ra.REWARD["claimed_progress"] < ra.REWARD["refutation"], (
            "a decisive refutation is real knowledge; a prose claim is not, and paying the claim "
            "more would defund the areas that produce powered nulls")

    def test_the_negations_still_hold(self) -> None:
        assert ra.classify("nothing wired yet, still blocked") == "inconclusive"
        assert ra.classify("not wired -- refuted at power") == "refutation"

    def test_the_other_labels_are_unchanged(self) -> None:
        assert ra.classify("refuted at power, zero predictive value") == "refutation"
        assert ra.classify("built a new validator rail") == "method"
        assert ra.classify("underpowered, data-blocked") == "inconclusive"
        assert ra.classify("") == "inconclusive"


class TestConfirmedSurvivorsAreGroundTruth:
    def test_an_unreadable_tracker_is_UNMEASURED_NOT_ZERO(self, tmp_path: Path,
                                                          monkeypatch: pytest.MonkeyPatch) -> None:
        """L1.28a. 'We cannot see the numerator' is not 'the numerator is zero'."""
        monkeypatch.setattr(ra, "SHADOW", tmp_path / "absent.json")
        n, why = ra.confirmed_survivors()
        assert n is None
        assert "UNMEASURED" in why

    def test_malformed_is_also_unmeasured(self, tmp_path: Path,
                                          monkeypatch: pytest.MonkeyPatch) -> None:
        bad = tmp_path / "bad.json"
        bad.write_text("{not json", "utf-8")
        monkeypatch.setattr(ra, "SHADOW", bad)
        assert ra.confirmed_survivors()[0] is None

    def test_an_empty_tracker_is_a_REAL_zero(self, tmp_path: Path,
                                             monkeypatch: pytest.MonkeyPatch) -> None:
        """The other half of the distinction: a readable tracker with no eligible axis IS zero."""
        f = tmp_path / "s.json"
        f.write_text(json.dumps({"axes": [{"verdict": "PENDING"}]}), "utf-8")
        monkeypatch.setattr(ra, "SHADOW", f)
        n, why = ra.confirmed_survivors()
        assert n == 0
        assert "UNMEASURED" not in why

    def test_only_ELIGIBLE_counts(self, tmp_path: Path,
                                  monkeypatch: pytest.MonkeyPatch) -> None:
        f = tmp_path / "s.json"
        f.write_text(json.dumps({"axes": [
            {"verdict": "ELIGIBLE"}, {"verdict": "ELIGIBLE"},
            {"verdict": "PENDING"}, {"verdict": "KILLED"}, {},
        ]}), "utf-8")
        monkeypatch.setattr(ra, "SHADOW", f)
        assert ra.confirmed_survivors()[0] == 2


class TestTheAlarmCannotBeSilencedByProse:
    """The regression that matters. Everything above is a means to this end."""

    @staticmethod
    def _prior_dominated(confirmed: int | None, total_n: int) -> bool:
        # Mirrors the gate in main(). Kept in one place so a drift between them fails a test
        # rather than reopening the defect.
        return (confirmed is None) or confirmed < 5 or total_n < 30

    def test_EIGHTY_TWO_CLAIMS_DO_NOT_LIFT_THE_GATE(self) -> None:
        """The exact historical numbers: 82 prose claims, 439 attempts, 0 confirmed."""
        assert self._prior_dominated(0, 439) is True, (
            "82 prose claims across 439 attempts must NOT clear the gate when the confirmed "
            "count is zero -- that is precisely the state that suppressed the warning")

    def test_unmeasured_fails_closed(self) -> None:
        assert self._prior_dominated(None, 10_000) is True

    def test_confirmed_evidence_does_lift_it(self) -> None:
        """A gate that can never open is not a gate; it must still respond to real evidence."""
        assert self._prior_dominated(5, 100) is False

    def test_the_gate_still_respects_thin_attempts(self) -> None:
        assert self._prior_dominated(50, 10) is True

    def test_the_live_gate_matches_this_mirror(self) -> None:
        """Reads the artifact the script actually wrote, so the mirror cannot drift unnoticed."""
        art = Path("data/research_allocation.json")
        if not art.exists():
            pytest.skip("allocator has not run on this host")
        d = json.loads(art.read_text("utf-8"))
        assert "confirmed_survivors" in d, "the artifact must carry ground truth, not prose"
        assert "total_survivors" not in d, (
            "the old unqualified key is what downstream readers would trust; it must not return")
        assert d["prior_dominated"] == self._prior_dominated(
            d["confirmed_survivors"], d["total_attempts"])


class TestTheArtifactCannotMisleadADashboard:
    def test_the_prose_count_is_named_as_prose(self) -> None:
        art = Path("data/research_allocation.json")
        if not art.exists():
            pytest.skip("allocator has not run on this host")
        d = json.loads(art.read_text("utf-8"))
        assert "claimed_progress_from_prose" in d
        for row in d["areas"]:
            assert "survivors" not in row, (
                f"{row['area']} still exposes a bare `survivors` key -- a dashboard reading it "
                "would present keyword hits as validated edges, which is the whole defect")

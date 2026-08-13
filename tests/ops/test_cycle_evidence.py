"""The shared cycle-evidence definition (R0336).

WHAT THESE LOCK. Two fences scored a cycle on vocabulary and on format, disagreed with each other
about the same log on 2026-08-01, and were both acked into silence for 14 days rather than fixed.
The tests below pin the three properties that repair depends on:

  * the CHEAP direction is closed -- typing a magic word, or pasting filenames nobody opened,
    buys nothing;
  * the EXPENSIVE direction is rewarded -- a cycle that reads carefully and reports its numbers
    scores, whatever dialect it writes in;
  * the two fences cannot issue contradictory verdicts, because there is one definition.

AND THE BAR DOES NOT MOVE. `test_the_floor_did_not_move` exists because the failure mode for a
fence like this is not a bad rewrite, it is a quiet loosening six months later.
"""
from __future__ import annotations

from libs.ops import cycle_evidence as ce


class TestTheCheapDirectionIsClosed:
    """Everything that used to buy a pass without doing the work."""

    def test_typing_the_magic_word_alone_is_not_interrogation(self) -> None:
        """The old fence passed any log containing 'probe'. This one asks for evidence."""
        ev = ce.score("I probed the system. Everything is fine. Verified.")
        assert ev.substance == 0
        assert ev.cited_claims == 0

    def test_pasting_filenames_nobody_opened_does_not_clear_the_floor(self) -> None:
        """Five bare paths passed the count this replaces; without values they prove nothing."""
        text = "\n".join(["Reviewed scripts/max_audit.py", "Reviewed libs/ops/fresh.py",
                          "Reviewed data/forward_slots.json", "Reviewed docs/CONSTITUTION.md",
                          "Reviewed ops/crontab.manifest.txt", "All fine."])
        ev = ce.score(text)
        assert ev.artifacts == 5, "the paths are all named"
        assert ev.cited_claims == 0, "but not one of them carries a value that was read"
        assert not ev.cited

    def test_a_log_cannot_satisfy_itself_with_the_digits_in_its_own_filename(self) -> None:
        """'20260811_2000.log' is path-shaped and full of digits. It is not a read."""
        ev = ce.score("=== cycle 20260811_2000.log started ===")
        assert ev.cited_claims == 0

    def test_bare_module_names_are_not_citations(self) -> None:
        """max_audit.CHECKS is how the desk cites when it is citing badly. The forward fix for
        that is the cycle prompt, not a fence that accepts it."""
        ev = ce.score("Checked max_audit.CHECKS and desk_memory._test_exists, both fine at 12.")
        assert ev.cited_claims == 0


class TestTheExpensiveDirectionIsRewarded:
    def test_a_path_with_a_value_on_the_same_line_is_a_cited_claim(self) -> None:
        ev = ce.score("read web/growth_audit.json, capital_util=1.005")
        assert ev.cited_claims == 1
        assert ev.substance == 1

    def test_the_same_path_without_a_value_is_only_an_artifact(self) -> None:
        ev = ce.score("read web/growth_audit.json and it looked fine")
        assert ev.artifacts == 1
        assert ev.cited_claims == 0

    def test_a_file_line_reference_counts_because_the_prompt_accepts_a_line(self) -> None:
        """'file path + the value/LINE you saw' -- the prompt's own words."""
        ev = ce.score("the wiring is at run_cashcarry_executor.py:1864")
        assert ev.cited_claims == 1

    def test_the_desks_own_dialects_of_a_value_all_count(self) -> None:
        for value in ("-17.6%", "+2,782.28", "0.018bps",
                      "−1869.74", "$4,805.61", "22/27"):  # noqa: RUF001
            ev = ce.score(f"data/x.json shows {value}")
            assert ev.cited_claims == 1, f"{value!r} should read as a value"

    def test_a_cycle_that_interrogates_in_its_own_words_scores(self) -> None:
        """THE 2026-08-01 FALSE POSITIVE. No magic word appears anywhere in this text."""
        text = ("Two of my own hypotheses were wrong and I am logging them rather than quietly "
                "dropping them. The 502 close-all storm self-resolved -- not an open rail failure.")
        ev = ce.score(text)
        assert ev.substance > 0, "this cycle plainly interrogated itself"
        assert ev.self_corrections + ev.refutations > 0


class TestTheTwoFencesCannotContradict:
    def test_a_cited_claim_always_implies_substance(self) -> None:
        """The interrogation fence fires on substance==0; the citation fence on cited_claims<5.
        If citations can exist without substance the two can disagree, so this is the invariant
        the whole repair rests on."""
        ev = ce.score("data/a.json=1\ndata/b.json=2\ndata/c.json=3")
        assert ev.cited_claims == 3
        assert ev.substance >= ev.cited_claims

    def test_interrogated_well_but_cited_badly_is_expressible(self) -> None:
        """The real 2026-08-01 state, which the old pair could only describe by contradicting
        itself: one fence said no interrogation, the other said the interrogation lacked cites."""
        text = ("The premise was refuted by the import graph. My own claim was wrong and is "
                "withdrawn. Checked max_audit.CHECKS -- 12 entries.")
        ev = ce.score(text)
        assert ev.substance > 0, "interrogation happened -- check_interrogation must stay silent"
        assert not ev.cited, "but it cited nothing -- the citation fence must fire"


class TestUnmeasuredIsNotHealth:
    def test_unmeasured_carries_no_evidence_and_says_why(self) -> None:
        ev = ce.unmeasured("no cycle log is both post-protocol and >=2000 bytes")
        assert not ev.measured
        assert ev.substance == 0
        assert "post-protocol" in ev.why_unmeasured

    def test_unmeasured_is_distinguishable_from_a_scored_empty_log(self) -> None:
        """Both have substance 0. Only one of them means 'we could not look' (L1.28a)."""
        scored = ce.score("")
        assert scored.measured and ce.unmeasured("x").measured is False


class TestTheBarDidNotMove:
    def test_the_floor_did_not_move(self) -> None:
        """The fence this replaces demanded 5 named reads. It still demands 5 -- each of which
        must now carry a value, which is STRICTLY HARDER. Editing a guard to fit the violation it
        caught is the failure this desk has paid for repeatedly."""
        assert ce.CITED_FLOOR == 5

    def test_scoring_is_strictly_harder_per_item_than_counting_paths(self) -> None:
        text = "\n".join(f"scripts/f{i}.py" for i in range(9))
        ev = ce.score(text)
        assert ev.artifacts == 9
        assert ev.cited_claims < ev.artifacts

    def test_the_verdict_is_serialisable_for_audit(self) -> None:
        d = ce.score("data/x.json=1").to_dict()
        assert d["cited_claims"] == 1 and d["substance"] == 1 and d["cited"] is False

"""THE POLICE ITSELF, PINNED -- including the alarm it must never raise falsely.

WHY THIS FILE MATTERS MORE THAN MOST. This instrument's whole job is to notice when the audit
stops looking. If it goes wrong in the QUIET direction it reports WATCHING over a blind desk,
which is worse than not existing -- it converts an absent guarantee into a stated one. If it goes
wrong in the LOUD direction it cries wolf, gets ignored, and this desk has already paid eleven and
a half days of unread pages for exactly that.

Both directions are tested here, and the loud one is not hypothetical: the FIRST live run named
four blind spots and ALL FOUR WERE FALSE. `bnb-funded` and `fee-carry-ratio` query the exchange
over HTTP, `dig-uncommitted` shells to `git status`, `check-registry` reads module globals -- none
opens a file, every one genuinely evaluates. The metric counted file reads only. It now counts any
external consultation, and the two that remained blind afterwards turned out to be REAL and were
fixed rather than exempted.
"""
from __future__ import annotations

from libs.ops.law_police import (
    BROKEN,
    CANNOT_EVALUATE,
    CLEAN,
    DEFECTIVE,
    EVALUATES_IN_MEMORY,
    NEVER_AUTO_CORRECT,
    CheckState,
    diff_roster,
    grade_check,
    police,
    repairs_for,
    unexplained_falls,
)


def _roster(states: list[CheckState]) -> dict:
    return {"roster": {c.name: {"state": c.state} for c in states}}


class TestTheThirdState:
    """A check that raised nothing and consulted nothing is NOT clean."""

    def test_raised_nothing_and_read_nothing_is_a_blind_spot(self) -> None:
        c = grade_check("x", n_defects=0, n_evidence=0)
        assert c.state == CANNOT_EVALUATE
        assert "BLIND SPOT" in c.why or "blind" in c.why.lower()

    def test_raised_nothing_but_read_something_is_a_genuine_pass(self) -> None:
        assert grade_check("x", n_defects=0, n_evidence=3).state == CLEAN

    def test_a_defect_is_the_audit_working(self) -> None:
        assert grade_check("x", n_defects=2, n_evidence=0).state == DEFECTIVE

    def test_an_exception_outranks_everything(self) -> None:
        assert grade_check("x", n_defects=0, n_evidence=9, raised=True).state == BROKEN

    def test_an_in_memory_check_is_exempt_but_only_with_a_stated_reason(self) -> None:
        """The narrow exemption. check-registry's subject IS the running program, so consulting
        nothing external is correct -- and grading it blind would start the desk ignoring the one
        alarm that guarantees every other check is registered."""
        name = next(iter(EVALUATES_IN_MEMORY))
        assert grade_check(name, n_defects=0, n_evidence=0).state == CLEAN
        for reason in EVALUATES_IN_MEMORY.values():
            assert len(reason) > 40, "an exemption without a real reason is a silenced alarm"

    def test_the_exemption_list_is_not_a_dumping_ground(self) -> None:
        """The two checks that PROMPTED this list were genuinely blind and were FIXED, not
        exempted. If they ever appear here, the fix has been reverted into a silence."""
        assert "bnb-funded" not in EVALUATES_IN_MEMORY
        assert "fee-carry-ratio" not in EVALUATES_IN_MEMORY
        assert len(EVALUATES_IN_MEMORY) <= 3, (
            "the exemption list is growing -- each entry is an alarm nobody will hear again")


class TestDeletionIsWeakening:
    def test_a_vanished_check_is_a_fall(self) -> None:
        """THE SILENT REGRESSION. Delete a check and its defects stop appearing -- the report gets
        BETTER. Without a roster nothing can tell a fixed defect from a deleted detector."""
        prior = _roster([CheckState("a", 0, 5, state=CLEAN),
                         CheckState("b", 1, 5, state=DEFECTIVE)])
        diff = diff_roster(prior, [CheckState("a", 0, 5, state=CLEAN)])
        assert [r["check"] for r in diff["vanished"]] == ["b"]
        assert unexplained_falls(diff) == ["VANISHED b"]

    def test_a_check_that_goes_blind_is_a_fall(self) -> None:
        """Evaluated real evidence yesterday, read nothing today: its input stopped being produced
        and the law it enforces is unenforced as of this run."""
        prior = _roster([CheckState("a", 0, 5, state=CLEAN)])
        diff = diff_roster(prior, [CheckState("a", 0, 0, state=CANNOT_EVALUATE)])
        assert [r["check"] for r in diff["went_blind"]] == ["a"]
        assert unexplained_falls(diff) == ["WENT-BLIND a (CLEAN -> CANNOT-EVALUATE)"]

    def test_adding_a_check_is_never_a_fall(self) -> None:
        diff = diff_roster(_roster([CheckState("a", 0, 5, state=CLEAN)]),
                           [CheckState("a", 0, 5, state=CLEAN),
                            CheckState("new", 0, 5, state=CLEAN)])
        assert diff["added"] == ["new"] and not unexplained_falls(diff)

    def test_a_named_cause_stops_the_page_but_not_the_record(self) -> None:
        """A fall someone EXPLAINED is not an alarm. It is still on the record, so a cause cannot
        quietly become a way to delete history."""
        prior = _roster([CheckState("a", 0, 5, state=CLEAN), CheckState("b", 0, 5, state=CLEAN)])
        diff = diff_roster(prior, [CheckState("a", 0, 5, state=CLEAN)])
        assert unexplained_falls(diff, {"b": "law repealed 2026-08-05, ledgered"}) == []
        assert diff["vanished"], "the fall must remain recorded even once explained"

    def test_a_blind_check_that_was_already_blind_is_not_a_new_fall(self) -> None:
        """Only a FALL pages. A standing blind spot is reported, not re-alarmed every day, or the
        pager trains the principal to swipe it away."""
        prior = _roster([CheckState("a", 0, 0, state=CANNOT_EVALUATE)])
        diff = diff_roster(prior, [CheckState("a", 0, 0, state=CANNOT_EVALUATE)])
        assert not unexplained_falls(diff)


class TestRepairIsTwiceFenced:
    def test_only_allowlisted_defects_are_repaired(self) -> None:
        allowed, report_only = repairs_for(["survivor-clocks-unrun", "something-nobody-listed"])
        assert [r["defect"] for r in allowed] == ["survivor-clocks-unrun"]
        assert [r["defect"] for r in report_only] == ["something-nobody-listed"]

    def test_every_repair_names_an_organ_and_a_reason(self) -> None:
        allowed, _ = repairs_for(["survivor-clocks-unrun", "survivor-cells-unconverted"])
        for r in allowed:
            assert r["organ"].startswith("scripts/") and len(r["why"]) > 40

    def test_the_never_touch_list_covers_the_standing_constraints(self) -> None:
        low = " ".join(NEVER_AUTO_CORRECT)
        for must in ("run_deadman_switch", "threshold", "leverage", "promote", "delete"):
            assert must in low, f"{must} is not fenced out of auto-repair"

    def test_a_forbidden_defect_is_refused_even_if_someone_allowlists_it(self, monkeypatch) -> None:
        """THE SECOND FENCE. An allowlist entry that ever drifts toward a gate, a size or the
        deadman switch is stopped here rather than trusted upstream -- because the first fence is
        a list a person edits, and this one is a rule."""
        import libs.ops.law_police as LP
        monkeypatch.setitem(LP.AUTO_CORRECTABLE, "loosen-threshold-now",
                            {"organ": "scripts/whatever.py", "why": "x" * 50})
        allowed, report_only = repairs_for(["loosen-threshold-now"])
        assert allowed == []
        assert "REFUSED" in report_only[0]["why"]

    def test_nothing_is_repaired_when_nothing_is_wrong(self) -> None:
        assert repairs_for([]) == ([], [])


class TestTheVerdict:
    def test_a_regression_outranks_a_blind_spot(self) -> None:
        prior = _roster([CheckState("a", 0, 5, state=CLEAN), CheckState("b", 0, 5, state=CLEAN)])
        rep = police([CheckState("a", 0, 0, state=CANNOT_EVALUATE)], prior, [])
        assert rep.verdict == "REGRESSION"

    def test_blind_spots_alone_still_are_not_watching(self) -> None:
        rep = police([CheckState("a", 0, 0, state=CANNOT_EVALUATE)], {}, [])
        assert rep.verdict == "BLIND-SPOTS"

    def test_a_broken_check_is_never_reported_as_watching(self) -> None:
        rep = police([CheckState("a", 0, 5, raised=True, state=BROKEN)], {}, [])
        assert rep.verdict == "BROKEN-CHECKS"

    def test_watching_requires_every_check_to_actually_evaluate(self) -> None:
        rep = police([CheckState("a", 0, 5, state=CLEAN),
                      CheckState("b", 2, 5, state=DEFECTIVE)], {}, [])
        assert rep.verdict == "WATCHING", (
            "a desk with defects is still being WATCHED -- the verdict is about the police, "
            "not about the desk's health")

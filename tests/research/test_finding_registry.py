"""Tests for §35 -- every finding must reach the loop that drives it.

These lock the two properties that decide whether the check is usable at all: it must catch a
finding with no register trace, and it must NOT accuse items it cannot actually evaluate. A check
that flags everything gets ignored, and an ignored check is worse than none because it looks like
coverage."""

from __future__ import annotations

from datetime import date

from libs.research.finding_registry import (
    CoverageRatchet,
    CoverageReport,
    Finding,
    coverage_report,
    is_tracked,
    parse_findings,
    register_health,
    untracked,
    update_coverage_ratchet,
)

_PROSE = """# Review

## Residuals

1. **Counterparty concentration** -- one venue, an FTX-class failure is fatal.
2. **Principal key-person risk** -- one operator owns every human action.

## Already live (duplicates -- do nothing)

3. **Stablecoin monitor** -- shipped, collector is live.
"""

_TABLE = """### RECOMMENDATIONS

| # | action | why | evidence |
| 1 | **CHANGE** `run_ci` -- fix the failing job, add a pre-push hook | gate 0 | ci red |
| 2 | **ADD** `scripts/fix_cookie_reconcile.py` -- diagnose rejection | bleed | logs |
"""


class TestParse:
    def test_prose_findings_extracted(self) -> None:
        f = parse_findings(_PROSE, source="docs/SYSTEM_REVIEW.md")
        assert [x.number for x in f] == [1, 2, 3]
        assert f[0].title.startswith("Counterparty")

    def test_settled_section_is_marked(self) -> None:
        f = {x.number: x for x in parse_findings(_PROSE, source="d")}
        assert f[1].settled is False
        assert f[3].settled is True  # under "Already live (duplicates -- do nothing)"

    def test_table_row_captures_the_whole_cell_not_just_the_verb(self) -> None:
        # capturing only the bolded span yields "CHANGE", which has no distinctive token and made
        # every audit-inbox row look untracked on the first real run
        f = parse_findings(_TABLE, source="docs/research/micro_audit_inbox.md")
        assert len(f) == 2
        assert "run_ci" in f[0].title
        assert f[0].tokens  # non-empty -- judgeable

    def test_unnumbered_prose_is_not_a_finding(self) -> None:
        assert parse_findings("Some **bolded** remark with no number.\n", source="d") == []

    def test_markdown_is_stripped_from_titles(self) -> None:
        f = parse_findings("| 1 | **ADD** `libs/x.py` thing | why |\n", source="d")
        assert "*" not in f[0].title and "`" not in f[0].title


class TestTracking:
    def test_finding_with_a_register_trace_is_tracked(self) -> None:
        f = Finding(source="d", number=1, title="Counterparty concentration")
        assert is_tracked(f, "| 54 | per-venue exposure cap, counterparty ... |")

    def test_finding_with_no_trace_is_untracked(self) -> None:
        f = Finding(source="d", number=1, title="Fee-tier VIP progression modelling")
        assert is_tracked(f, "| 1 | something entirely unrelated |") is False

    def test_tokenless_finding_is_never_accused(self) -> None:
        # unjudgeable -> not reported. Reporting what you cannot evaluate manufactures work.
        assert is_tracked(Finding(source="d", number=1, title="CHANGE"), "") is True

    def test_stopwords_alone_do_not_prove_tracking(self) -> None:
        f = Finding(source="d", number=1, title="Fee-tier progression")
        assert is_tracked(f, "the data risk audit check build run") is False

    def test_settled_findings_are_never_reported(self) -> None:
        f = parse_findings(_PROSE, source="d")
        assert all(x.number != 3 for x in untracked(f, register=""))


class TestCoverage:
    def test_full_coverage_when_everything_is_traced(self) -> None:
        f = parse_findings(_PROSE, source="d")
        reg = "counterparty concentration ... principal key-person risk"
        rep = coverage_report(f, reg)
        assert rep.n_untracked == 0 and rep.coverage == 1.0
        assert "the cycle can see them" in rep.verdict

    def test_partial_coverage_names_the_invisible_ones(self) -> None:
        rep = coverage_report(parse_findings(_PROSE, source="d"), "counterparty only")
        assert rep.n_untracked == 1
        assert any("key-person" in n for n in rep.untracked_names)
        assert "invisible" in rep.verdict

    def test_settled_items_excluded_from_the_denominator(self) -> None:
        rep = coverage_report(parse_findings(_PROSE, source="d"), "")
        assert rep.n_open == 2 and rep.n_settled == 1  # the shipped item is not owed

    def test_no_findings_owes_nothing(self) -> None:
        rep = coverage_report([], "")
        assert rep.coverage == 1.0 and "nothing owed" in rep.verdict


def _rep(open_: int, ut: int) -> CoverageReport:
    return CoverageReport(n_findings=open_, n_settled=0, n_open=open_, n_untracked=ut,
                          coverage=round(1 - ut / open_, 3) if open_ else 1.0,
                          untracked_names=(), verdict="")


class TestCoverageRatchet:
    """The floor only rises -- and the denominator cannot be shrunk to fake it."""

    PRIOR = CoverageRatchet(best_coverage=0.83, max_open_findings=71, max_docs_scanned=5)

    def test_deleting_findings_to_reach_100_is_caught(self) -> None:
        _, v = update_coverage_ratchet(self.PRIOR, _rep(20, 0), n_docs=5)
        assert v.scope_shrank is True and "SCOPE SHRANK" in v.verdict

    def test_dropping_a_doc_from_scope_is_caught(self) -> None:
        _, v = update_coverage_ratchet(self.PRIOR, _rep(71, 0), n_docs=3)
        assert v.scope_shrank is True

    def test_coverage_falling_is_a_regression(self) -> None:
        _, v = update_coverage_ratchet(self.PRIOR, _rep(80, 25), n_docs=5)
        assert v.coverage_regressed is True and "REGRESSED" in v.verdict

    def test_honest_100_percent_sets_the_floor(self) -> None:
        n, v = update_coverage_ratchet(self.PRIOR, _rep(71, 0), n_docs=5)
        assert n.best_coverage == 1.0 and "100%" in v.verdict
        assert v.scope_shrank is False and v.coverage_regressed is False

    def test_a_worse_cycle_never_lowers_the_floor(self) -> None:
        good = CoverageRatchet(best_coverage=1.0, max_open_findings=71, max_docs_scanned=5)
        n, _ = update_coverage_ratchet(good, _rep(71, 30), n_docs=5)
        assert n.best_coverage == 1.0            # record untouched by a bad cycle
        assert n.max_open_findings == 71

    def test_growing_the_scope_counts_as_improvement(self) -> None:
        n, v = update_coverage_ratchet(self.PRIOR, _rep(90, 15), n_docs=6)
        assert v.improved is True                # more findings in scope is progress
        assert n.max_open_findings == 90 and n.max_docs_scanned == 6

    def test_first_run_has_no_floor_to_break(self) -> None:
        _, v = update_coverage_ratchet(CoverageRatchet(), _rep(10, 2), n_docs=2)
        assert v.coverage_regressed is False and v.scope_shrank is False


class TestArtifactGovernance:
    """§36 -- the miner problem cannot reappear because ungoverned artifacts fire on day one."""

    def test_every_docs_artifact_is_claimed(self) -> None:
        # the real repo must stay fully classified; a new artifact with no law is the miner
        # problem waiting to happen, and this is the test that keeps it from landing quietly
        import scripts.max_audit as m
        defects: list[tuple[str, str]] = []
        m.check_artifact_governance(defects)
        assert defects == [], f"ungoverned artifacts: {defects}"

    def test_law_sets_do_not_overlap_incoherently(self) -> None:
        import scripts.max_audit as m
        # an artifact cannot be both a cadenced producer and terminal -- that is a contradiction
        assert not (set(m._PRODUCER_CADENCE) & set(m._TERMINAL_ARTIFACTS))
        # nor both in-scope and excluded for the same law
        assert not (set(m._FINDING_DOCS) & set(m._FINDING_DOCS_EXCLUDED))
        assert not (set(m._DIG_DOCS) & set(m._DIG_DOCS_EXCLUDED))

    def test_every_cadenced_producer_states_a_reason(self) -> None:
        import scripts.max_audit as m
        for rel, (days, why) in m._PRODUCER_CADENCE.items():
            assert days > 0, rel
            assert len(why) > 30, f"{rel} needs a real reason, not a label"


_REG = """# GAP REGISTER

_Reviewed + re-ranked at the START of every daily AI cycle; items stale >7 days MUST be escalated._
_Re-ranked 2026-07-20T09:30Z._

| # | Gap | Why | Trigger / plan | Owner | Added | Status |
|---|-----|-----|----------------|-------|-------|--------|
| 1 | **Live connector** | gates everything | deadline 2026-07-31 | brain | 07-16 | open |
| 2 | **Fill-quality ledger** | cost calibration | after enough trades | brain | 07-16 | open |
| 3 | **Recorder spot leg** | half of every trade | done | brain | 07-19 | closed |
"""


class TestRegisterHealth:
    """§36(3) -- the organ every other law routes into is held to its own stated rules."""

    def test_rows_and_open_count(self) -> None:
        h = register_health(_REG, today=date(2026, 7, 22))
        assert h.n_rows == 3 and h.n_open == 2   # the closed row is not open

    def test_rerank_age_from_the_self_declared_stamp(self) -> None:
        # NOT mtime -- editing the file must not fake a re-rank that never happened
        h = register_health(_REG, today=date(2026, 7, 22))
        assert h.rerank_age_days == 2.0

    def test_drift_is_caught_before_the_escalation_bar(self) -> None:
        h = register_health(_REG, today=date(2026, 7, 24))
        assert h.rerank_stale is True and h.rerank_breach is False

    def test_breach_of_its_own_seven_day_rule(self) -> None:
        h = register_health(_REG, today=date(2026, 8, 1))
        assert h.rerank_breach is True and "escalation bar" in h.verdict

    def test_row_with_a_dated_plan_is_not_parked(self) -> None:
        h = register_health(_REG, today=date(2026, 7, 21))
        assert not any("Live connector" in u for u in h.undated_open)  # carries 2026-07-31

    def test_row_without_a_date_is_parked(self) -> None:
        # took none of the three exits: implement / defer WITH A DEADLINE / retire with reason
        h = register_health(_REG, today=date(2026, 7, 21))
        assert any("Fill-quality ledger" in u for u in h.undated_open)

    def test_unparseable_register_is_loud(self) -> None:
        h = register_health("# GAP REGISTER\n\nnothing here\n", today=date(2026, 7, 25))
        assert h.n_rows == 0 and "drives nothing" in h.verdict

    def test_missing_stamp_does_not_crash(self) -> None:
        h = register_health(_REG.replace("_Re-ranked 2026-07-20T09:30Z._", ""),
                            today=date(2026, 7, 25))
        assert h.rerank_age_days == -1.0 and h.rerank_stale is False

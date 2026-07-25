"""Tests for §35 -- every finding must reach the loop that drives it.

These lock the two properties that decide whether the check is usable at all: it must catch a
finding with no register trace, and it must NOT accuse items it cannot actually evaluate. A check
that flags everything gets ignored, and an ignored check is worse than none because it looks like
coverage."""

from __future__ import annotations

from libs.research.finding_registry import (
    Finding,
    coverage_report,
    is_tracked,
    parse_findings,
    untracked,
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

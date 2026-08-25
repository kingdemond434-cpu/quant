"""A multi-subject card may not read terminal while part of its subject is unopened (R0581).

MEASURED 2026-08-13 and re-measured 2026-08-20: a card can read "verified + MINED" with half its
NAMED subject never opened, and the card grade, the source backlog and the mine gate all read
GREEN. Card 24 named VeighNa/vnpy.alpha AND Qlib; the conversion mined only Qlib paths, so the
unread half went on propagating a claim into the desk's own gap list that opening it REFUTED.
L1.57's denominator problem, aimed at a research card.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from libs.research.source_backlog import SourceCard, _subjects, parse_watchlist

TODAY = date(2026, 8, 20)
WATCHLIST = Path(__file__).resolve().parents[2] / "docs/research/data_axis_watchlist.md"


def _card(grade: str) -> SourceCard:
    return parse_watchlist(f"### 9. A source — grade: {grade}\n", today=TODAY)[0]


class TestMarker:
    def test_undeclared_is_none_not_zero(self) -> None:
        """UNMEASURED, never 'no subjects' and never 'fully covered' (L1.28a)."""
        assert _subjects("verified-clean") == (None, None)

    @pytest.mark.parametrize("txt,exp", [
        ("[subjects: 3/5]", (3, 5)),
        ("[subjects:1/2]", (1, 2)),
        ("[subjects: 10 / 12 ]", (10, 12)),
    ])
    def test_marker_is_read_covered_over_named(self, txt: str, exp: tuple[int, int]) -> None:
        assert _subjects(txt) == exp


class TestCoverageLabel:
    @pytest.mark.parametrize("grade,label", [
        ("verified-clean", "UNDECLARED"),
        ("verified-clean [subjects: 5/5]", "FULL"),
        ("verified-clean [subjects: 3/5]", "PARTIAL"),
        ("verified-clean [subjects: 6/5]", "OVER-DECLARED"),
    ])
    def test_four_states_never_a_bare_boolean(self, grade: str, label: str) -> None:
        assert _card(grade).subject_coverage == label


class TestClassification:
    def test_a_declared_shortfall_outranks_a_s33_conversion(self) -> None:
        """THE defect: `screened -> artifact` closed a card whose other subjects were unopened."""
        assert _card("verified-clean [§33: screened -> data/x.json]").category == "converted"
        assert _card(
            "verified-clean [subjects: 3/5] [§33: screened -> data/x.json]"
        ).category == "verification"

    def test_a_declared_shortfall_outranks_a_terminal_grade(self) -> None:
        assert _card("verified-clean [subjects: 1/2]").category == "verification"

    def test_full_coverage_leaves_the_grade_alone(self) -> None:
        assert _card(
            "verified-clean [subjects: 5/5] [§33: wired -> data/x.json]"
        ).category == "converted"

    def test_over_declared_is_a_measurement_defect_not_a_clean_card(self) -> None:
        """covered > named must not round down to FULL and close the card."""
        assert _card("verified-clean [subjects: 6/5]").category == "verification"

    def test_undeclared_cards_are_completely_unchanged(self) -> None:
        """40 cards are undeclared; a check red on day one gets switched off (L1.43)."""
        for grade, cat in [
            ("verified-clean", "resolved"),
            ("verified-clean [§33: wired -> data/x.json]", "converted"),
            ("needs-legitimacy-review", "legitimacy"),
            ("UNVERIFIED", "verification"),
            ("verified-clean [§33: killed -> docs/graveyard.md x]", "resolved"),
        ]:
            assert _card(grade).category == cat, grade

    def test_a_shortfall_does_not_escape_the_s33_enforcement_population(self) -> None:
        """`resolved` is what DROPS a card from max_audit._mine_items. This must never be it --
        a card claiming an artifact is the last one that should escape the artifact check."""
        assert _card("x [subjects: 1/2] [§33: wired -> data/x.json]").category != "resolved"

    def test_legitimacy_still_outranks_a_shortfall(self) -> None:
        """A §13 hard stop is not downgraded to ordinary verification work."""
        assert _card(
            "needs-legitimacy-review [subjects: 1/2]"
        ).category == "legitimacy"


class TestLiveWatchlist:
    """The three cards annotated 2026-08-20, each verified from the card's OWN prose.

    Selected by NAME, not by card_id: the watchlist carries duplicate ids across renumbering eras
    (22, 23, 24, 26, 29 each appear twice), so an id-keyed lookup silently returns whichever card
    came last -- the first draft of this test asserted against the wrong card 22 and failed.
    """

    @pytest.mark.parametrize("needle,covered,named", [
        ("CFE regulated crypto futures", 3, 5),      # FBT/PBT/XBTF screened; FET/PET not
        ("KR venue-state layer", 1, 2),              # Upbit artifact; Bithumb none
        ("ADGM/FSRA", 1, 2),                         # corpus MINED; register pages UNMINED
    ])
    def test_declared_shortfalls_are_in_the_work_queue(
            self, needle: str, covered: int, named: int) -> None:
        cards = [c for c in parse_watchlist(WATCHLIST.read_text("utf-8"), today=TODAY)
                 if needle in c.name]
        assert len(cards) == 1, f"{needle!r} matched {len(cards)} cards"
        c = cards[0]
        assert (c.subjects_covered, c.subjects_named) == (covered, named)
        assert c.subject_coverage == "PARTIAL"
        assert c.category == "verification", "a PARTIAL card must not read terminal"

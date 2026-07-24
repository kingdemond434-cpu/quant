"""Tests for the source-verification backlog picker (clears the catalogue, never generates more)."""

from __future__ import annotations

from libs.research.source_backlog import (
    SourceCard,
    next_pending,
    parse_watchlist,
)

_SAMPLE = """# Watchlist

### 1. Upbit Historical Market Data portal — grade: needs-monitoring
### 2. OKX official historical-data portal — grade: verified-clean
### 4. Bithumb (spot + futures) — grade: UNVERIFIED
### 5. Coincheck — grade: destroyed-at-source (for this session)
### 6. Tardis — grade: needs-monitoring (forward) / destroyed-at-source (backfill)
### 20. Baidu Index — grade: needs-legitimacy-review
### 21. NAVER DataLab (Korean search-attention) — grade: needs-monitoring (built, unrun)
"""


class TestParseWatchlist:
    def test_extracts_every_card(self) -> None:
        cards = parse_watchlist(_SAMPLE)
        assert len(cards) == 7
        assert {c.card_id for c in cards} == {1, 2, 4, 5, 6, 20, 21}

    def test_classifies_resolved(self) -> None:
        cards = parse_watchlist(_SAMPLE)
        by_id = {c.card_id: c for c in cards}
        assert by_id[2].category == "resolved"  # bare verified-clean
        assert by_id[5].category == "resolved"  # bare destroyed-at-source

    def test_classifies_verification_pending(self) -> None:
        cards = parse_watchlist(_SAMPLE)
        by_id = {c.card_id: c for c in cards}
        assert by_id[1].category == "verification"  # needs-monitoring
        assert by_id[4].category == "verification"  # UNVERIFIED

    def test_compound_grade_stays_pending(self) -> None:
        # "needs-monitoring (forward) / destroyed-at-source (backfill)" has a NON-terminal
        # component -- the whole card must stay pending, not be silently closed out.
        cards = parse_watchlist(_SAMPLE)
        by_id = {c.card_id: c for c in cards}
        assert by_id[6].category == "verification"

    def test_classifies_legitimacy_pending(self) -> None:
        cards = parse_watchlist(_SAMPLE)
        by_id = {c.card_id: c for c in cards}
        assert by_id[20].category == "legitimacy"

    def test_unrecognized_grade_fails_open_to_pending(self) -> None:
        cards = parse_watchlist("### 99. Something — grade: mystery-status\n")
        assert cards[0].category == "verification"


class TestNextPending:
    def test_resolved_excluded_from_every_queue(self) -> None:
        cards = parse_watchlist(_SAMPLE)
        rep = next_pending(cards)
        assert "OKX official historical-data portal" not in rep.next_verification
        assert "Coincheck" not in rep.next_verification
        assert rep.n_resolved == 2

    def test_needs_monitoring_before_bare_unverified(self) -> None:
        cards = [
            SourceCard(card_id=1, name="A", grade_raw="UNVERIFIED", category="verification"),
            SourceCard(card_id=2, name="B", grade_raw="needs-monitoring", category="verification"),
        ]
        rep = next_pending(cards, limit=5)
        assert rep.next_verification[0] == "B"  # cheaper-to-finish goes first

    def test_oldest_card_id_first_within_same_rank(self) -> None:
        cards = [
            SourceCard(card_id=5, name="newer", grade_raw="UNVERIFIED", category="verification"),
            SourceCard(card_id=1, name="older", grade_raw="UNVERIFIED", category="verification"),
        ]
        rep = next_pending(cards, limit=5)
        assert rep.next_verification[0] == "older"

    def test_legitimacy_kept_separate_from_verification(self) -> None:
        cards = parse_watchlist(_SAMPLE)
        rep = next_pending(cards, limit=5)
        assert "Baidu Index" in rep.next_legitimacy
        assert "Baidu Index" not in rep.next_verification

    def test_limit_caps_batch(self) -> None:
        cards = [
            SourceCard(card_id=i, name=f"s{i}", grade_raw="UNVERIFIED", category="verification")
            for i in range(10)
        ]
        rep = next_pending(cards, limit=3)
        assert len(rep.next_verification) == 3
        assert rep.n_verification_pending == 10

    def test_empty_backlog_clear_verdict(self) -> None:
        cards = [SourceCard(card_id=1, name="X", grade_raw="verified-clean", category="resolved")]
        rep = next_pending(cards)
        assert "backlog clear" in rep.verdict

    def test_no_cards(self) -> None:
        rep = next_pending([])
        assert rep.n_total == 0
        assert "backlog clear" in rep.verdict

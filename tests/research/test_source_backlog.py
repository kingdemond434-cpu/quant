"""Tests for the source-verification backlog picker (clears the catalogue, never generates more)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from libs.research.source_backlog import (
    SourceCard,
    backlog_from_file,
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


# ---------------------------------------------------------------------------------------------
# F0002: the verify-queue must offer only what a miner can actually do THIS cycle.
#
# Raised 2026-07-28 by the CN frontier miner, accepted, and measured: three sessions (07-26 CN,
# 07-26 EN-C, 07-28 CN) each re-derived by hand that the same cards were not workable. On the
# live watchlist this cut the offered queue from 15 items to 5 without losing a single card --
# 4 were terminally killed, 11 carry a dated deferral and are reported with their return date.
# ---------------------------------------------------------------------------------------------

_S33 = """# Watchlist

### 30. EODHD.com — grade: KILLED as a purchase [§33: killed -> docs/graveyard.md `eodhd`]
### 31. Regulatory-event timeline — grade: needs-monitoring [§33: deferred(2026-08-24) tier:3]
### 32. NAVER DataLab — grade: needs-legitimacy-review [§33: deferred(2026-08-09) tier:3]
### 33. Live axis — grade: UNVERIFIED
### 34. Hourly — grade: needs-monitoring (sibling graveyard-KILLED) [§33: deferred(2026-08-24)]
"""

_TODAY = date(2026, 8, 12)


class TestNonActionableCardsAreNotOfferedAsThisCycle:
    def test_a_terminally_killed_card_is_resolved_not_pending(self) -> None:
        """The fail-open `return "verification"` was offering killed cards forever: a §33 kill
        matches none of the recognised grade substrings, so it fell through to pending."""
        card = next(c for c in parse_watchlist(_S33, today=_TODAY) if c.card_id == 30)
        assert card.category == "resolved"

    def test_the_word_killed_in_PROSE_never_resolves_a_live_card(self) -> None:
        """THE TRAP THIS AVOIDS. Card 34's grade contains 'graveyard-KILLED' describing a
        SIBLING rung while the card itself has a screen owed. Substring-matching the word would
        silently close a card with real work -- only the §33 MARKER counts."""
        card = next(c for c in parse_watchlist(_S33, today=_TODAY) if c.card_id == 34)
        assert card.category == "deferred", "resolved by prose, not by disposition"
        assert card.deferred_until == date(2026, 8, 24)

    def test_a_FUTURE_deferral_is_withheld_and_NAMED_with_its_return_date(self) -> None:
        rep = next_pending(parse_watchlist(_S33, today=_TODAY))
        assert "Regulatory-event timeline" not in " ".join(rep.next_verification)
        # 31 and 34 only: NAVER (32) was deferred to 08-09, which has already passed on _TODAY,
        # so it is correctly back in the legitimacy queue rather than withheld.
        assert rep.n_deferred == 2
        # Withheld is not hidden: the card and its date are published, soonest first.
        assert rep.deferred[0][1] == "2026-08-24"
        assert "deferred (next returns 2026-08-24)" in rep.verdict

    def test_a_PAST_deferral_returns_to_the_queue_ON_ITS_OWN(self) -> None:
        """THE RE-ENTRY CONDITION, and the half that matters most.

        NAVER was deferred to 2026-08-09. An exclusion with no path back is how a card gets
        dropped forever -- 'ask of any exclusion: what is the path back?'. The date IS the path,
        so the same input classified on a later day must be workable again with no edit.
        """
        before = next(c for c in parse_watchlist(_S33, today=date(2026, 8, 1)) if c.card_id == 32)
        after = next(c for c in parse_watchlist(_S33, today=_TODAY) if c.card_id == 32)
        assert before.category == "deferred"
        assert after.category == "legitimacy", "the deferral expired and nothing re-admitted it"

    def test_a_deferral_dated_TODAY_is_workable_today(self) -> None:
        """Boundary: `deferred(2026-08-24)` means blocked UNTIL the 24th, workable ON it."""
        card = next(c for c in parse_watchlist(_S33, today=date(2026, 8, 24)) if c.card_id == 31)
        assert card.category == "verification"

    def test_a_malformed_date_leaves_the_card_workable(self) -> None:
        """Fail OPEN on debris: an unparseable date must never become an indefinite block."""
        bad = "### 40. X — grade: UNVERIFIED [§33: deferred(2026-13-99) tier:2]\n"
        card = parse_watchlist(bad, today=_TODAY)[0]
        assert card.category == "verification"
        assert card.deferred_until is None

    def test_the_live_watchlist_offers_only_workable_cards(self) -> None:
        """The standing invariant, on the real file the miners read."""
        rep = backlog_from_file(Path("docs/research/data_axis_watchlist.md"))
        offered = set(rep.next_verification) | set(rep.next_legitimacy)
        deferred_names = {n for n, _ in rep.deferred}
        assert not (offered & deferred_names), "a deferred card is also being offered"
        assert rep.n_total == (rep.n_resolved + rep.n_verification_pending
                               + rep.n_legitimacy_pending + rep.n_deferred), "cards lost"

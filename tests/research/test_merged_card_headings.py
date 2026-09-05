"""A merged watchlist card must stay in the denominator (L1.60).

`### 13<en dash>14.` uses an EN DASH (U+2013). Both card parsers required `(\\d+)\\.`, so the
heading matched neither, emitted no row, and was never IN the population any fence iterates.
Its absence and its non-existence were byte-identical to every reader -- the silent-attrition
shape, arriving through a regex rather than through an `except: continue`.
"""
from __future__ import annotations

import pytest

from libs.research.mine_conversion import _ITEM_RE
from libs.research.source_backlog import _CARD_RE, parse_watchlist

# The real heading, verbatim from docs/research/data_axis_watchlist.md:938.
MERGED = ("### 13\u201314. Community data lakes (Kaggle btcusdt, HuggingFace sebdg/crypto_data) "
          "— grade: UNVERIFIED")
PLAIN = "### 24. Foreign AI-quant RESEARCH SYSTEMS (Qlib) — grade: verified-clean + MINED"


class TestMergedHeadings:
    def test_the_en_dash_card_is_parsed_at_all(self) -> None:
        assert _CARD_RE.match(MERGED) is not None
        assert _ITEM_RE.match(MERGED) is not None

    def test_the_id_is_the_first_number_in_the_range(self) -> None:
        assert _CARD_RE.match(MERGED).group(1) == "13"          # type: ignore[union-attr]
        assert _ITEM_RE.match(MERGED).group("cid") == "13"      # type: ignore[union-attr]

    @pytest.mark.parametrize("dash", ["\u2013", "\u2014", "-"])
    def test_every_dash_a_writer_may_type(self, dash: str) -> None:
        head = f"### 13{dash}14. Community data lakes — grade: UNVERIFIED"
        assert _CARD_RE.match(head) is not None

    def test_the_range_is_not_swallowed_into_the_name(self) -> None:
        """The name must start at the title, not at a leftover '14.'."""
        assert _CARD_RE.match(MERGED).group(2).startswith("Community")   # type: ignore[union-attr]

    def test_plain_cards_are_unchanged(self) -> None:
        m = _CARD_RE.match(PLAIN)
        assert m is not None and m.group(1) == "24"
        assert _ITEM_RE.match(PLAIN).group("cid") == "24"        # type: ignore[union-attr]

    def test_a_merged_card_reaches_the_backlog_with_its_grade(self) -> None:
        cards = parse_watchlist(MERGED + "\n\nbody text\n")
        assert [c.card_id for c in cards] == [13]
        assert cards[0].category != "resolved", "UNVERIFIED must not read as done"

    def test_the_live_watchlist_no_longer_drops_it(self) -> None:
        from pathlib import Path
        doc = Path(__file__).resolve().parents[2] / "docs/research/data_axis_watchlist.md"
        ids = {c.card_id for c in parse_watchlist(doc.read_text("utf-8"))}
        assert 13 in ids, "card 13-14 is still invisible to the source backlog"

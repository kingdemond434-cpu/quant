"""Regression tests for the dated central-bank document collector.

Written in the same change as the fix (LAWS §5, promotion rule 13). Each test names the
specific defect it would have caught in the pre-2026-08-26 implementation.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parents[1] / "desks/mt5/side_channels/central_bank_miner.py"


@pytest.fixture(scope="module")
def miner():  # type: ignore[no-untyped-def]
    spec = importlib.util.spec_from_file_location("_cb_miner_under_test", _SRC)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


_RSS = """<rss><channel>
<item>
  <title><![CDATA[FOMC statement &#39;on&#39; policy]]></title>
  <link><![CDATA[https://example.invalid/a.htm]]></link>
  <description><![CDATA[The Committee decided to hold; forward guidance unchanged.]]></description>
  <pubDate><![CDATA[Tue, 25 Aug 2026 18:00:00 GMT]]></pubDate>
</item>
<item>
  <title>Undated notice</title>
  <link>https://example.invalid/b.htm</link>
</item>
</channel></rss>"""

_RDF = """<rdf:RDF xmlns:dc="http://purl.org/dc/elements/1.1/">
<item rdf:about="https://example.invalid/s.htm">
  <title>Governor: outlook</title>
  <link>https://example.invalid/s.htm</link>
  <dc:date>2026-08-17T08:22:00Z</dc:date>
</item></rdf:RDF>"""


def test_every_emitted_row_is_dated(miner) -> None:  # type: ignore[no-untyped-def]
    """THE ORIGINAL DEFECT: the old miner emitted no timestamp at all, so nothing it produced
    could ever become an event series -- the reason `event_reaction`/`macro_conditional`
    stayed absent while this miner logged 20+ rows a fortnight."""
    rows = miner.parse_feed(_RSS, "Fed", "USD", "u")
    assert rows, "a dated item must survive parsing"
    assert all(r["published_utc"] for r in rows)


def test_undated_item_is_dropped_not_stamped_with_now(miner) -> None:  # type: ignore[no-untyped-def]
    """L1.46 clock provenance: a collection time must never stand in for a publication time."""
    rows = miner.parse_feed(_RSS, "Fed", "USD", "u")
    assert [r["title"] for r in rows] == ["FOMC statement 'on' policy"]


def test_rdf_dc_date_feeds_parse(miner) -> None:  # type: ignore[no-untyped-def]
    """BIS publishes RDF with dc:date, not RSS pubDate; a pubDate-only reader silently
    returns zero rows -- absence read as a clean verdict (WS-005)."""
    rows = miner.parse_feed(_RDF, "BIS", "XXX", "u")
    assert len(rows) == 1
    assert rows[0]["published_utc"].startswith("2026-08-17T08:22")


def test_instruments_derive_from_currency_never_from_substring(miner) -> None:  # type: ignore[no-untyped-def]
    """THE SECOND ORIGINAL DEFECT: instruments were found by substring-matching tickers against
    the page text. "EURUSD" never appears on federalreserve.gov, so the old code returned []
    every run and fell back to f"{currency}USD" -- emitting "USDUSD" for the Fed."""
    rows = miner.parse_feed(_RSS, "Fed", "USD", "u")
    inst = rows[0]["instruments"]
    assert "EURUSD" in inst and "XAUUSD" in inst
    assert "USDUSD" not in inst
    assert all(len(s) >= 6 for s in inst)


def test_html_entities_are_unescaped(miner) -> None:  # type: ignore[no-untyped-def]
    rows = miner.parse_feed(_RSS, "Fed", "USD", "u")
    assert "&#39;" not in rows[0]["title"]


def test_policy_signals_read_the_description_too(miner) -> None:  # type: ignore[no-untyped-def]
    rows = miner.parse_feed(_RSS, "Fed", "USD", "u")
    assert "forward guidance" in rows[0]["policy_signals"]


def test_seeded_feeds_are_a_seed_not_a_boundary(miner) -> None:  # type: ignore[no-untyped-def]
    """LAWS §1 anti-hardcode: adding a bank must be adding a row, never editing logic."""
    assert set(miner.FEEDS) >= {"Fed", "ECB", "BoJ", "BoE", "BoC", "BIS"}
    for info in miner.FEEDS.values():
        assert info["url"].startswith("https://") and info["currency"]

"""quant-mind's citation rule on the hunter: an unquoted claim is the model's, not the source's."""
from __future__ import annotations

import json

from libs.research import grounding as G
from libs.research.public_strategy_hunter import Source, extraction_prompt, run

PAGE = ("Our gold strategy buys XAUUSD at the Tokyo open when the overnight range is narrow.\n"
        "Backtested 2015-2024 it returned 18% a year after   costs.")


def test_quotes_verify_through_whitespace_case_and_typography():
    assert G.verify(PAGE, "BUYS xauusd at the Tokyo open")
    assert G.verify(PAGE, "returned 18% a year after costs")
    assert not G.verify(PAGE, "audited by a broker statement")
    assert not G.verify(PAGE, "gold")                              # too short to mean anything


def test_ground_and_cap():
    ext = {"mechanism": "Tokyo open range", "evidence_class": "LIVE_BROKER_EXCHANGE",
           "performance_claim": "18% a year",
           "evidence_quotes": {"mechanism": "buys XAUUSD at the Tokyo open",
                               "evidence_class": ["a live broker statement shows"]}}
    g = G.ground(ext, PAGE)
    assert g["state"] == "PARTIAL" and g["grounded_fields"] == ["mechanism"]
    assert set(g["ungrounded_fields"]) == {"evidence_class", "performance_claim"}
    assert G.capped_tier(4, g) == 0 and G.capped_tier(-1, g) == -1
    ext["evidence_quotes"]["performance_claim"] = "returned 18% a year"
    assert G.capped_tier(2, G.ground(ext, PAGE)) == 2
    assert G.ground({"mechanism": "x"}, PAGE)["state"] == "NO_QUOTES"
    assert G.ground({}, PAGE)["state"] == "NO_CLAIMS"


def test_tiles_cover_every_character_once():
    text = ("word " * 9000).strip()
    spans = G.tiles(text, 1000)
    assert spans[0][0] == 0 and spans[-1][1] == len(text)
    assert all(a[1] == b[0] for a, b in zip(spans, spans[1:], strict=False))


def test_the_hunter_asks_for_quotes_and_caps_an_unquoted_tier():
    assert "evidence_quotes" in extraction_prompt({"url": "u"}, PAGE, ["PUBLIC_STRATEGY"])
    source = Source("site", "https://example.test/feed", "site")
    feed = (b"<rss><channel><item><title>Gold at the Tokyo open</title>"
            b"<link>https://example.test/a</link><description>" + PAGE.encode()
            + b"</description></item></channel></rss>")

    def ask(prompt: str) -> str:
        return json.dumps({"mechanism": "Tokyo open range", "evidence_class": "BACKTEST",
                           "evidence_quotes": {"mechanism": "buys XAUUSD at the Tokyo open"}})

    out = run([source], {}, ask, getter=lambda url: feed)
    item = out["items"][0]
    assert item["status"] == "EXTRACTED"
    assert item["grounding"]["grounded_fields"] == ["mechanism"]
    assert item["evidence_tier"] == 0                  # BACKTEST, but nothing quoted says so


def test_a_long_source_is_read_in_tiles_and_merged():
    long_page = ("filler text " * 6000) + PAGE + (" more filler" * 6000)
    source = Source("site", "https://example.test/feed", "site")
    feed = (b"<rss><channel><item><title>Long</title><link>https://example.test/b</link>"
            b"<description>" + long_page.encode() + b"</description></item></channel></rss>")
    seen: list[str] = []

    def ask(prompt: str) -> str:
        seen.append(prompt)
        if "Tokyo open" in prompt:
            return json.dumps({"mechanism": "Tokyo open range", "evidence_quotes":
                               {"mechanism": "buys XAUUSD at the Tokyo open"}})
        return json.dumps({"mechanism": None, "horizon": "intraday"})

    item = run([source], {}, ask, getter=lambda url: feed)["items"][0]
    assert len(seen) >= 2 and item["content_chars_read"] == item["content_chars"]
    assert item["mechanism"] == "Tokyo open range" and item["horizon"] == "intraday"
    assert item["grounding"]["grounded_fields"] == ["mechanism"]

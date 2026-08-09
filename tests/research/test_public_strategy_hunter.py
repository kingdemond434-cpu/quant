from __future__ import annotations

import json

import pytest

from libs.research.public_strategy_hunter import (
    Source,
    discover,
    evidence_tier,
    feed_items,
    load_sources,
    missions,
    parse_extraction,
    run,
    youtube_channel_id,
    youtube_transcript,
)

FEED = b"""<feed xmlns="http://www.w3.org/2005/Atom" xmlns:yt="http://www.youtube.com/xml/schemas/2015">
<entry><yt:videoId>abc</yt:videoId><title>How I made 200% systematically</title>
<published>2026-08-08T00:00:00Z</published></entry></feed>"""


def test_youtube_discovery_resolves_handle_and_feed() -> None:
    def getter(url: str) -> bytes:
        return b'{"channelId":"UC123"}' if "@" in url else FEED

    rows = discover(Source("channel", "https://www.youtube.com/@channel", "youtube"), getter)
    assert rows[0]["url"] == "https://www.youtube.com/watch?v=abc"
    assert "EXTREME_RETURN" in missions(rows[0])
    assert youtube_channel_id(b"nothing") is None
    with pytest.raises(ValueError):
        discover(Source("bad", "https://www.youtube.com/@bad", "youtube"), lambda _: b"no id")


def test_feed_and_caption_states_never_upgrade_missing_text() -> None:
    rows = feed_items(FEED, source=Source("x", "u", "atom"))
    assert len(rows) == 1
    assert youtube_transcript(b"no captions")["transcript_state"] == "UNAVAILABLE"
    caption = (
        b'{"captionTracks":[{"languageCode":"en","baseUrl":"https://captions"}],"audioTracks":[]}'
    )
    got = youtube_transcript(
        caption, lambda _: b"<transcript><text>" + b"word " * 300 + b"</text></transcript>"
    )
    assert got["transcript_state"] == "FULL"


def test_extraction_parser_accepts_json_fence_and_rejects_prose() -> None:
    assert parse_extraction('```json\n{"mechanism":"carry"}\n```') == {"mechanism": "carry"}
    assert parse_extraction("trust me") is None


def test_one_hunter_runs_three_missions_and_deduplicates_state() -> None:
    source = Source("channel", "https://www.youtube.com/@channel", "youtube")

    def getter(url: str) -> bytes:
        if "@channel" in url:
            return b'{"channelId":"UC123"}'
        if "feeds" in url:
            return FEED
        return b"no caption tracks"

    def ask(prompt: str) -> str:
        assert "DESCRIPTION_ONLY" not in prompt  # transcript attempt state is explicit
        return json.dumps({"mechanism": "forced liquidation rebound", "evidence_class": "BACKTEST"})

    first = run([source], {}, ask, getter=getter)
    assert len(first["items"]) == 1
    assert set(first["items"][0]["missions"]) == {
        "VIDEO_TRANSCRIPT",
        "PUBLIC_STRATEGY",
        "EXTREME_RETURN",
    }
    assert first["items"][0]["transcript_state"] == "UNAVAILABLE"
    assert first["k_miner_replaced"] is False
    second = run([source], first["state"], ask, getter=getter)
    assert second["items"] == []


def test_source_failure_is_recorded_and_does_not_abort_other_sources() -> None:
    def getter(url: str) -> bytes:
        if "bad" in url:
            raise OSError("blocked")
        return b"<feed/>"

    report = run(
        [Source("bad", "https://bad", "atom"), Source("ok", "https://ok", "atom")],
        {},
        lambda _: "{}",
        getter=getter,
    )
    assert report["failures"][0]["source"] == "bad"


def test_evidence_tiers_and_discovered_sources_become_next_sweep_inputs(tmp_path) -> None:
    registry = tmp_path / "sources.json"
    registry.write_text(
        json.dumps(
            {
                "sources": [
                    {
                        "name": "seed",
                        "url": "https://seed.example",
                        "kind": "site",
                        "language": "zh",
                        "surface": "forum",
                    }
                ]
            }
        ),
        "utf-8",
    )
    sources = load_sources(
        registry,
        ["https://new.example/research", "javascript:bad", "https://seed.example"],
    )
    assert [source.url for source in sources] == [
        "https://seed.example",
        "https://new.example/research",
    ]
    assert sources[0].language == "zh"
    assert sources[1].surface == "discovered"
    assert evidence_tier("audited") == 6
    assert evidence_tier("5000% screenshot") == -1


def test_reputation_and_emergence_use_independent_sources_not_follower_count() -> None:
    sources = [
        Source("tiny-zh", "https://a.example", "site", "zh", "forum"),
        Source("tiny-ru", "https://b.example", "site", "ru", "repository"),
    ]

    def ask(_prompt: str) -> str:
        return json.dumps(
            {
                "mechanism": "liquidity-state transition",
                "evidence_class": "BACKTEST",
                "reproducible": True,
            }
        )

    report = run(sources, {}, ask, getter=lambda url: url.encode())
    assert report["emergence_watch"][0]["source_count"] == 2
    assert report["source_reputation"]["tiny-zh"]["reproducible"] == 1
    assert set(report["source_coverage"]["languages"]) == {"ru", "zh"}

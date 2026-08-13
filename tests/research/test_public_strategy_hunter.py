from __future__ import annotations

import json
import urllib.error

import pytest

from libs.research.public_strategy_hunter import (
    TRANSCRIPT_BLOCKED,
    TRANSCRIPT_UNKNOWN_STATES,
    TRANSCRIPT_UNREADABLE,
    Source,
    discover,
    evidence_tier,
    extraction_prompt,
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


class TestR0466RefusalIsNotAbsence:
    """R0466 / OP-052. A caption endpoint answering 403 and a video with no captions both
    returned ``transcript_state: UNAVAILABLE``, and ``extraction_prompt`` reads that field and
    nothing else -- so at the one place the state is consumed, a ground the desk is BLOCKED FROM
    was byte-identical to a ground with nothing on it (WS-005 / L1.28a).
    """

    CAPTIONED = (b'{"captionTracks":[{"languageCode":"en","baseUrl":"https://captions"}],'
                 b'"audioTracks":[]}')

    def _refuse(self, code: int):
        def getter(url: str) -> bytes:
            raise urllib.error.HTTPError(url, code, "Forbidden", {}, None)  # type: ignore[arg-type]
        return getter

    def test_a_403_on_the_caption_track_is_not_the_same_value_as_no_captions(self) -> None:
        absent = youtube_transcript(b"a page with no caption tracks at all")
        walled = youtube_transcript(self.CAPTIONED, self._refuse(403))
        assert absent["transcript_state"] == "UNAVAILABLE"
        assert walled["transcript_state"] != absent["transcript_state"], (
            "a wall and an empty ground are the same value again")
        assert walled["transcript_state"] == TRANSCRIPT_BLOCKED
        assert walled["http_status"] == 403

    def test_the_status_survives_because_403_and_429_need_different_next_moves(self) -> None:
        # 403 = a curated denylist, run the OP-052 UA matrix. 429 = pace, come back later.
        # "blocked" alone cannot tell a reader which, so the code is carried, not just a flag.
        assert youtube_transcript(self.CAPTIONED, self._refuse(429))["http_status"] == 429
        assert youtube_transcript(self.CAPTIONED, self._refuse(503))["http_status"] == 503

    def test_a_timeout_is_blocked_not_absent(self) -> None:
        def getter(url: str) -> bytes:
            raise TimeoutError("read timed out")
        got = youtube_transcript(self.CAPTIONED, getter)
        assert got["transcript_state"] == TRANSCRIPT_BLOCKED
        assert got["http_status"] is None       # no venue said anything; do not invent a code

    def test_an_antibot_page_served_with_200_is_unreadable_not_absent(self) -> None:
        # OP-068's third false-null class: a 200 carrying a challenge page. We were served
        # something and it was not captions -- which is not "this video has no captions".
        got = youtube_transcript(self.CAPTIONED, lambda _: b"<html>Access denied</html>")
        assert got["transcript_state"] == TRANSCRIPT_UNREADABLE
        assert got["transcript_state"] in TRANSCRIPT_UNKNOWN_STATES

    def test_a_genuinely_empty_caption_body_is_still_not_called_blocked(self) -> None:
        # The other half, and the one that keeps this honest: making every thin answer a wall
        # destroys the same distinction from the opposite side.
        got = youtube_transcript(self.CAPTIONED, lambda _: b"<transcript></transcript>")
        assert got["transcript_state"] == "PARTIAL"
        assert got["transcript_state"] not in TRANSCRIPT_UNKNOWN_STATES

    def test_the_run_loop_does_not_flatten_a_blocked_watch_page(self) -> None:
        """THE CALLER HALF. Hardening the helper alone fixes nothing if run()'s handler still
        collapses everything to UNAVAILABLE -- the L1.60 invisible-attrition shape."""
        def getter(url: str) -> bytes:
            if "@channel" in url:
                return b'{"channelId":"UC123"}'
            if "feeds" in url:
                return FEED
            raise urllib.error.HTTPError(url, 403, "Forbidden", {}, None)  # type: ignore[arg-type]

        report = run([Source("channel", "https://www.youtube.com/@channel", "youtube")], {},
                     lambda _: json.dumps({"mechanism": "m", "evidence_class": "BACKTEST"}),
                     getter=getter)
        item = report["items"][0]
        assert item["transcript_state"] == TRANSCRIPT_BLOCKED, (
            "run() is still recording a refused watch page as a video without captions")
        assert item["http_status"] == 403

    def test_the_extraction_prompt_shows_the_model_that_it_was_blocked(self) -> None:
        # extraction_prompt reads transcript_state and nothing else, so this is the ONLY place
        # the distinction can actually reach a consumer. If it prints UNAVAILABLE for a wall,
        # every fix above is cosmetic.
        walled = youtube_transcript(self.CAPTIONED, self._refuse(403))
        prompt = extraction_prompt({"url": "u", "title": "t", **walled}, "", ["PUBLIC_STRATEGY"])
        assert f"TRANSCRIPT_STATE: {TRANSCRIPT_BLOCKED}" in prompt

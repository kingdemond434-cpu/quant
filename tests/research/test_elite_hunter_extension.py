from __future__ import annotations

import json

from libs.research.public_strategy_hunter import Source, discover, missions, run


def test_research_site_changes_are_content_deduped_and_reprocessed() -> None:
    source = Source("Flashbots Research", "https://research", "site")
    payload = {"body": b"<html>MEV research paper A</html>"}

    def getter(_url: str) -> bytes:
        return payload["body"]

    def ask(_prompt: str) -> str:
        return json.dumps({"mechanism": "builder auction congestion", "evidence_class": "PAPER"})

    first = run([source], {}, ask, getter=getter)
    assert len(first["items"]) == 1
    assert "ELITE_EXTERNAL_INTELLIGENCE" in first["items"][0]["missions"]
    assert first["items"][0]["content_hash"]
    assert run([source], first["state"], ask, getter=getter)["items"] == []
    payload["body"] = b"<html>MEV research paper B</html>"
    changed = run([source], first["state"], ask, getter=getter)
    assert len(changed["items"]) == 1


def test_youtube_strategy_keeps_original_three_missions() -> None:
    item = {
        "url": "https://youtube.com/watch?v=x",
        "source_kind": "youtube",
        "title": "systematic research 200%",
        "description": "quant paper",
    }
    assert set(missions(item)) == {"VIDEO_TRANSCRIPT", "PUBLIC_STRATEGY", "EXTREME_RETURN"}


def test_generic_site_content_is_actual_public_text_not_a_byte_count() -> None:
    row = discover(
        Source("Lab", "https://lab", "site"),
        lambda _url: b"<html><h1>Portable order book states</h1></html>",
    )[0]
    assert row["description"] == "Portable order book states"
    assert row["source_kind"] == "site"

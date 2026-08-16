from __future__ import annotations

import json
from pathlib import Path

from libs.research.public_strategy_hunter import Source, discover, extraction_prompt, missions, run


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


def test_named_x_depth_floor_is_registered_and_reaches_midnight() -> None:
    registry = json.loads(Path("docs/research/GPT_HUNTER_SOURCES.json").read_text("utf-8"))
    x_names = {
        str(row.get("name", "")).casefold()
        for row in registry["sources"]
        if row.get("surface") == "x"
    }
    assert {"l1vsun", "shmidtqq", "antpalkin"} <= x_names
    assert "cvxv666" not in x_names

    mandate = Path("docs/research/ELITE_QUANT_INTELLIGENCE_MANDATE.md").read_text("utf-8")
    midnight = Path("ops/midnight_codex_prompt.txt").read_text("utf-8")
    for handle in ("@L1vsun", "@shmidtqq", "@antpalkin"):
        assert handle in mandate
        assert handle in midnight
    assert "BLOCKED access is never a clean null" in midnight
    assert "existing hypothesis/conversion pipeline" in midnight


def test_named_x_floor_is_recursive_extractive_and_implementation_bound() -> None:
    mandate = Path("docs/research/ELITE_QUANT_INTELLIGENCE_MANDATE.md").read_text("utf-8")
    midnight = Path("ops/midnight_codex_prompt.txt").read_text("utf-8")
    for required in (
        "NAMED-SEED MAXIMUM-DEPTH / MAXIMUM-ROI LAW",
        "artifact-exhaustive",
        "papers and appendices",
        "repositories and forks",
        "failures and negative results",
        "test -> implementation -> consumer -> measured-effect",
        "E[log W] uplift",
    ):
        assert required in mandate
    for required in (
        "outbound citations",
        "papers/appendices",
        "repos/forks/notebooks",
        "validation/falsification",
        "immediately IMPLEMENT and TEST",
        "E[log W] uplift / total conversion cost",
        "Surface summaries and passive reading lists fail",
    ):
        assert required in midnight


def test_creator_extraction_mines_research_system_not_only_strategy_claim() -> None:
    prompt = extraction_prompt(
        {"url": "https://x.com/L1vsun", "title": "creator", "source_kind": "x"},
        "public creator material",
        ["PUBLIC_STRATEGY", "ELITE_EXTERNAL_INTELLIGENCE"],
    )
    for field in (
        "research_system",
        "discovery_process",
        "testing_process",
        "data_pipeline",
        "superior_capabilities",
        "measurable_gap",
        "replication_plan",
    ):
        assert field in prompt
    assert "external threshold never becomes an internal gate" in prompt

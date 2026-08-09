from __future__ import annotations

import json
from pathlib import Path

import scripts.run_external_intelligence as runner


def test_external_items_enter_existing_hypothesis_queue_once(
    tmp_path: Path, monkeypatch
) -> None:
    data = tmp_path / "data" / "intelligence"
    data.mkdir(parents=True)
    item = {
        "status": "EXTRACTED",
        "url": "https://paper",
        "source": "lab",
        "title": "State first",
        "mechanism": "liquidity state conditions order-flow response",
        "signal": "state-conditioned OFI",
        "data": "public LOB",
        "validation": "leave-one-asset-out",
        "falsifier": "no held-out improvement",
        "evidence_class": "PAPER",
    }
    (data / "public_strategy_items.json").write_text(
        json.dumps({"items": [item]}), "utf-8"
    )
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    monkeypatch.setattr(runner, "OUT", data / "external_frontier.json")
    monkeypatch.setattr(runner, "QUEUE", tmp_path / "data" / "hypothesis_queue.jsonl")
    assert runner.main() == 0
    first = runner.QUEUE.read_text("utf-8").splitlines()
    assert len(first) == 1
    row = json.loads(first[0])
    assert row["status"] == "EXTERNAL_PRIOR"
    assert row["search_method"] == "reverse_engineering"
    assert runner.main() == 0
    assert len(runner.QUEUE.read_text("utf-8").splitlines()) == 1
    assert (tmp_path / "data" / "published_gaps" / "external_intelligence.json").exists()


def test_unextracted_claim_never_enters_queue(tmp_path: Path, monkeypatch) -> None:
    data = tmp_path / "data" / "intelligence"
    data.mkdir(parents=True)
    (data / "public_strategy_items.json").write_text(json.dumps({
        "items": [{"status": "EXTRACTION_FAILED", "mechanism": "claimed edge"}]
    }), "utf-8")
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    monkeypatch.setattr(runner, "OUT", data / "external_frontier.json")
    monkeypatch.setattr(runner, "QUEUE", tmp_path / "data" / "hypothesis_queue.jsonl")
    runner.main()
    assert not runner.QUEUE.exists()

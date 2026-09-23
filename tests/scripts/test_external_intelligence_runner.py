from __future__ import annotations

import json
from pathlib import Path

import scripts.run_external_intelligence as runner


def _mt5_paths(tmp_path: Path, monkeypatch) -> tuple[Path, Path]:
    queue = tmp_path / "desks" / "mt5" / "data" / "research_queue.json"
    queue.parent.mkdir(parents=True, exist_ok=True)
    queue.write_text("[]", "utf-8")
    family_source = tmp_path / "desks" / "mt5" / "research" / "run_hunt17.py"
    family_source.parent.mkdir(parents=True, exist_ok=True)
    family_source.write_text(
        "PARAMS = {'h4_momentum': [dict(n=34, rr=2.0, ttl=12)]}\n", "utf-8"
    )
    intake = tmp_path / "data" / "intelligence" / "mt5_external_intake.json"
    monkeypatch.setattr(runner, "MT5_QUEUE", queue)
    monkeypatch.setattr(runner, "MT5_INTAKE", intake)
    monkeypatch.setattr(runner, "MT5_FAMILY_SOURCE", family_source)
    return queue, intake


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
    mt5_queue, intake = _mt5_paths(tmp_path, monkeypatch)
    assert runner.main() == 0
    first = runner.QUEUE.read_text("utf-8").splitlines()
    assert len(first) == 1
    row = json.loads(first[0])
    assert row["status"] == "EXTERNAL_PRIOR"
    assert row["search_method"] == "reverse_engineering"
    assert runner.main() == 0
    assert len(runner.QUEUE.read_text("utf-8").splitlines()) == 1
    assert (tmp_path / "data" / "published_gaps" / "external_intelligence.json").exists()
    assert json.loads(mt5_queue.read_text("utf-8")) == []
    assert json.loads(intake.read_text("utf-8"))["dispositions"][0]["disposition"] == (
        "BLOCKED_IMPLEMENTATION"
    )


def test_unextracted_claim_never_enters_queue(tmp_path: Path, monkeypatch) -> None:
    data = tmp_path / "data" / "intelligence"
    data.mkdir(parents=True)
    (data / "public_strategy_items.json").write_text(json.dumps({
        "items": [{"status": "EXTRACTION_FAILED", "mechanism": "claimed edge"}]
    }), "utf-8")
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    monkeypatch.setattr(runner, "OUT", data / "external_frontier.json")
    monkeypatch.setattr(runner, "QUEUE", tmp_path / "data" / "hypothesis_queue.jsonl")
    _mt5_paths(tmp_path, monkeypatch)
    runner.main()
    assert not runner.QUEUE.exists()


def test_exact_supported_recipe_enters_executable_mt5_queue_once(
    tmp_path: Path, monkeypatch
) -> None:
    queue, intake = _mt5_paths(tmp_path, monkeypatch)
    item = {
        "status": "EXTRACTED",
        "url": "https://public.example/mechanism",
        "source": "public",
        "mechanism": "persistent H4 flow",
        "hypothesis": "flow persists after costs",
        "evidence_class": "FORWARD_PAPER_TRADING",
        "mt5_experiment": {
            "family": "h4_momentum",
            "side": "LONG",
            "param_overrides": {"n": 55, "rr": 2.5},
        },
    }
    first = runner.inject_mt5_experiments([item])
    second = runner.inject_mt5_experiments([item])
    rows = json.loads(queue.read_text("utf-8"))
    assert len(rows) == 1
    assert rows[0]["status"] == "QUEUED"
    assert rows[0]["authority"] == "EXTERNAL_PRIOR_ONLY_ORIGINAL_TEN_GATES_REQUIRED"
    assert len(first["queued"]) == 1
    assert second["queued"] == []
    assert json.loads(intake.read_text("utf-8"))["dispositions"][0]["disposition"] == (
        "DEDUPLICATED"
    )


def test_unknown_family_or_parameter_fails_closed(tmp_path: Path, monkeypatch) -> None:
    queue, _ = _mt5_paths(tmp_path, monkeypatch)
    base = {
        "status": "EXTRACTED",
        "url": "https://public.example/ticks",
        "mechanism": "signed tick pressure",
        "hypothesis": "tick pressure predicts 30 second returns",
    }
    report = runner.inject_mt5_experiments([
        {**base, "mt5_experiment": {
            "family": "tick_pressure", "side": "LONG", "param_overrides": {}
        }},
        {**base, "url": "https://public.example/bad-param", "mt5_experiment": {
            "family": "h4_momentum", "side": "LONG", "param_overrides": {"secret": 1}
        }},
    ])
    assert json.loads(queue.read_text("utf-8")) == []
    assert {row["disposition"] for row in report["dispositions"]} == {
        "REJECTED_INVALID_RECIPE"
    }

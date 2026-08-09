from __future__ import annotations

import json
from pathlib import Path

import scripts.research_alpha_optimizer as optimizer


def test_existing_optimizer_publishes_search_method_frontier(
    tmp_path: Path, monkeypatch
) -> None:
    data = tmp_path / "data"
    web = tmp_path / "web"
    data.mkdir()
    web.mkdir()
    ledger = data / "decision_ledger.json"
    ledger.write_text(json.dumps({
        "decisions": [{
            "id": "d1",
            "search_method": "constraint_first",
            "useful_information": True,
            "hypothesis": "forced collateral migration",
        }]
    }), "utf-8")
    (web / "axis_shadows.json").write_text(json.dumps({"axes": []}), "utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(optimizer, "LEDGER", ledger)
    monkeypatch.setattr(optimizer, "OUT", data / "research_alpha_optimizer.json")
    monkeypatch.setattr(optimizer, "HIST", data / "method_outcomes.jsonl")
    optimizer.main()
    saved = json.loads(optimizer.OUT.read_text("utf-8"))
    evolution = saved["search_strategy_evolution"]
    assert evolution["coverage"]["represented"] == 1
    assert evolution["serendipity_channel"]["bounded_concurrent_missions"] == 1
    assert saved["mode"] == "INSTRUMENTING"

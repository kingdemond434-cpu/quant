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


def test_keyword_hits_are_not_published_as_survivors_or_shadow_candidates(
    tmp_path: Path, monkeypatch
) -> None:
    data = tmp_path / "data"
    web = tmp_path / "web"
    data.mkdir()
    web.mkdir()
    ledger = data / "decision_ledger.json"
    ledger.write_text(
        json.dumps(
            {
                "decisions": [
                    {
                        "id": "deadman-reset",
                        "decision": "combined filter path replicates the risk formula",
                    },
                    {
                        "id": "onchain-wired",
                        "decision": "composite throughput axis wired to a forward clock",
                    },
                ]
            }
        ),
        "utf-8",
    )
    (web / "axis_shadows.json").write_text(
        json.dumps({"updated": "2026-08-09T00:00:00Z", "axes": []}),
        "utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(optimizer, "LEDGER", ledger)
    monkeypatch.setattr(optimizer, "OUT", data / "research_alpha_optimizer.json")
    monkeypatch.setattr(optimizer, "HIST", data / "method_outcomes.jsonl")

    optimizer.main()

    saved = json.loads(optimizer.OUT.read_text("utf-8"))
    assert saved["confirmed_edges"] == 0
    assert saved["strategy_survivors"]["count"] == 0
    assert saved["shadow_admission"]["eligible"] == []
    weak = saved["weak_label_diagnostics"]
    assert weak["classification_authority"] == "NONE"
    fusion = next(row for row in weak["methods"] if row["method"] == "fusion")
    assert fusion["keyword_classified_hits"] == 2
    assert set(fusion["keyword_hit_ids"]) == {"deadman-reset", "onchain-wired"}
    assert "survivors" not in fusion


def test_same_day_rerun_does_not_fabricate_history_windows(
    tmp_path: Path, monkeypatch
) -> None:
    data = tmp_path / "data"
    web = tmp_path / "web"
    data.mkdir()
    web.mkdir()
    ledger = data / "decision_ledger.json"
    ledger.write_text(json.dumps({"decisions": []}), "utf-8")
    (web / "axis_shadows.json").write_text(json.dumps({"axes": []}), "utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(optimizer, "LEDGER", ledger)
    monkeypatch.setattr(optimizer, "OUT", data / "research_alpha_optimizer.json")
    monkeypatch.setattr(optimizer, "HIST", data / "method_outcomes.jsonl")

    optimizer.main()
    optimizer.main()

    rows = [
        json.loads(line)
        for line in optimizer.HIST.read_text("utf-8").splitlines()
        if line.strip()
    ]
    assert len(rows) == 1

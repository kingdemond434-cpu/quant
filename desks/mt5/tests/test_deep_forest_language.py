"""The deep-forest miner stamps language and region on every donated row and keeps a
per-language frontier (Tier-1 I17).

The registry holds 502 grounds in 26 languages and nothing reported which languages produced a
finding. Pinned: tasks and dataset rows carry the ground's `language` beside `lang`, every ground
enters the frontier state as NAMED_ONLY with its language, a run's statuses become YIELDED /
EMPTY / BLOCKED per ground, a skipped run never demotes hunted ground, and the report carries the
per-language rollup.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_DESK = Path(__file__).resolve().parents[1]
for p in (str(_DESK), str(_DESK / "research"), str(_DESK / "side_channels")):
    if p not in sys.path:
        sys.path.insert(0, p)

from libs.research import hunt_frontier as hf  # noqa: E402
from research import deep_forest_miner as dfm  # noqa: E402

_GROUNDS = [
    {"name": "七禾网", "region": "cn", "language": "zh", "route": "http", "kind": "interview",
     "url": "https://www.7hcn.com/"},
    {"name": "smart-lab", "region": "ru", "language": "ru", "route": "foreign", "kind": "forum"},
    {"name": "velog", "region": "kr", "language": "ko", "route": "foreign", "kind": "blog"},
]


def test_a_task_carries_the_grounds_language_beside_the_claims_lang() -> None:
    row = {"claim": "黄金夜盘开盘后前30分钟顺势做多", "lang": "zh-Hans", "language": "zh",
           "region": "cn", "cluster": "cn", "ground": "七禾网", "route": "http",
           "url": "https://www.7hcn.com/a", "evidence_grade": "INTERVIEW", "score": 0.5,
           "claim_hash": "abc", "mechanism_class": "momentum"}
    t = dfm._task(row)
    assert t["lang"] == "zh-Hans" and t["language"] == "zh" and t["region"] == "cn"
    assert dfm._task({**row, "language": None})["language"] == "zh-Hans"   # falls to the claim


def test_every_registered_ground_enters_the_frontier_named_only_with_its_language(
        tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(dfm, "SEEN", tmp_path / "seen.json")
    out = dfm._record_frontier([], _GROUNDS)
    assert out["vectors"] == 3 and out["unhunted"] == 3
    assert out["by_language"] == {
        "ko": {"NAMED_ONLY": 1, "BLOCKED": 0, "EMPTY": 0, "YIELDED": 0, "findings": 0,
               "vectors": 1},
        "ru": {"NAMED_ONLY": 1, "BLOCKED": 0, "EMPTY": 0, "YIELDED": 0, "findings": 0,
               "vectors": 1},
        "zh": {"NAMED_ONLY": 1, "BLOCKED": 0, "EMPTY": 0, "YIELDED": 0, "findings": 0,
               "vectors": 1}}
    assert out["languages_named_only"] == ["ko", "ru", "zh"] and out["languages_yielded"] == []
    st = hf.load(tmp_path / "deep_forest_frontier.json")
    assert st.vectors["七禾网"].language == "zh" and st.vectors["七禾网"].region == "cn"


def test_statuses_become_outcomes_and_a_skipped_run_never_demotes_hunted_ground(
        tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(dfm, "SEEN", tmp_path / "seen.json")
    status = [{"ground": "七禾网", "region": "cn", "language": "zh", "status": "PRODUCTIVE",
               "claims": 4},
              {"ground": "smart-lab", "region": "ru", "language": "ru",
               "status": "REACHED_NO_CLAIMS", "claims": 0},
              {"ground": "velog", "region": "kr", "language": "ko", "status": "NO_NETWORK",
               "why": "three straight transport failures on this box"}]
    out = dfm._record_frontier(status, _GROUNDS)
    assert out["by_language"]["zh"]["YIELDED"] == 1 and out["by_language"]["zh"]["findings"] == 4
    assert out["by_language"]["ru"]["EMPTY"] == 1
    assert out["by_language"]["ko"]["BLOCKED"] == 1
    assert out["languages_yielded"] == ["zh"] and out["languages_named_only"] == []
    st = hf.load(tmp_path / "deep_forest_frontier.json")
    assert st.vectors["velog"].blocker.startswith("NO_NETWORK: three straight")
    # a --no-fetch or budget-exhausted run records nothing about hunted ground
    again = dfm._record_frontier([{"ground": "七禾网", "status": "SKIPPED"},
                                  {"ground": "velog", "status": "BUDGET_EXHAUSTED"}], _GROUNDS)
    assert again["by_language"]["zh"]["YIELDED"] == 1
    assert again["by_language"]["ko"]["BLOCKED"] == 1 and again["unhunted"] == 0


def test_run_publishes_the_frontier_and_write_false_leaves_it_untouched(tmp_path,
                                                                        monkeypatch) -> None:
    monkeypatch.setattr(dfm, "CLAIMS", tmp_path / "claims.jsonl")
    monkeypatch.setattr(dfm, "SEEN", tmp_path / "seen.json")
    monkeypatch.setattr(dfm, "REPORT", tmp_path / "DEEP_FOREST.json")
    monkeypatch.setattr(dfm, "PROVENANCE", tmp_path / "mined_sources.jsonl")
    monkeypatch.setattr(dfm, "DATASETS", tmp_path / "datasets.jsonl")
    monkeypatch.setattr(dfm, "WORLD", tmp_path / "world")
    monkeypatch.setattr(dfm, "SOURCES", tmp_path / "sources.json")
    monkeypatch.setattr(dfm, "_feed_frontier", lambda urls: 0)
    monkeypatch.setattr(dfm, "_universe", lambda: {"XAUUSD"})
    import research.regime_coverage as rc
    monkeypatch.setattr(rc, "_merge_into_queue", lambda tasks, source="x": None)
    (tmp_path / "sources.json").write_text(json.dumps({"grounds": _GROUNDS}), "utf-8")
    doc = dfm.run(budget_s=5, fetch=False)
    assert doc["frontier"]["vectors"] == 3 and doc["frontier"]["unhunted"] == 3
    assert set(doc["frontier"]["by_language"]) == {"zh", "ru", "ko"}
    assert doc["frontier"]["path"].endswith("deep_forest_frontier.json")
    assert (tmp_path / "deep_forest_frontier.json").exists()
    assert "frontier (data/deep_forest_frontier.json" in " ".join(doc["ledger_schema"])
    doc2 = dfm.run(budget_s=5, fetch=False, write=False)
    assert doc2["frontier"]["status"] == "UNMEASURED" and "write=False" in doc2["frontier"]["why"]

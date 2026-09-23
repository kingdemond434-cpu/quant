"""THE META-EVOLUTION LAYER on tmp state: a mutation touching a rail is refused and never
applied; the QD archive's occupancy rises across passes; a dry run writes nothing; and when the
fence is not seen refusing the self-test, nothing is applied at all."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_ROOT), str(_DESK), str(_DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.research import immutable_rails as IR  # noqa: E402
from research import research_evolution as RE  # noqa: E402


@pytest.fixture
def rig(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    state = tmp_path / "data" / "research_evolution"
    monkeypatch.setattr(RE, "STATE_DIR", state)
    monkeypatch.setattr(RE, "POPULATION", state / "population.json")
    monkeypatch.setattr(RE, "ARCHIVE", state / "archive.json")
    monkeypatch.setattr(RE, "LINEAGE", state / "lineage.jsonl")
    monkeypatch.setattr(RE, "ACTIVE", state / "active_variants.json")
    monkeypatch.setattr(RE, "OUT", tmp_path / "reports" / "RESEARCH_EVOLUTION.json")
    for name in ("ROI_REPORT", "COMPUTE_POLICY", "COVERAGE", "RESIDUAL", "ADVERSARY_POP",
                 "FORGE", "AXIS", "SPECIALISATION"):
        monkeypatch.setattr(RE, name, tmp_path / "absent" / f"{name}.json")
    monkeypatch.setattr(RE, "_record_discovery", lambda g, v: ("stub", "stubbed"))
    monkeypatch.setattr(RE, "_record_request", lambda r: ("stub", "stubbed"))
    return tmp_path


def test_dry_run_writes_nothing(rig: Path) -> None:
    doc = RE.run(budget_s=30, dry_run=True, n_proposals=4, seed=1)
    assert doc["status"] == "OK" and doc["dry_run"] is True
    assert not (rig / "data").exists() and not (rig / "reports").exists()
    assert doc["proposals"]["n"] == 4 and len(doc["proposals"]["applied"]) == 4
    assert doc["fitness"]["n_variants_credited"] == 0
    assert any(u["what"] == "variant fitness" for u in doc["unmeasured"])


def test_archive_occupancy_rises_across_passes_and_state_persists(rig: Path) -> None:
    first = RE.run(budget_s=30, dry_run=False, n_proposals=6, seed=1)
    assert first["archive"]["occupancy"] == first["archive"]["lit_this_pass"] > 0
    assert (RE.POPULATION.exists() and RE.ARCHIVE.exists() and RE.LINEAGE.exists()
            and RE.ACTIVE.exists() and RE.OUT.exists())
    second = RE.run(budget_s=30, dry_run=False, n_proposals=6, seed=2)
    assert second["archive"]["occupancy"] > first["archive"]["occupancy"]
    assert second["archive"]["occupancy_before"] == first["archive"]["occupancy"]
    assert second["population"]["generation"] == 2
    assert second["archive"]["possible"] == RE.possible_cells()
    rows = [json.loads(ln) for ln in RE.LINEAGE.read_text("utf-8").splitlines() if ln.strip()]
    assert len(rows) == 12 and all(r["applied"] for r in rows)
    assert all(r["touches"] for r in rows), "every applied variant declares its change set"
    active = json.loads(RE.ACTIVE.read_text("utf-8"))["variants"]
    assert active and all(v["basis"].startswith("newest applied") for v in active.values())
    assert set(second["consumers"]) == set(RE.SEARCH_FAMILIES)
    assert second["curriculum"] and all("question" in q for q in second["curriculum"])


def test_a_mutation_touching_a_rail_is_refused_and_never_applied(
        rig: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    hard = {"status": "UNMEASURED"}
    good = RE.make_genome("mcts_tree", "bars", "japan", "sub_4h",
                         RE.random_config("mcts_tree", __import__("random").Random(3)),
                         [], 1, "immigrant", hard)
    bad = RE.make_genome("grammar_evolution", "tape", "korea", "intrabar",
                         RE.random_config("grammar_evolution", __import__("random").Random(4)),
                         [], 1, "immigrant", hard)
    bad["touches"] = [{"path": "desks/mt5/scripts/external_gauntlet.py", "symbols": ["run"]},
                      {"path": "libs/moat/registry.py", "symbols": ["record_trial"]}]
    monkeypatch.setattr(RE, "propose", lambda *a, **k: [good, bad])
    doc = RE.run(budget_s=30, dry_run=False, n_proposals=2, seed=5)
    assert [r["id"] for r in doc["proposals"]["applied"]] == [good["id"]]
    refused = doc["proposals"]["refused"]
    assert len(refused) == 1 and refused[0]["id"] == bad["id"]
    names = {(r["path"], r["symbol"]) for r in refused[0]["refused"]}
    assert ("desks/mt5/scripts/external_gauntlet.py", None) in names
    assert ("libs/moat/registry.py", "record_trial") in names
    pop = json.loads(RE.POPULATION.read_text("utf-8"))
    assert [g["id"] for g in pop["genomes"]] == [good["id"]]
    rows = [json.loads(ln) for ln in RE.LINEAGE.read_text("utf-8").splitlines() if ln.strip()]
    assert {r["id"]: r["applied"] for r in rows} == {good["id"]: True, bad["id"]: False}
    assert doc["rails_self_test"]["refused"] is True


def test_nothing_is_applied_when_the_fence_is_not_seen_refusing(
        rig: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(RE.IR, "refuse_proposal", lambda p, rails=None: IR.Verdict(ok=True))
    doc = RE.run(budget_s=30, dry_run=False, n_proposals=3, seed=1)
    assert doc["status"] == "BLOCKED" and "NOT refused" in doc["why"]
    assert not RE.POPULATION.exists() and not RE.LINEAGE.exists()


def test_archive_keeps_one_elite_per_cell_and_only_measured_fitness_displaces() -> None:
    archive: dict = {"cells": {}}
    a = {"id": "a", "search_family": "mcts_tree", "data_family": "bars", "region": "japan",
         "horizon": "sub_4h", "fitness": {"status": "UNMEASURED"}}
    b = {**a, "id": "b"}
    c = {**a, "id": "c", "fitness": {"status": "MEASURED", "value": 0.5}}
    d = {**a, "id": "d", "fitness": {"status": "MEASURED", "value": 0.1}}
    assert RE.archive_put(archive, a) and not RE.archive_put(archive, b)
    assert RE.archive_put(archive, c) and not RE.archive_put(archive, d)
    assert archive["cells"][RE.cell_key(a)]["genome_id"] == "c"
    assert RE.split_from_policy(None)[0] == RE.DEFAULT_SPLIT
    assert abs(sum(RE.split_from_policy({"split": {"exploitation": 0.5, "exploration": 0.3,
                                                   "frontier": 0.2}})[0].values()) - 1.0) < 1e-9

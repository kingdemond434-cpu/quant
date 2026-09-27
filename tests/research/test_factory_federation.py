from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from libs.research import factory_federation as F

ROOT = Path(__file__).resolve().parents[2]
SPEC = ROOT / "docs" / "research" / "factory_surfaces_v1.json"
RUNNER_PATH = ROOT / "desks" / "mt5" / "research" / "factory_federation.py"


def _runner():
    spec = importlib.util.spec_from_file_location("factory_federation_runner", RUNNER_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_manifest_covers_every_named_factory_and_separates_rights() -> None:
    rows = F.load_manifest(json.loads(SPEC.read_text("utf-8")))
    factories = {r.factory_id for r in rows}
    assert {"numerai", "quantconnect", "worldquant", "quantiacs", "cloudquant",
            "collective2", "crunchdao", "quantpedia", "kaggle_finance", "mql5",
            "joinquant", "bigquant", "ricequant", "strategyquant", "rd_agent_qlib",
            "historical_factories"} <= factories
    assert all(set(r.rights) == set(F.RIGHTS) for r in rows)
    brain = next(r for r in rows if r.key == "worldquant:brain_public")
    assert brain.rights["read"] == "PUBLIC" and brain.rights["automate"] == "NO"
    assert F.access_blocker(brain) == "AUTOMATION_NO"


def test_manifest_refuses_a_surface_with_implicit_rights() -> None:
    with pytest.raises(ValueError, match="missing rights"):
        F.load_manifest({"factories": [{"factory_id": "x", "worker": "w", "surfaces": [{
            "surface_id": "s", "source_uri": "https://x", "surface_type": "documentation",
            "language": "en", "rights": {"read": "PUBLIC"}, "cadence_hours": 1,
            "evaluation_lane": "RESEARCH_PROCESS"}]}]})


def test_non_github_surface_reaches_version_registry_and_compiler_handoff(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    runner = _runner()
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    (inbox / "numerai.json").write_text(json.dumps({
        "factory_id": "numerai", "surface_id": "docs_data", "version": "2026-09-27",
        "content": "era-aware neutralized lagged forecasts",
        "family": "trend_ma_cross", "symbols": ["EURUSD"],
        "mechanism": "lagged cross-sectional information persists across independent eras",
        "falsifier": "no positive PIT OOS contribution after costs and neutralization",
        "source_rule_or_reconstruction": "RECONSTRUCTED",
        "components": [{"component_id": "era-neutral", "type": "feature",
                        "target_lane": "DATA_REPRESENTATION"}]}, indent=1), "utf-8")
    monkeypatch.setattr(runner, "PROCESSED", tmp_path / "processed")
    monkeypatch.setattr(runner, "DONATIONS", tmp_path / "donations")
    monkeypatch.setattr(runner, "_record_registry", lambda row: True)
    state, report = tmp_path / "state.json", tmp_path / "report.json"
    got = runner.run(manifest=SPEC, state_path=state, inbox=inbox, report=report)
    assert got["counts"]["new_versions"] == 1
    assert got["counts"]["donated_cells"] == 1
    row = got["new_versions"][0]
    assert row["consumer_ack"] == {"registry_intake": True, "evaluator_handoff": True,
                                    "eventual_disposition": False}
    assert row["input_version_id"] and row["content_hash"]
    assert next((tmp_path / "donations").glob("discoveries_*.json"))


def test_restart_deduplicates_content_version(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    runner = _runner()
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    payload = {"factory_id": "quantiacs", "surface_id": "docs", "content": "sequential replay"}
    (inbox / "one.json").write_text(json.dumps(payload), "utf-8")
    monkeypatch.setattr(runner, "PROCESSED", tmp_path / "processed")
    monkeypatch.setattr(runner, "DONATIONS", tmp_path / "donations")
    monkeypatch.setattr(runner, "_record_registry", lambda row: True)
    state, report = tmp_path / "state.json", tmp_path / "report.json"
    assert runner.run(manifest=SPEC, state_path=state, inbox=inbox, report=report)["counts"][
        "new_versions"] == 1
    (inbox / "two.json").write_text(json.dumps(payload), "utf-8")
    again = runner.run(manifest=SPEC, state_path=state, inbox=inbox, report=report)
    assert again["counts"]["new_versions"] == 0 and again["counts"]["versions"] == 1


def test_cross_factory_synthesis_is_ablation_complete_and_has_no_authority() -> None:
    got = F.synthesis_plan(({"factory_id": "a", "component_id": "x"},
                            {"factory_id": "b", "component_id": "y"}))
    assert [r["name"] for r in got["ablation_plan"]] == ["baseline", "only_a", "only_b",
                                                                  "combined"]
    assert "research proposal only" in got["authority"]

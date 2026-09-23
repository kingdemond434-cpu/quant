"""The model zoo enrols the generators it already has, and reports an AI-vs-no-LLM delta.

Measured 2026-09-08 (inventory I11): MODEL_ZOO.json said `entrants: 0` every hour while the
external-screen chain and two LLM seats produced hypotheses the gauntlet judged. These tests pin
the generator league: entrants over the compiler's own window, survivors counted from the
hypothesis graph inside that window only, hours from the ledger where a leg was costed and
UNCOSTED named where none was, and a delta that is MEASURED only when both sides entered rows.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent.parent
_RESEARCH = _ROOT / "desks" / "mt5" / "research"


@pytest.fixture(scope="module")
def zoo():
    spec = importlib.util.spec_from_file_location("_model_zoo_gen", _RESEARCH / "model_zoo.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


COMPILED = {
    "compiled_at": "2026-09-08T12:00:00+00:00",
    "per_source": {"cot": {"rows": 22, "candidates": 7, "deepening": 0}},
    "seats": {"deepseek": {"rows": 40, "candidates": 5, "deepening": 35},
              "kimi_k3_deep_forest": {"rows": 0, "candidates": 0, "deepening": 0}},
}


def _row(i: int, source: str, fate: str, at: str) -> dict:
    return {"id": f"n{i}", "source": source, "fate": fate, "at": at, "region": "r", "symbol": "X",
            "family": "f", "params": {}}


IN = "2026-09-05T00:00:00+00:00"        # inside the 7-day window ending 2026-09-08T12:00
OUT = "2026-08-20T00:00:00+00:00"       # before it
GRAPH = [
    _row(1, "external", "BORN", IN), _row(1, "external", "CERTIFIED", IN),
    _row(2, "edge_search:hour", "FAILED", IN),
    _row(3, "external", "CERTIFIED", OUT),                 # outside the window: not counted
    _row(4, "miner:deepseek", "BORN", IN), _row(4, "miner:deepseek", "FAILED", IN),
    _row(5, "deepseek", "CERTIFIED", IN),
    _row(6, "fund_playbook:Renaissance:A", "BORN", IN),    # neither entrant
]
COSTS = {"search": {"runs": 2, "wall_s": 1440.0, "cpu_s": 1.0, "failures": 0, "hours": 0.4}}


def test_the_no_llm_arm_and_the_seats_are_entrants_over_the_compilers_window(zoo) -> None:
    ents = zoo.generator_entrants(COMPILED, GRAPH, COSTS)
    by = {e["model_id"]: e for e in ents}
    assert set(by) == {"external_screen", "deepseek", "kimi_k3_deep_forest"}
    ext = by["external_screen"]
    assert ext["kind"] == "no_llm"
    assert ext["window"] == ["2026-09-01T12:00:00+00:00", "2026-09-08T12:00:00+00:00"]
    assert (ext["rows"], ext["judged"], ext["survivors"]) == (2, 2, 1)   # n3 is out of window
    assert ext["survivor_yield"] == 0.5
    ds = by["deepseek"]
    assert ds["kind"] == "llm_seat" and ds["rows"] == 40 and ds["candidates"] == 5
    assert (ds["judged"], ds["survivors"]) == (2, 1)                   # miner:deepseek + deepseek
    assert "seats" in ds["rows_basis"]
    kimi = by["kimi_k3_deep_forest"]
    assert kimi["rows"] == 0 and kimi["survivors"] == 0


def test_hours_are_measured_where_a_leg_was_costed_and_uncosted_is_named_elsewhere(zoo) -> None:
    by = {e["model_id"]: e for e in zoo.generator_entrants(COMPILED, GRAPH, COSTS)}
    assert by["external_screen"]["compute_hours"] == 0.4
    assert by["external_screen"]["cost_basis"].startswith("measured: 2 run(s) of search")
    assert by["external_screen"]["survivors_per_hour"] == 2.5
    assert by["deepseek"]["compute_hours"] is None
    assert by["deepseek"]["cost_basis"].startswith("UNCOSTED")
    assert by["deepseek"]["survivors_per_hour"] is None
    nothing = {e["model_id"]: e for e in zoo.generator_entrants(COMPILED, GRAPH, {})}
    assert "search" in nothing["external_screen"]["cost_basis"]
    assert nothing["external_screen"]["cost_basis"].startswith("UNCOSTED")


def test_the_delta_is_measured_when_both_sides_entered_rows(zoo) -> None:
    v = zoo.ai_vs_no_llm(zoo.generator_entrants(COMPILED, GRAPH, COSTS))
    assert v["status"] == "MEASURED"
    assert v["delta_survivors"] == 0                     # 1 seat survivor vs 1 no-LLM survivor
    assert v["no_llm"]["survivors"] == 1 and v["llm_seats"]["survivors"] == 1
    assert v["llm_seats"]["rows"] == 40 and v["llm_seats"]["seats"] == list(zoo.SEATS)
    assert v["decisive"] is False                        # shared sample 2 < MIN_SHARED_N
    assert v["per_hour_comparable"] is False
    assert "INCOMPARABLE per hour" in v["per_hour_why"] and "deepseek" in v["per_hour_why"]


def test_a_delta_against_an_empty_entrant_is_unmeasured_not_zero(zoo) -> None:
    quiet = json.loads(json.dumps(COMPILED))
    quiet["seats"] = {s: {"rows": 0, "candidates": 0, "deepening": 0} for s in zoo.SEATS}
    graph = [r for r in GRAPH if "deepseek" not in r["source"]]
    v = zoo.ai_vs_no_llm(zoo.generator_entrants(quiet, graph, COSTS))
    assert v["status"] == "UNMEASURED"
    assert "donated 0 rows" in v["why"] and "empty entrant" in v["why"]
    assert v["delta_survivors"] == -1                    # the arithmetic is still shown


def test_a_compiled_artifact_without_a_seats_block_names_it(zoo) -> None:
    old = {k: v for k, v in COMPILED.items() if k != "seats"}
    by = {e["model_id"]: e for e in zoo.generator_entrants(old, GRAPH, COSTS)}
    assert by["deepseek"]["rows"] is None
    assert "`seats` block" in by["deepseek"]["rows_basis"]
    assert "2026-09-08" in by["deepseek"]["rows_basis"]
    v = zoo.ai_vs_no_llm(list(by.values()))
    assert v["status"] == "UNMEASURED" and "rows in the window are unknown" in v["why"]


def test_no_compiled_artifact_means_no_window_and_says_so(zoo, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(zoo, "COMPILED", tmp_path / "absent.json")
    g = zoo.generator_league()
    assert g["status"] == "UNMEASURED" and g["entrants"] == []
    assert "absent.json" in g["missing_input"] and "compiled_at" in g["missing_input"]
    assert zoo.shared_window({}) is None and zoo.shared_window(None) is None


def test_generator_identity_follows_the_bandits_arm_and_the_seat_names(zoo) -> None:
    assert zoo.generator_of("miner:deepseek") == "deepseek"
    assert zoo.generator_of("kimi_k3_deep_forest") == "kimi_k3_deep_forest"
    assert zoo.generator_of("edge_search:hour") == "external_screen"
    assert zoo.generator_of("deep_forest_jp") == "external_screen"
    assert zoo.generator_of("fund_playbook:Renaissance:A") is None
    assert zoo.generator_of("miner:cot") is None


def test_run_counts_generator_entrants_and_publishes_the_delta(zoo) -> None:
    doc = zoo.run()
    assert doc["entrants"] == doc["forecaster_entrants"] + doc["generator_entrants"]
    assert doc["generators"]["status"] in ("MEASURED", "UNMEASURED")
    assert "ai_vs_no_llm" in doc["generators"]
    if doc["generators"]["status"] == "MEASURED":
        assert doc["generator_entrants"] == 1 + len(zoo.SEATS)
        assert doc["generators"]["ai_vs_no_llm"]["status"] in ("MEASURED", "UNMEASURED")


def test_the_ledger_is_read_where_the_hourly_cycle_writes_it(zoo, tmp_path) -> None:
    """The zoo read `<repo>/data/compute_ledger.jsonl` for a `seconds` key: a file that never
    existed, for a key the ledger never writes. It now reads `wall_s` from the desk's ledger."""
    assert zoo.LEDGER == zoo.BASE / "data" / "compute_ledger.jsonl"
    p = tmp_path / "ledger.jsonl"
    p.write_text("".join(json.dumps({"at": "2026-09-06T11:00:00+00:00", "run": f"r{i}",
                                     "wall_s": 360.0, "cpu_s": 1.0}) + "\n"
                         for i in range(6)), "utf-8")
    per_hour, why = zoo.cost_per_hour(p)
    assert per_hour == zoo.DEFAULT_COST_PER_HOUR            # still a declared price ...
    assert "over 6 ledger run(s) totalling 0.6h" in why    # ... but the hours are now counted
